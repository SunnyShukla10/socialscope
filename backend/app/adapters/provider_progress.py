import logging
import time
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional


logger = logging.getLogger(__name__)
ProgressCallback = Callable[[dict], Awaitable[None]]


@dataclass(frozen=True)
class ProviderPageStats:
    raw_items: int
    accepted_items: int
    duplicate_items: int = 0
    filtered_items: int = 0
    malformed_items: int = 0
    has_continuation: bool = False
    credits_used: Optional[int] = None

    @property
    def cursor_only(self) -> bool:
        return self.raw_items == 0 and self.has_continuation


@dataclass(frozen=True)
class PaginationDecision:
    should_continue: bool
    stop_reason: Optional[str] = None


def evaluate_provider_page(
    *, stats: ProviderPageStats, consecutive_no_progress_pages: int,
    continuation_repeated: bool, collected_posts: int, requested_posts: int,
) -> PaginationDecision:
    if collected_posts >= requested_posts:
        return PaginationDecision(False, "requested_limit_reached")
    if not stats.has_continuation:
        return PaginationDecision(False, "provider_exhausted")
    if continuation_repeated:
        return PaginationDecision(False, "repeated_cursor")
    if stats.raw_items == 0:
        return PaginationDecision(False, "empty_page_with_continuation")
    if consecutive_no_progress_pages >= 3:
        return PaginationDecision(False, "consecutive_filtered_pages")
    return PaginationDecision(True)


class PaginationSafeguardReached(Exception):
    """Base class for a safe, intentional stop to provider pagination."""


class ProviderNoProgressTimeout(PaginationSafeguardReached):
    pass


class ProviderMaximumPagesReached(PaginationSafeguardReached):
    pass


class ProviderRepeatedCursor(PaginationSafeguardReached):
    pass


class ProviderProgressTracker:
    """Per-platform page, cursor, and meaningful-progress safeguards."""

    def __init__(
        self,
        *,
        provider: str,
        no_progress_timeout_seconds: float,
        max_pages: int,
        on_progress: Optional[ProgressCallback] = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.provider = provider
        self.no_progress_timeout_seconds = no_progress_timeout_seconds
        self.max_pages = max_pages
        self._on_progress = on_progress
        self._clock = clock
        self._last_progress = clock()
        self._requests_started = 0
        self._seen_cursors: set[str] = set()

    @property
    def requests_started(self) -> int:
        return self._requests_started

    async def before_request(self) -> None:
        elapsed = self._clock() - self._last_progress
        if elapsed > self.no_progress_timeout_seconds:
            raise ProviderNoProgressTimeout(
                f"{self.provider} made no progress within the configured timeout"
            )
        if self._requests_started >= self.max_pages:
            raise ProviderMaximumPagesReached(
                f"{self.provider} reached the configured maximum pages"
            )
        self._requests_started += 1

    async def page_received(
        self,
        *,
        new_posts: int,
        cursor: object = None,
    ) -> None:
        if cursor is not None:
            cursor_key = str(cursor)
            if cursor_key in self._seen_cursors:
                raise ProviderRepeatedCursor(
                    f"{self.provider} returned a repeated pagination cursor"
                )
            self._seen_cursors.add(cursor_key)

        self._last_progress = self._clock()
        if not self._on_progress:
            return
        try:
            await self._on_progress(
                {
                    "requests_started": self._requests_started,
                    "new_posts": max(0, int(new_posts)),
                }
            )
        except Exception as exc:
            logger.warning(
                "Could not persist %s provider progress (%s)",
                self.provider,
                type(exc).__name__,
            )

    async def record_stop(self, *, reason: str, details: Optional[dict] = None) -> None:
        if not self._on_progress:
            return
        try:
            await self._on_progress({"stop_reason": reason, "stop_details": details or {}})
        except Exception as exc:
            logger.warning(
                "Could not persist %s provider stop (%s)",
                self.provider,
                type(exc).__name__,
            )
