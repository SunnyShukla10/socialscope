import asyncio
import logging
import re
import time
import httpx
from collections import deque
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Awaitable, Callable, Optional, TypeVar

from app.config import settings
from app.adapters.cancellation import CancellationSignal, CollectionCancelled

logger = logging.getLogger(__name__)
T = TypeVar("T")


class ProviderRetrySafeguardError(Exception):
    """Sanitized provider failure raised when a configured retry guard trips."""

    def __init__(self, provider: str, status_code: Optional[int], reason: str):
        super().__init__(f"{provider} {reason}")
        self.status_code = status_code


class ProviderRepeated502Error(ProviderRetrySafeguardError):
    pass


class ProviderRetryBudgetExceeded(ProviderRetrySafeguardError):
    pass


class SlidingWindowRateLimiter:
    """Process-local sliding-window limiter used by all requests for a provider."""

    def __init__(
        self,
        max_requests: int,
        period_seconds: float,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ):
        self.max_requests = max_requests
        self.period_seconds = period_seconds
        self._clock = clock
        self._sleep = sleeper
        self._timestamps: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(
        self,
        cancellation: Optional[CancellationSignal] = None,
    ) -> None:
        while True:
            if cancellation:
                cancellation.raise_if_cancelled()
            async with self._lock:
                now = self._clock()
                cutoff = now - self.period_seconds
                while self._timestamps and self._timestamps[0] <= cutoff:
                    self._timestamps.popleft()

                if len(self._timestamps) < self.max_requests:
                    self._timestamps.append(now)
                    return

                wait_seconds = max(
                    0.0,
                    self.period_seconds - (now - self._timestamps[0]),
                )
            if cancellation:
                await cancellation.run(self._sleep(wait_seconds))
            else:
                await self._sleep(wait_seconds)


def _status_code(exc: Exception) -> Optional[int]:
    response = getattr(exc, "response", None)
    response_status = getattr(response, "status_code", None)
    direct_status = getattr(exc, "status_code", None)
    if isinstance(response_status, int):
        return response_status
    if isinstance(direct_status, int):
        return direct_status
    match = re.search(r"\b(429|5\d\d)\b", str(exc))
    return int(match.group(1)) if match else None


def _retry_after_seconds(exc: Exception) -> Optional[float]:
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", {}) or {}
    value = headers.get("Retry-After") or headers.get("retry-after")
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        try:
            retry_at = parsedate_to_datetime(value)
            if retry_at.tzinfo is None:
                retry_at = retry_at.replace(tzinfo=timezone.utc)
            return max(0.0, (retry_at - datetime.now(timezone.utc)).total_seconds())
        except (TypeError, ValueError, OverflowError):
            return None


def _is_retryable(
    exc: Exception,
    additional_status_codes: frozenset[int] = frozenset(),
) -> bool:
    if isinstance(exc, httpx.TransportError):
        return True
    status_code = _status_code(exc)
    return (
        status_code in additional_status_codes
        or status_code == 429
        or bool(status_code and 500 <= status_code <= 599)
    )


def safe_provider_error(provider: str, exc: Exception) -> str:
    """Return useful provider context without request bodies, headers, or credentials."""
    status_code = _status_code(exc)
    error_name = type(exc).__name__
    if status_code:
        return f"{provider} request failed with HTTP {status_code} ({error_name})"
    return f"{provider} request failed ({error_name})"


class ProviderRequestController:
    """Shared provider concurrency, optional rate limiting, and transient retries."""

    def __init__(
        self,
        provider: str,
        max_concurrency: int,
        rate_limiter: Optional[SlidingWindowRateLimiter] = None,
        *,
        max_retries: int = 3,
        retry_base_seconds: float = 1.0,
        retry_max_seconds: float = 30.0,
        retry_time_budget_seconds: Optional[float] = None,
        max_repeated_502: Optional[int] = None,
        operation_timeout_seconds: Optional[float] = None,
        sleeper: Callable[[float], Awaitable[None]] = asyncio.sleep,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.provider = provider
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._rate_limiter = rate_limiter
        self._max_retries = max_retries
        self._retry_base_seconds = retry_base_seconds
        self._retry_max_seconds = retry_max_seconds
        self._retry_time_budget_seconds = retry_time_budget_seconds
        self._max_repeated_502 = max_repeated_502
        self._operation_timeout_seconds = operation_timeout_seconds
        self._sleep = sleeper
        self._clock = clock

    async def run_async(
        self,
        operation: Callable[[], Awaitable[T]],
        cancellation: Optional[CancellationSignal] = None,
        *,
        additional_retry_status_codes: frozenset[int] = frozenset(),
        additional_status_max_retries: Optional[int] = None,
    ) -> T:
        return await self._run(
            operation,
            cancellation,
            additional_retry_status_codes=additional_retry_status_codes,
            additional_status_max_retries=additional_status_max_retries,
        )

    async def run_sync(
        self,
        operation: Callable[[], T],
        cancellation: Optional[CancellationSignal] = None,
    ) -> T:
        return await self._run(lambda: asyncio.to_thread(operation), cancellation)

    async def _run(
        self,
        operation: Callable[[], Awaitable[T]],
        cancellation: Optional[CancellationSignal],
        *,
        additional_retry_status_codes: frozenset[int] = frozenset(),
        additional_status_max_retries: Optional[int] = None,
    ) -> T:
        retry_time_spent = 0.0
        retry_started_at: Optional[float] = None
        repeated_502_failures = 0
        max_retries = self._max_retries
        for attempt in range(max_retries + 1):
            if cancellation:
                cancellation.raise_if_cancelled()
            if self._rate_limiter:
                await self._rate_limiter.acquire(cancellation)

            semaphore_acquired = False
            try:
                if cancellation:
                    await cancellation.run(self._semaphore.acquire())
                else:
                    await self._semaphore.acquire()
                semaphore_acquired = True

                if cancellation:
                    cancellation.raise_if_cancelled()
                from app.services.budget_service import current_budget, current_endpoint
                budget = current_budget.get()
                request = budget.execute(self.provider, current_endpoint.get(), operation) if budget else operation()
                if self._operation_timeout_seconds:
                    request = asyncio.wait_for(
                        request,
                        timeout=self._operation_timeout_seconds,
                    )
                if cancellation:
                    return await cancellation.run(request)
                return await request
            except CollectionCancelled:
                raise
            except Exception as exc:
                if cancellation:
                    cancellation.raise_if_cancelled()
                status_code = _status_code(exc)
                if status_code == 502:
                    repeated_502_failures += 1
                else:
                    repeated_502_failures = 0
                if (
                    self._max_repeated_502 is not None
                    and repeated_502_failures >= self._max_repeated_502
                ):
                    logger.warning(
                        "%s stopped after %s repeated HTTP 502 failures",
                        self.provider,
                        repeated_502_failures,
                    )
                    raise ProviderRepeated502Error(
                        self.provider,
                        status_code,
                        "repeated HTTP 502 safeguard reached",
                    ) from exc
                additional_retry_exhausted = (
                    status_code in additional_retry_status_codes
                    and additional_status_max_retries is not None
                    and attempt >= additional_status_max_retries
                )
                if additional_retry_exhausted or attempt >= max_retries or not _is_retryable(
                    exc,
                    additional_retry_status_codes,
                ):
                    raise

                retry_after = _retry_after_seconds(exc)
                exponential_delay = min(
                    self._retry_max_seconds,
                    self._retry_base_seconds * (2**attempt),
                )
                delay = retry_after if retry_after is not None else exponential_delay
                if retry_started_at is None:
                    retry_started_at = self._clock()
                retry_elapsed = max(
                    retry_time_spent,
                    self._clock() - retry_started_at,
                )
                if (
                    self._retry_time_budget_seconds is not None
                    and retry_elapsed + delay > self._retry_time_budget_seconds
                ):
                    logger.warning(
                        "%s retry time budget exhausted after %.2fs",
                        self.provider,
                        retry_elapsed,
                    )
                    raise ProviderRetryBudgetExceeded(
                        self.provider,
                        status_code,
                        "retry time budget exhausted",
                    ) from exc
                retry_time_spent += delay
                logger.warning(
                    "%s transient request failure; retrying in %.2fs (attempt %s/%s): %s",
                    self.provider,
                    delay,
                    attempt + 1,
                    max_retries,
                    safe_provider_error(self.provider, exc),
                )
                if cancellation:
                    await cancellation.run(self._sleep(delay))
                else:
                    await self._sleep(delay)
            finally:
                if semaphore_acquired:
                    self._semaphore.release()

        raise RuntimeError("unreachable")


xpoz_request_controller = ProviderRequestController(
    provider="xpoz",
    max_concurrency=settings.XPOZ_MAX_CONCURRENCY,
    rate_limiter=SlidingWindowRateLimiter(
        settings.XPOZ_REQUESTS_PER_PERIOD,
        settings.XPOZ_RATE_PERIOD_SECONDS,
    ),
    max_retries=settings.PROVIDER_MAX_RETRIES,
    retry_base_seconds=settings.PROVIDER_RETRY_BASE_SECONDS,
    retry_max_seconds=settings.PROVIDER_RETRY_MAX_SECONDS,
    retry_time_budget_seconds=settings.XPOZ_RETRY_TIME_BUDGET_SECONDS,
    max_repeated_502=settings.XPOZ_MAX_REPEATED_502,
    operation_timeout_seconds=settings.XPOZ_OPERATION_TIMEOUT_SECONDS,
)

socialvault_request_controller = ProviderRequestController(
    provider="socialvault",
    max_concurrency=settings.SOCIALVAULT_MAX_CONCURRENCY,
    rate_limiter=SlidingWindowRateLimiter(
        settings.SOCIALVAULT_REQUESTS_PER_PERIOD,
        settings.SOCIALVAULT_RATE_PERIOD_SECONDS,
    ),
    max_retries=settings.PROVIDER_MAX_RETRIES,
    retry_base_seconds=settings.PROVIDER_RETRY_BASE_SECONDS,
    retry_max_seconds=settings.PROVIDER_RETRY_MAX_SECONDS,
    retry_time_budget_seconds=settings.SOCIALVAULT_RETRY_TIME_BUDGET_SECONDS,
    max_repeated_502=settings.SOCIALVAULT_MAX_REPEATED_502,
)
