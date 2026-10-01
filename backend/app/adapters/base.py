from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import datetime
from app.adapters.cancellation import CancellationSignal
from app.adapters.provider_progress import ProviderProgressTracker


class VendorAdapter(ABC):
    """Abstract base class for all social data vendor adapters."""

    @abstractmethod
    async def search(
        self,
        query: str,
        platform: str,
        date_from: Optional[datetime],
        date_to: Optional[datetime],
        max_results: int = 500,
        cancellation: Optional[CancellationSignal] = None,
        progress: Optional[ProviderProgressTracker] = None,
    ) -> List[dict]:
        """
        Search for posts matching the query on the given platform.

        Returns a list of normalized post dicts with at minimum:
        - external_id: str
        - platform: str
        - vendor: str
        - author_username: str
        - author_display_name: str
        - author_followers: int
        - body: str
        - url: str
        - published_at: datetime
        - likes: int
        - shares: int
        - comments: int
        - views: int
        - engagement_score: float
        - sentiment: str  # positive | neutral | negative | mixed
        - sentiment_score: float  # -1.0 to 1.0
        - hashtags: list[str]
        - mentions: list[str]
        - media_urls: list[str]
        - extra_metadata: dict
        """
        ...

    @abstractmethod
    def get_supported_platforms(self) -> List[str]:
        """Return list of platform names this adapter supports."""
        ...
