import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import AsyncIterator, Awaitable, Callable, Optional, Sequence

from app.adapters.cancellation import CancellationSignal, CollectionCancelled
from app.adapters.provider_limits import safe_provider_error


@dataclass(frozen=True)
class PlatformCollectionRequest:
    platform: str
    query: str
    date_from: Optional[datetime]
    date_to: Optional[datetime]
    max_results: int
    budget: object = None


@dataclass(frozen=True)
class PlatformCollectionResult:
    platform: str
    status: str
    posts: tuple[dict, ...] = ()
    error: Optional[str] = None


async def _collect_one(
    router,
    request: PlatformCollectionRequest,
    cancellation: Optional[CancellationSignal] = None,
    progress_callback: Optional[Callable[[str, dict], Awaitable[None]]] = None,
) -> PlatformCollectionResult:
    from app.services.budget_service import current_budget, BudgetStopped
    token = current_budget.set(request.budget)
    try:
        if request.max_results <= 0:
            return PlatformCollectionResult(platform=request.platform, status="completed")
        if request.budget:
            from app.config import settings
            provider = router.get_vendor_for_platform(request.platform)
            configured = settings.XPOZ_API_KEY if provider == "xpoz" else settings.SOCIALVAULT_API_KEY
            if not configured:
                return PlatformCollectionResult(platform=request.platform, status="failed", error="missing_credentials: configure the provider key in .env")
        search_kwargs = {
            "query": request.query,
            "platform": request.platform,
            "date_from": request.date_from,
            "date_to": request.date_to,
            "max_results": request.max_results,
        }
        if cancellation is not None:
            search_kwargs["cancellation"] = cancellation
        if progress_callback is not None:
            search_kwargs["progress_callback"] = progress_callback
        posts = await router.search(
            **search_kwargs,
        )
        if request.budget and progress_callback:
            dates = sorted(str(p["published_at"]) for p in posts if p.get("published_at"))
            details = {**request.budget.metrics, "publication_min": dates[0] if dates else None,
                "publication_max": dates[-1] if dates else None, "returned_unique": len(posts)}
            await progress_callback(request.platform, {"stop_reason": request.budget.stop_reason,
                "stop_details": details})
        if cancellation and cancellation.is_cancelled:
            return PlatformCollectionResult(
                platform=request.platform,
                status="cancelled",
                posts=tuple(posts),
            )
        return PlatformCollectionResult(
            platform=request.platform,
            status="completed",
            posts=tuple(posts),
        )
    except BudgetStopped as exc:
        if progress_callback:
            await progress_callback(request.platform, {"stop_reason": str(exc)})
        return PlatformCollectionResult(platform=request.platform, status="completed", error=str(exc))
    except CollectionCancelled:
        return PlatformCollectionResult(
            platform=request.platform,
            status="cancelled",
        )
    except Exception as exc:
        provider = router.get_vendor_for_platform(request.platform)
        return PlatformCollectionResult(
            platform=request.platform,
            status="failed",
            error=safe_provider_error(provider, exc),
        )
    finally:
        current_budget.reset(token)


async def collect_platforms(
    router,
    requests: Sequence[PlatformCollectionRequest],
    cancellation: Optional[CancellationSignal] = None,
    progress_callback: Optional[Callable[[str, dict], Awaitable[None]]] = None,
) -> tuple[PlatformCollectionResult, ...]:
    """Compatibility helper that returns all results in completion order."""
    results = [
        result
        async for result in iter_platform_results(
            router,
            requests,
            cancellation,
            progress_callback,
        )
    ]
    return tuple(results)


async def iter_platform_results(
    router,
    requests: Sequence[PlatformCollectionRequest],
    cancellation: Optional[CancellationSignal] = None,
    progress_callback: Optional[Callable[[str, dict], Awaitable[None]]] = None,
) -> AsyncIterator[PlatformCollectionResult]:
    """Yield isolated platform results as soon as each collector finishes."""
    tasks = [
        asyncio.create_task(
            _collect_one(
                router,
                request,
                cancellation,
                progress_callback,
            )
        )
        for request in requests
    ]
    try:
        for completed in asyncio.as_completed(tasks):
            yield await completed
    finally:
        unfinished = [task for task in tasks if not task.done()]
        for task in unfinished:
            task.cancel()
        if unfinished:
            await asyncio.gather(*unfinished, return_exceptions=True)
