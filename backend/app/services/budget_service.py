"""Record provider usage and cache responses without enforcing credit caps.

Cancellation, post ceilings, and small preview samples still bound collection.
Usage estimates are bookkeeping, not deductions from an application allowance.
"""
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
import hashlib
import json
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert
from app.models.collection_pull import CollectionPull, ProviderUsage, ProviderCache, RunPost

COSTS = {
    "/twitter/search": 1, "/reddit/search": 1, "/youtube/search": 1,
    "/tiktok/search/keyword": 1, "/google/search": 1, "/facebook/group/posts": 1, "/facebook/profile/posts": 1,
}
PREVIEW_REQUESTS = {"facebook": 2, "instagram": 3}
FRESH_SECONDS = 900
MAX_PULL_POSTS = 5000
current_budget: ContextVar = ContextVar("collection_budget", default=None)
current_endpoint: ContextVar = ContextVar("provider_endpoint", default="sdk_operation")


class BudgetStopped(Exception):
    """Safe, displayable explanation. Never contains provider exception text."""


@dataclass
class BudgetContext:
    sessions: object
    pull_id: object
    job_id: object
    platform: str
    mode: str
    fingerprint: str
    stop_reason: str | None = None
    metrics: dict = field(default_factory=dict)

    def stop(self, reason):
        self.stop_reason = reason
        raise BudgetStopped(reason)

    async def reserve(self, provider, endpoint):
        cost = COSTS.get(endpoint, 0) if provider == "socialvault" else 0
        async with self.sessions() as db:
            # Serialize usage records with cancellation and pull lifecycle changes.
            await db.execute(select(CollectionPull).where(
                CollectionPull.id == self.pull_id).with_for_update())
            from app.models.search_job import SearchJob
            job = await db.get(SearchJob, self.job_id)
            if not job or job.status not in {"running", "queued", "pending"}:
                self.stop("cancelled_or_inactive: no further requests allowed")
            accepted = (await db.execute(select(func.count(func.distinct(RunPost.post_id)))
                .join(SearchJob, SearchJob.id == RunPost.job_id)
                .where(SearchJob.pull_id == self.pull_id))).scalar_one()
            if accepted >= MAX_PULL_POSTS:
                self.stop("post_limit: pull has reached 5000 unique posts including previews")
            if self.mode == "preview":
                attempts = (await db.execute(select(func.count(ProviderUsage.id)).where(
                    ProviderUsage.job_id == self.job_id,
                    ProviderUsage.platform == self.platform))).scalar_one()
                if attempts >= PREVIEW_REQUESTS.get(self.platform, 1):
                    self.stop("preview_limit: small search preview sample reached")
            usage = ProviderUsage(pull_id=self.pull_id, job_id=self.job_id,
                platform=self.platform, provider=provider, endpoint=endpoint, reserved=cost)
            db.add(usage)
            await db.commit()  # Durable before any network operation.
            return usage.id

    async def settle(self, usage_id, result=None, unknown=False):
        async with self.sessions() as db:
            row = (await db.execute(select(ProviderUsage).where(
                ProviderUsage.id == usage_id).with_for_update())).scalar_one()
            row.state = "unknown" if unknown or row.provider == "xpoz" else "estimated"
            row.estimated = row.reserved if row.provider == "socialvault" and not unknown else None
            try:
                payload = result.json()
                reported = payload.get("credits_used")
                if isinstance(reported, int) and not isinstance(reported, bool) and reported >= 0:
                    row.reported = reported
                    row.state = "reported"
            except (AttributeError, ValueError, TypeError):
                pass
            await db.commit()

    async def execute(self, provider, endpoint, operation):
        usage_id = await self.reserve(provider, endpoint)
        try:
            result = await operation()
        except BaseException:
            await self.settle(usage_id, unknown=True)
            raise
        await self.settle(usage_id, result=result)
        return result

    def cache_key(self, endpoint, params):
        return hashlib.sha256(json.dumps([self.fingerprint, self.platform, endpoint, params],
            sort_keys=True, default=str).encode()).hexdigest()

    async def cached(self, key):
        async with self.sessions() as db:
            row = await db.get(ProviderCache, (self.pull_id, key))
            if row and (row.created_at.replace(tzinfo=timezone.utc) if row.created_at.tzinfo is None else row.created_at) >= datetime.now(timezone.utc) - timedelta(seconds=FRESH_SECONDS):
                return row.payload
        return None

    async def cache(self, key, payload):
        async with self.sessions() as db:
            await db.execute(insert(ProviderCache).values(pull_id=self.pull_id, key=key,
                payload=payload).on_conflict_do_update(index_elements=["pull_id", "key"],
                set_={"payload": payload, "created_at": datetime.now(timezone.utc)}))
            await db.commit()


async def usage_summary(db, pull):
    rows = (await db.execute(select(ProviderUsage).where(ProviderUsage.pull_id == pull.id))).scalars().all()
    by_platform = {}
    for platform in pull.platforms:
        own = [r for r in rows if r.platform == platform]
        by_platform[platform] = {
            "requests": len(own), "reserved": sum(r.reserved for r in own if r.state == "reserved"),
            "estimated": sum(r.estimated or 0 for r in own if r.state == "estimated"),
            "reported": sum(r.reported or 0 for r in own),
            "unknown_requests": sum(r.state in {"reserved", "unknown"} for r in own),
        }
    return {"pull_id": str(pull.id), "credit_cap": None, "platforms": by_platform,
        "scope": "Usage is recorded for this pull; SocialScope does not enforce a credit cap."}
