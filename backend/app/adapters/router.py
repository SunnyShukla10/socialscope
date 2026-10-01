from typing import Awaitable, Callable, List, Optional
from datetime import datetime
from app.adapters.base import VendorAdapter
from app.adapters.xpoz_adapter import XpozAdapter
from app.adapters.socialvault_adapter import SocialVaultAdapter
from app.adapters.provider_limits import safe_provider_error
from app.adapters.cancellation import CancellationSignal, CollectionCancelled
from app.adapters.provider_progress import ProviderProgressTracker
from app.config import settings
from app.platforms import PLATFORM_PROVIDERS
import logging

logger = logging.getLogger(__name__)

# Platform → primary vendor mapping
PLATFORM_VENDOR_MAP = {
    platform: provider
    for platform, provider in PLATFORM_PROVIDERS.items()
    if platform != "x"
}


def _provider_for_platform(platform: str) -> str:
    normalized_platform = platform.lower()
    return PLATFORM_VENDOR_MAP.get(
        normalized_platform,
        PLATFORM_PROVIDERS.get(normalized_platform, "xpoz"),
    )


class VendorRouter:
    """Routes platform search requests to the appropriate vendor adapter."""

    def __init__(self):
        self._xpoz = XpozAdapter()
        self._socialvault = SocialVaultAdapter()

    def _get_adapter(self, vendor: str) -> VendorAdapter:
        """Get the real adapter for a vendor."""
        if vendor == "xpoz":
            return self._xpoz
        elif vendor == "socialvault":
            return self._socialvault
        else:
            return self._xpoz

    async def search(
        self,
        query: str,
        platform: str,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        max_results: int = 500,
        cancellation: Optional[CancellationSignal] = None,
        progress_callback: Optional[Callable[[str, dict], Awaitable[None]]] = None,
    ) -> List[dict]:
        """Search a platform using the appropriate vendor."""
        vendor = _provider_for_platform(platform)
        adapter = self._get_adapter(vendor)
        provider_progress_callback = None
        if progress_callback is not None:
            async def provider_progress_callback(event: dict) -> None:
                await progress_callback(platform.lower(), event)

        if vendor == "xpoz":
            progress = ProviderProgressTracker(
                provider=vendor,
                no_progress_timeout_seconds=settings.XPOZ_NO_PROGRESS_TIMEOUT_SECONDS,
                max_pages=settings.XPOZ_MAX_PAGES,
                on_progress=provider_progress_callback,
            )
        else:
            progress = ProviderProgressTracker(
                provider=vendor,
                no_progress_timeout_seconds=settings.SOCIALVAULT_NO_PROGRESS_TIMEOUT_SECONDS,
                max_pages=settings.SOCIALVAULT_MAX_PAGES,
                on_progress=provider_progress_callback,
            )

        try:
            search_kwargs = {
                "query": query,
                "platform": platform,
                "date_from": date_from,
                "date_to": date_to,
                "max_results": max_results,
            }
            if cancellation is not None:
                search_kwargs["cancellation"] = cancellation
            search_kwargs["progress"] = progress
            return await adapter.search(
                **search_kwargs,
            )
        except CollectionCancelled:
            raise
        except Exception as exc:
            logger.error(
                "Primary adapter failed for %s: %s",
                platform,
                safe_provider_error(vendor, exc),
            )
            raise

    def get_vendor_for_platform(self, platform: str) -> str:
        return _provider_for_platform(platform)

    def get_all_platforms(self) -> List[str]:
        return list(PLATFORM_VENDOR_MAP.keys())


# Singleton instance
vendor_router = VendorRouter()
