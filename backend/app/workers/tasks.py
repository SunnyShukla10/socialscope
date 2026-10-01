import asyncio
import uuid
from datetime import datetime, timedelta, timezone

from celery.utils.log import get_task_logger

from app.services.collection_status import collection_terminal_status
from app.services.collection_lifecycle import (
    can_transition_job_status,
    finalize_platform_cancellation,
    platform_state,
)
from app.adapters.cancellation import CancellationSignal
from app.services.platform_collection import (
    PlatformCollectionRequest,
    iter_platform_results,
)
from app.workers.celery_app import celery_app

logger = get_task_logger(__name__)


def _run_async(coro):
    """Run an async coroutine from a synchronous Celery task."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    if loop.is_closed():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


def _active_celery_task_ids() -> set[str] | None:
    """Return task IDs currently executing, or None when inspection is unavailable."""
    from app.config import settings

    try:
        inspector = celery_app.control.inspect(
            timeout=settings.COLLECTION_ABANDONED_INSPECT_TIMEOUT_SECONDS
        )
        workers = inspector.active()
        if workers is None:
            return None
        return {
            str(task["id"])
            for tasks in workers.values()
            for task in tasks
            if task.get("id")
        }
    except Exception as exc:
        logger.warning(
            "Could not inspect Celery workers during abandoned-job recovery (%s)",
            type(exc).__name__,
        )
        return None


@celery_app.task
def reconcile_abandoned_collection_jobs():
    """Periodically finalize stale running or cancelling collection jobs."""
    from app.config import settings

    active_task_ids = _active_celery_task_ids()
    recovered_at = datetime.now(timezone.utc)
    stale_before = recovered_at - timedelta(
        seconds=settings.COLLECTION_ABANDONED_JOB_STALE_SECONDS
    )

    async def _execute():
        from sqlalchemy.ext.asyncio import (
            AsyncSession,
            async_sessionmaker,
            create_async_engine,
        )
        from app.services.abandoned_jobs import reconcile_abandoned_jobs

        engine = create_async_engine(settings.DATABASE_URL, echo=False)
        SessionLocal = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        try:
            async with SessionLocal() as db:
                return await reconcile_abandoned_jobs(
                    db,
                    stale_before=stale_before,
                    recovered_at=recovered_at,
                    batch_size=settings.COLLECTION_ABANDONED_RECONCILE_BATCH_SIZE,
                    active_task_ids=active_task_ids,
                )
        finally:
            await engine.dispose()

    recovered = _run_async(_execute())
    if not recovered:
        return {"recovered": 0, "jobs": []}

    return {"recovered": len(recovered), "jobs": [str(job.job_id) for job in recovered]}


async def _monitor_collection_cancellation(
    SessionLocal,
    job_uuid: uuid.UUID,
    cancellation: CancellationSignal,
    poll_seconds: float,
) -> None:
    from sqlalchemy import select
    from app.models.search_job import SearchJob

    while not cancellation.is_cancelled:
        try:
            async with SessionLocal() as db:
                status = (
                    await db.execute(
                        select(SearchJob.status).where(SearchJob.id == job_uuid)
                    )
                ).scalar_one_or_none()
            if status in {"cancelling", "cancelled"}:
                cancellation.cancel()
                return
        except Exception as exc:
            logger.warning(
                "Could not check cancellation state for job %s (%s)",
                job_uuid,
                type(exc).__name__,
            )
        await asyncio.sleep(poll_seconds)


async def _record_provider_progress(
    SessionLocal,
    job_uuid: uuid.UUID,
    platform: str,
    event: dict,
) -> None:
    from sqlalchemy import select
    from app.models.search_job import SearchJob

    progress_at = datetime.now(timezone.utc)
    async with SessionLocal() as db:
        job = (
            await db.execute(
                select(SearchJob)
                .where(SearchJob.id == job_uuid)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if not job or job.status not in {"running", "cancelling"}:
            return

        states = dict(job.platform_states or {})
        state_key = next(
            (key for key in states if str(key).lower() == platform.lower()),
            platform.lower(),
        )
        state = dict(
            states.get(state_key)
            or platform_state("running", started_at=job.started_at)
        )
        if state.get("status") in {"pending", "running", "cancel_requested"}:
            state["last_progress_at"] = progress_at.isoformat()
            if event.get("stop_reason"):
                state["provider_stop_reason"] = event["stop_reason"]
            if event.get("stop_details"):
                state["provider_stop_details"] = {**(state.get("provider_stop_details") or {}), **event["stop_details"]}
            states[state_key] = state
            job.platform_states = states
            job.last_progress_at = progress_at
            await db.commit()


async def _iter_cancellable_platform_results(
    router,
    requests,
    SessionLocal,
    job_uuid: uuid.UUID,
    poll_seconds: float,
):
    cancellation = CancellationSignal()

    async def record_progress(platform: str, event: dict) -> None:
        await _record_provider_progress(
            SessionLocal,
            job_uuid,
            platform,
            event,
        )

    monitor = asyncio.create_task(
        _monitor_collection_cancellation(
            SessionLocal,
            job_uuid,
            cancellation,
            poll_seconds,
        )
    )
    try:
        async for result in iter_platform_results(
            router,
            requests,
            cancellation,
            record_progress,
        ):
            yield result
    finally:
        monitor.cancel()
        await asyncio.gather(monitor, return_exceptions=True)


def _deduplicate_raw_posts(platform: str, posts: tuple[dict, ...]) -> list[dict]:
    unique_posts: dict[tuple[str, str], dict] = {}
    for post in posts:
        external_id = post.get("external_id")
        if external_id is None or str(external_id).strip() == "":
            logger.warning("Skipping %s post without a stable external ID", platform)
            continue
        normalized_platform = str(post.get("platform") or platform).lower()
        key = (normalized_platform, str(external_id))
        unique_posts.setdefault(key, post)
    return list(unique_posts.values())


def _collection_shortfall_message(
    provider_posts: int,
    committed_posts: int,
    requested_posts: int,
    provider_stop_reason: str | None = None,
) -> str | None:
    """Return a user-safe explanation when a provider cannot fill its allocation."""
    if requested_posts <= 0 or committed_posts >= requested_posts:
        return None
    duplicate_count = max(0, provider_posts - committed_posts)
    message = (
        f"Provider returned {provider_posts:,} of {requested_posts:,} requested posts; "
        f"{committed_posts:,} unique posts were saved"
    )
    if duplicate_count:
        message += f" ({duplicate_count:,} duplicate or previously saved)"
    if provider_stop_reason == "empty_page_with_continuation":
        return (
            f"{message}. The next provider page contained no posts but included another "
            "pagination cursor, so SocialScope stopped to avoid additional credit usage."
        )
    return f"{message}. The provider may have exhausted matching results or stopped pagination."


async def _persist_platform_posts(
    db,
    job,
    platform: str,
    raw_posts: tuple[dict, ...],
) -> tuple[int, tuple[uuid.UUID, ...]]:
    from sqlalchemy import select, func
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from app.models.normalized_post import NormalizedPost
    from app.models.account import Account
    from app.models.collection_pull import RunPost, CollectionPull
    from app.models.search_job import SearchJob
    from app.services.budget_service import MAX_PULL_POSTS

    # Serialize accepted posts across platforms and all previews of this pull.
    pull_seen = set()
    if job.pull_id:
        await db.execute(select(CollectionPull.id).where(CollectionPull.id == job.pull_id).with_for_update())
        pull_seen = set((await db.execute(select(NormalizedPost.platform, NormalizedPost.external_id)
            .join(RunPost, RunPost.post_id == NormalizedPost.id)
            .join(SearchJob, SearchJob.id == RunPost.job_id)
            .where(SearchJob.pull_id == job.pull_id).distinct())).all())

    inserted_count = 0
    account_ids: set[uuid.UUID] = set()
    allocation = (job.platform_allocations or {}).get(platform, 0)
    existing_count = (await db.execute(select(func.count(RunPost.post_id)).join(
        NormalizedPost, NormalizedPost.id == RunPost.post_id).where(
        RunPost.job_id == job.id, NormalizedPost.platform == platform))).scalar_one()
    for raw in _deduplicate_raw_posts(platform, raw_posts):
        if existing_count + inserted_count >= allocation:
            break
        post_platform = str(raw.get("platform") or platform).lower()
        identity = (post_platform, str(raw["external_id"]))
        if job.pull_id and identity not in pull_seen and len(pull_seen) >= MAX_PULL_POSTS:
            continue
        account_id = None
        username = raw.get("author_username")
        if username:
            acc_result = await db.execute(
                select(Account).where(
                    Account.platform == post_platform,
                    Account.username == username,
                ).order_by(Account.created_at.asc())
            )
            account = acc_result.scalars().first()
            if not account:
                account = Account(
                    platform=post_platform,
                    username=username,
                    display_name=raw.get("author_display_name"),
                    bio=raw.get("bio"),
                    followers=raw.get("author_followers", 0),
                    avg_engagement_rate=raw.get("engagement_score", 0.0),
                    extra_metadata={},
                )
                db.add(account)
                await db.flush()
            else:
                if raw.get("author_display_name"):
                    account.display_name = raw["author_display_name"]
                if raw.get("bio") is not None:
                    account.bio = raw["bio"]
                if raw.get("author_followers") is not None:
                    account.followers = raw["author_followers"]
            account_id = account.id
            account_ids.add(account_id)

        statement = (
            pg_insert(NormalizedPost)
            .values(
                project_id=job.project_id,
                search_job_id=job.id,
                account_id=account_id,
                platform=post_platform,
                vendor=raw.get("vendor", "mock"),
                external_id=str(raw["external_id"]),
                url=raw.get("url"),
                body=raw.get("body", ""),
                author_username=raw.get("author_username"),
                author_display_name=raw.get("author_display_name"),
                author_followers=raw.get("author_followers", 0),
                likes=raw.get("likes", 0),
                shares=raw.get("shares", 0),
                comments=raw.get("comments", 0),
                views=raw.get("views", 0),
                engagement_score=raw.get("engagement_score", 0.0),
                sentiment=raw.get("sentiment", "neutral"),
                sentiment_score=raw.get("sentiment_score", 0.0),
                language=raw.get("language", "en"),
                hashtags=raw.get("hashtags", []),
                mentions=raw.get("mentions", []),
                media_urls=raw.get("media_urls", []),
                extra_metadata=raw.get("extra_metadata", {}),
                published_at=raw.get("published_at"),
            )
            .on_conflict_do_nothing(
                constraint="uq_normalized_post_project_platform_external_id"
            )
            .returning(NormalizedPost.id)
        )
        inserted_id = (await db.execute(statement)).scalar_one_or_none()
        if not inserted_id:
            inserted_id = (await db.execute(select(NormalizedPost.id).where(
                NormalizedPost.project_id == job.project_id, NormalizedPost.platform == post_platform,
                NormalizedPost.external_id == str(raw["external_id"])))).scalar_one()
        membership = (await db.execute(pg_insert(RunPost).values(job_id=job.id, post_id=inserted_id)
            .on_conflict_do_nothing().returning(RunPost.post_id))).scalar_one_or_none()
        if membership:
            inserted_count += 1
            pull_seen.add(identity)

    return inserted_count, tuple(account_ids)


@celery_app.task(bind=True)
def run_collection_job(self, job_id: str):
    """
    Collect platforms concurrently and persist each result as soon as it finishes.
    """
    logger.info(f"Starting collection job: {job_id}")

    async def _execute():
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
        from sqlalchemy import func, select
        from app.config import settings
        from app.models.search_job import SearchJob
        from app.models.query_version import QueryVersion
        from app.models.normalized_post import NormalizedPost
        from app.models.collection_pull import RunPost
        from app.services.budget_service import BudgetContext
        from app.adapters.router import vendor_router

        engine = create_async_engine(settings.DATABASE_URL, echo=False)
        SessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

        try:
            async with SessionLocal() as db:
                result = await db.execute(
                    select(SearchJob)
                    .where(SearchJob.id == uuid.UUID(job_id))
                    .with_for_update()
                )
                job = result.scalar_one_or_none()
                if not job:
                    logger.error("Collection job %s not found", job_id)
                    return {"status": "not_found"}
                if job.status == "cancelling":
                    cancelled_at = datetime.now(timezone.utc)
                    total_posts = (
                        await db.execute(
                            select(func.count(RunPost.post_id)).where(
                                RunPost.job_id == uuid.UUID(job_id)
                            )
                        )
                    ).scalar_one()
                    job.status = "cancelled"
                    job.cancelled_at = cancelled_at
                    job.completed_at = cancelled_at
                    job.total_posts_collected = total_posts
                    job.platform_states = finalize_platform_cancellation(
                        list(job.platforms or []),
                        dict(job.platform_states or {}),
                        cancelled_at=cancelled_at,
                    )
                    job.last_progress_at = cancelled_at
                    await db.commit()
                    return {
                        "status": "cancelled",
                        "total_posts": total_posts,
                    }
                if job.status not in {"pending", "queued"}:
                    logger.info(
                        "Ignoring collection task for non-startable job %s with status %s",
                        job_id,
                        job.status,
                    )
                    return {"status": job.status, "collection_not_started": True}

                if not job.pull_id or not 100 <= job.requested_post_count <= 5000:
                    job.status = "failed"
                    job.error_message = "Missing pull allowance or invalid post target; create a new collection."
                    await db.commit()
                    return {"status": "failed"}
                platforms = tuple(job.platforms)
                allocations = dict(job.platform_allocations or {})
                collection_started_at = datetime.now(timezone.utc)
                job.status = "running"
                job.started_at = collection_started_at
                job.completed_at = None
                job.error_message = None
                job.platform_states = {
                    platform: platform_state("pending") for platform in platforms
                }
                job.last_progress_at = collection_started_at
                await db.commit()

                qv_result = await db.execute(
                    select(QueryVersion).where(
                        QueryVersion.search_job_id == job.id,
                        QueryVersion.is_active == True,
                    ).order_by(QueryVersion.version_number.desc())
                )
                query_version = qv_result.scalar_one_or_none()
                query_string = query_version.boolean_query if query_version else "general"
                job_snapshot = job

                job.platform_states = {
                    platform: platform_state(
                        "running",
                        started_at=collection_started_at,
                        last_progress_at=collection_started_at,
                    )
                    for platform in platforms
                }
                await db.commit()

            if job_snapshot.mode == "collection":
                from sqlalchemy.dialects.postgresql import insert
                async with SessionLocal() as preview_db:
                    for platform in platforms:
                        previous = (await preview_db.execute(select(RunPost.post_id).distinct()
                            .join(SearchJob, SearchJob.id == RunPost.job_id)
                            .join(NormalizedPost, NormalizedPost.id == RunPost.post_id)
                            .where(SearchJob.pull_id == job_snapshot.pull_id, SearchJob.mode == "preview",
                                SearchJob.fingerprint == job_snapshot.fingerprint, NormalizedPost.platform == platform)
                            .limit(int(allocations.get(platform, 0))))).scalars().all()
                        for post_id in previous:
                            await preview_db.execute(insert(RunPost).values(job_id=job_snapshot.id, post_id=post_id).on_conflict_do_nothing())
                    await preview_db.commit()
            requests = tuple(
                PlatformCollectionRequest(
                    platform=platform,
                    query=query_string,
                    date_from=job_snapshot.date_from,
                    date_to=job_snapshot.date_to,
                    max_results=int(allocations.get(platform.lower(), 0)),
                    budget=BudgetContext(SessionLocal, job_snapshot.pull_id, job_snapshot.id,
                        platform, job_snapshot.mode, job_snapshot.fingerprint),
                )
                for platform in platforms
            )
            all_errors = []
            successful_platforms = 0
            async for platform_result in _iter_cancellable_platform_results(
                vendor_router,
                requests,
                SessionLocal,
                uuid.UUID(job_id),
                settings.COLLECTION_CANCELLATION_POLL_SECONDS,
            ):
                platform_completed_at = datetime.now(timezone.utc)
                if platform_result.status == "failed":
                    error = platform_result.error or "provider request failed"
                    all_errors.append(f"{platform_result.platform}: {error}")
                    async with SessionLocal() as platform_db:
                        job_result = await platform_db.execute(
                            select(SearchJob).where(
                                SearchJob.id == uuid.UUID(job_id)
                            ).with_for_update()
                        )
                        platform_job = job_result.scalar_one()
                        current_states = dict(platform_job.platform_states or {})
                        current_states[platform_result.platform] = platform_state(
                            "failed",
                            started_at=job_snapshot.started_at,
                            completed_at=platform_completed_at,
                            last_progress_at=platform_completed_at,
                            error=error,
                        )
                        platform_job.platform_states = current_states
                        platform_job.last_progress_at = platform_completed_at
                        platform_job.error_message = "; ".join(all_errors)
                        await platform_db.commit()
                    logger.error(
                        "Collection failed for %s: %s",
                        platform_result.platform,
                        error,
                    )
                    continue

                try:
                    platform_cancelled = platform_result.status == "cancelled"
                    requested_for_platform = int(allocations.get(platform_result.platform.lower(), 0))
                    queued_account_ids: list[uuid.UUID] = []
                    async with SessionLocal() as platform_db:
                        job_result = await platform_db.execute(
                            select(SearchJob).where(
                                SearchJob.id == uuid.UUID(job_id)
                            ).with_for_update()
                        )
                        platform_job = job_result.scalar_one()
                        (
                            inserted_count,
                            platform_account_ids,
                        ) = await _persist_platform_posts(
                            platform_db,
                            platform_job,
                            platform_result.platform,
                            platform_result.posts,
                        )
                        inserted_count = (await platform_db.execute(select(func.count(RunPost.post_id))
                            .join(NormalizedPost, NormalizedPost.id == RunPost.post_id).where(
                                RunPost.job_id == platform_job.id, NormalizedPost.platform == platform_result.platform))).scalar_one()
                        total_posts = (
                            await platform_db.execute(
                                select(func.count(RunPost.post_id)).where(
                                    RunPost.job_id == uuid.UUID(job_id)
                                )
                            )
                        ).scalar_one()
                        current_states = dict(platform_job.platform_states or {})
                        previous_state = dict(current_states.get(platform_result.platform) or {})
                        provider_stop_reason = previous_state.get("provider_stop_reason")
                        provider_stop_details = previous_state.get("provider_stop_details")
                        shortfall_error = None if platform_cancelled else _collection_shortfall_message(
                            len(platform_result.posts),
                            inserted_count,
                            requested_for_platform,
                            provider_stop_reason,
                        )
                        current_states[platform_result.platform] = platform_state(
                            "cancelled" if platform_cancelled else "completed",
                            posts_collected=inserted_count,
                            started_at=job_snapshot.started_at,
                            completed_at=platform_completed_at,
                            last_progress_at=platform_completed_at,
                            error="Cancelled by user" if platform_cancelled else shortfall_error,
                            provider_stop_reason=provider_stop_reason,
                            provider_stop_details=provider_stop_details,
                        )
                        platform_job.platform_states = current_states
                        platform_job.total_posts_collected = total_posts
                        platform_job.last_progress_at = platform_completed_at
                        await platform_db.commit()

                    if not platform_cancelled:
                        successful_platforms += 1
                        if shortfall_error:
                            all_errors.append(
                                f"{platform_result.platform}: {shortfall_error}"
                            )
                    logger.info(
                        "Platform collection persisted: platform=%s provider_posts=%s "
                        "new_posts_committed=%s duplicates_or_existing=%s status=%s",
                        platform_result.platform,
                        len(platform_result.posts),
                        inserted_count,
                        max(0, len(platform_result.posts) - inserted_count),
                        "cancelled" if platform_cancelled else "completed",
                    )
                except Exception as exc:
                    error = f"database write failed ({type(exc).__name__})"
                    all_errors.append(f"{platform_result.platform}: {error}")
                    async with SessionLocal() as failure_db:
                        job_result = await failure_db.execute(
                            select(SearchJob).where(
                                SearchJob.id == uuid.UUID(job_id)
                            ).with_for_update()
                        )
                        failed_job = job_result.scalar_one()
                        current_states = dict(failed_job.platform_states or {})
                        current_states[platform_result.platform] = platform_state(
                            "failed",
                            started_at=job_snapshot.started_at,
                            completed_at=platform_completed_at,
                            last_progress_at=platform_completed_at,
                            error=error,
                        )
                        failed_job.platform_states = current_states
                        failed_job.last_progress_at = platform_completed_at
                        failed_job.error_message = "; ".join(all_errors)
                        await failure_db.commit()
                    logger.exception(
                        "Database write failed for platform %s",
                        platform_result.platform,
                    )

            async with SessionLocal() as db:
                total_posts = (
                    await db.execute(
                        select(func.count(RunPost.post_id)).where(
                            RunPost.job_id == uuid.UUID(job_id)
                        )
                    )
                ).scalar_one()
                result = await db.execute(
                    select(SearchJob).where(SearchJob.id == uuid.UUID(job_id)).with_for_update()
                )
                job = result.scalar_one()
                job.total_posts_collected = total_posts
                cancellation_pending = job.status == "cancelling"
                terminal_at = datetime.now(timezone.utc)
                if cancellation_pending:
                    job.status = "cancelled"
                    job.cancelled_at = terminal_at
                    job.completed_at = terminal_at
                    job.platform_states = finalize_platform_cancellation(
                        list(job.platforms or []),
                        dict(job.platform_states or {}),
                        cancelled_at=terminal_at,
                    )
                    job.last_progress_at = terminal_at
                else:
                    job.status = collection_terminal_status(
                        total_posts,
                        all_errors,
                        successful_platforms=successful_platforms,
                    )
                    job.completed_at = terminal_at
                    job.error_message = "; ".join(all_errors) if all_errors else None
                    job.last_progress_at = job.completed_at
                await db.commit()

            logger.info(
                "Collection job %s finished with status %s and %s posts",
                job_id,
                job.status,
                total_posts,
            )
            return {"status": job.status, "total_posts": total_posts}
        finally:
            await engine.dispose()

    try:
        return _run_async(_execute())
    except Exception as exc:
        logger.error("Collection job %s failed (%s)", job_id, type(exc).__name__)
        async def _mark_failed():
            from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
            from sqlalchemy import select
            from app.config import settings
            from app.models.search_job import SearchJob

            engine = create_async_engine(settings.DATABASE_URL, echo=False)
            SessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
            marked_failed = False
            async with SessionLocal() as db:
                result = await db.execute(select(SearchJob).where(SearchJob.id == uuid.UUID(job_id)).with_for_update())
                job = result.scalar_one_or_none()
                if job and can_transition_job_status(job.status, "failed"):
                    job.status = "failed"
                    job.completed_at = datetime.now(timezone.utc)
                    job.last_progress_at = job.completed_at
                    job.error_message = f"Collection task failed ({type(exc).__name__})"
                    await db.commit()
                    marked_failed = True
            await engine.dispose()
            return marked_failed

        marked_failed = _run_async(_mark_failed())
        return {
            "status": "failed",
            "error": f"Collection task failed ({type(exc).__name__})",
        }


@celery_app.task
def normalize_posts(raw_posts: list, job_id: str, project_id: str):
    """Normalize and persist a batch of raw posts (called by run_collection_job internally)."""
    # This task is available for future use when batching is needed
    # Currently normalization happens inline in run_collection_job
    logger.info(f"normalize_posts called with {len(raw_posts)} posts for job {job_id}")
    return {"normalized": len(raw_posts)}
