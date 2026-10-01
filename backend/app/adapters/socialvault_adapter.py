import random
import hashlib
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional
from urllib.parse import urlparse, urlunparse
import httpx
from app.adapters.base import VendorAdapter
from app.adapters.cancellation import CancellationSignal, CollectionCancelled
from app.adapters.provider_limits import safe_provider_error, socialvault_request_controller
from app.adapters.provider_progress import (
    ProviderPageStats,
    PaginationSafeguardReached,
    ProviderProgressTracker,
    evaluate_provider_page,
)
from app.config import settings
from app.adapters.xpoz_adapter import (
    _power_law_int, _seeded_choice, _pick_sentiment, _random_timestamp,
    _generate_twitter_post, DISPLAY_NAMES, MIGRAINE_POSTS, EV_POSTS, REDDIT_USERS
)

logger = logging.getLogger(__name__)

TIKTOK_USERNAMES = [
    "migraine.journey.official", "ubrelvy.experience", "chronic.headache.life",
    "neurology.nurse.tiktok", "headache.hacks.daily", "ev.life.content",
    "charging.station.tips", "electric.car.owner", "sustainable.commuter",
    "clean.energy.creator", "zero.emissions.tok", "health.advocate.tiktok",
    "patient.story.series", "pharma.facts.daily", "brain.health.creator",
]

YOUTUBE_CHANNELS = [
    "MigraineWarriorTV", "ChronicPainChannel", "NeurologyNow", "HealthAdvocateYT",
    "HeadacheRelief101", "EVChargingGuide", "ElectricCarLife", "SustainableTransport",
    "ZeroEmissionsJourney", "CleanEnergyChannel", "PharmacyTalkDaily",
    "PatientPowerYouTube", "MedicalExplained", "EVRoadTripperYT", "ChargingNetworkReview",
]

FACEBOOK_USERS = [
    "Sarah Johnson Mitchell", "Michael Chen Davis", "Emily Rodriguez",
    "David Thompson", "Jennifer Williams Baker", "Robert Kim",
    "Amanda Foster Clark", "Christopher Lee Martinez", "Melissa Turner",
    "James Wilson Hughes", "Patricia Moore Evans", "Thomas Anderson",
    "Linda Brown Scott", "Charles Harris", "Barbara Jackson Taylor",
]

PINTEREST_USERS = [
    "wellness_by_elena", "migraine_management_tips", "chronic_health_board",
    "ev_lifestyle_pins", "sustainable_transport_ideas", "clean_commute_boards",
    "healthy_living_pins", "patient_resources_board", "neurology_health_tips",
    "electric_vehicle_diy", "home_charging_setup", "green_car_ideas",
]


def _generate_tiktok_post(query: str, idx: int, date_from, date_to) -> dict:
    seed = f"tiktok_{query}_{idx}"
    username = _seeded_choice(seed + "u", TIKTOK_USERNAMES)
    display = _seeded_choice(seed + "d", DISPLAY_NAMES)
    followers = _power_law_int(100, 500000, exponent=3)

    is_ev = any(w in query.lower() for w in ["ev", "electric", "charging", "tesla"])
    body = _seeded_choice(seed + "body", EV_POSTS if is_ev else MIGRAINE_POSTS)
    body = body + " #fyp #foryoupage"

    views = _power_law_int(500, 2000000, exponent=3)
    likes = _power_law_int(10, int(views * 0.12), exponent=2)
    comments = _power_law_int(0, int(likes * 0.08) + 1, exponent=2)
    shares = _power_law_int(0, int(likes * 0.06) + 1, exponent=2)
    engagement = round((likes + comments * 2 + shares * 3) / max(views, 1) * 100, 4)
    sentiment, score = _pick_sentiment()
    published_at = _random_timestamp(date_from, date_to)
    vid_id = hashlib.md5(seed.encode()).hexdigest()[:18]

    hashtags = ["#fyp", "#foryoupage"]
    if is_ev:
        hashtags += random.sample(["#ev", "#electriccar", "#evcharging", "#tesla",
                                    "#sustainability", "#greenlife"], k=random.randint(2, 4))
    else:
        hashtags += random.sample(["#migraine", "#chronicpain", "#invisibleillness",
                                    "#healthtok", "#migrainewarrior"], k=random.randint(2, 4))

    return {
        "external_id": f"tt_{vid_id}",
        "platform": "tiktok",
        "vendor": "socialvault",
        "author_username": username,
        "author_display_name": display,
        "author_followers": followers,
        "bio": f"TikTok creator | {followers:,} followers",
        "body": body,
        "url": f"https://www.tiktok.com/@{username}/video/{random.randint(10**18, 10**19)}",
        "published_at": published_at,
        "likes": likes,
        "shares": shares,
        "comments": comments,
        "views": views,
        "engagement_score": engagement,
        "sentiment": sentiment,
        "sentiment_score": score,
        "hashtags": hashtags,
        "mentions": [],
        "media_urls": [f"https://cdn.tiktok.com/video/{vid_id}.mp4"],
        "language": "en",
        "extra_metadata": {"video_duration_seconds": random.randint(15, 180)},
    }


def _generate_youtube_post(query: str, idx: int, date_from, date_to) -> dict:
    seed = f"youtube_{query}_{idx}"
    channel = _seeded_choice(seed + "u", YOUTUBE_CHANNELS)
    subscribers = _power_law_int(500, 800000, exponent=3)

    is_ev = any(w in query.lower() for w in ["ev", "electric", "charging", "tesla"])
    body = _seeded_choice(seed + "body", EV_POSTS if is_ev else MIGRAINE_POSTS)
    title = body[:80] + ("..." if len(body) > 80 else "")

    views = _power_law_int(100, 500000, exponent=3)
    likes = _power_law_int(5, int(views * 0.06), exponent=2)
    comments = _power_law_int(0, int(likes * 0.2) + 1, exponent=2)
    engagement = round((likes + comments * 3) / max(views, 1) * 100, 4)
    sentiment, score = _pick_sentiment()
    published_at = _random_timestamp(date_from, date_to)
    vid_id = hashlib.md5(seed.encode()).hexdigest()[:11]

    return {
        "external_id": f"yt_{vid_id}",
        "platform": "youtube",
        "vendor": "socialvault",
        "author_username": channel.lower().replace(" ", "_"),
        "author_display_name": channel,
        "author_followers": subscribers,
        "bio": f"YouTube channel | {subscribers:,} subscribers",
        "body": body,
        "url": f"https://www.youtube.com/watch?v={vid_id}",
        "published_at": published_at,
        "likes": likes,
        "shares": 0,
        "comments": comments,
        "views": views,
        "engagement_score": engagement,
        "sentiment": sentiment,
        "sentiment_score": score,
        "hashtags": [],
        "mentions": [],
        "media_urls": [f"https://img.youtube.com/vi/{vid_id}/maxresdefault.jpg"],
        "language": "en",
        "extra_metadata": {"video_title": title, "video_duration_seconds": random.randint(180, 1800)},
    }


def _generate_facebook_post(query: str, idx: int, date_from, date_to) -> dict:
    seed = f"facebook_{query}_{idx}"
    username = _seeded_choice(seed + "u", FACEBOOK_USERS)
    friends = _power_law_int(50, 2000, exponent=2)

    is_ev = any(w in query.lower() for w in ["ev", "electric", "charging", "tesla"])
    body = _seeded_choice(seed + "body", EV_POSTS if is_ev else MIGRAINE_POSTS)

    likes = _power_law_int(1, 500, exponent=3)
    comments = _power_law_int(0, int(likes * 0.3) + 1, exponent=2)
    shares = _power_law_int(0, int(likes * 0.2) + 1, exponent=2)
    engagement = round((likes + comments * 2 + shares * 3) / max(friends, 1) * 100, 4)
    sentiment, score = _pick_sentiment()
    published_at = _random_timestamp(date_from, date_to)
    post_id = hashlib.md5(seed.encode()).hexdigest()[:15]

    return {
        "external_id": f"fb_{post_id}",
        "platform": "facebook",
        "vendor": "socialvault",
        "author_username": username.lower().replace(" ", "."),
        "author_display_name": username,
        "author_followers": friends,
        "bio": None,
        "body": body,
        "url": f"https://www.facebook.com/posts/{post_id}",
        "published_at": published_at,
        "likes": likes,
        "shares": shares,
        "comments": comments,
        "views": 0,
        "engagement_score": engagement,
        "sentiment": sentiment,
        "sentiment_score": score,
        "hashtags": [],
        "mentions": [],
        "media_urls": [],
        "language": "en",
        "extra_metadata": {"privacy": "public"},
    }


def _generate_pinterest_post(query: str, idx: int, date_from, date_to) -> dict:
    seed = f"pinterest_{query}_{idx}"
    username = _seeded_choice(seed + "u", PINTEREST_USERS)
    followers = _power_law_int(100, 50000, exponent=3)

    is_ev = any(w in query.lower() for w in ["ev", "electric", "charging", "tesla"])
    body = _seeded_choice(seed + "body", EV_POSTS if is_ev else MIGRAINE_POSTS)

    likes = _power_law_int(1, 1000, exponent=3)
    shares = _power_law_int(0, int(likes * 0.5) + 1, exponent=2)
    engagement = round((likes + shares * 2) / max(followers, 1) * 100, 4)
    sentiment, score = _pick_sentiment()
    published_at = _random_timestamp(date_from, date_to)
    pin_id = hashlib.md5(seed.encode()).hexdigest()[:12]

    return {
        "external_id": f"pi_{pin_id}",
        "platform": "pinterest",
        "vendor": "socialvault",
        "author_username": username,
        "author_display_name": username.replace("_", " ").title(),
        "author_followers": followers,
        "bio": None,
        "body": body,
        "url": f"https://www.pinterest.com/pin/{random.randint(10**17, 10**18)}/",
        "published_at": published_at,
        "likes": likes,
        "shares": shares,
        "comments": 0,
        "views": _power_law_int(likes * 5, likes * 50, exponent=1.2),
        "engagement_score": engagement,
        "sentiment": sentiment,
        "sentiment_score": score,
        "hashtags": [],
        "mentions": [],
        "media_urls": [f"https://i.pinimg.com/originals/{pin_id}.jpg"],
        "language": "en",
        "extra_metadata": {"board": "Health Tips" if not is_ev else "EV Lifestyle"},
    }


def _generate_reddit_post(query: str, idx: int, date_from, date_to) -> dict:
    seed = f"reddit_{query}_{idx}"
    username = _seeded_choice(seed + "u", REDDIT_USERS)

    is_ev = any(w in query.lower() for w in ["ev", "electric", "charging", "tesla"])
    body = _seeded_choice(seed + "body", EV_POSTS if is_ev else MIGRAINE_POSTS)
    subreddit = _seeded_choice(
        seed + "sub",
        ["r/electricvehicles", "r/EVCharging"] if is_ev else ["r/MyastheniaGravis", "r/ChronicIllness"],
    )
    upvotes = _power_law_int(1, 3000, exponent=3)
    comments = _power_law_int(0, int(upvotes * 0.4) + 1, exponent=2)
    shares = _power_law_int(0, int(comments * 0.3) + 1, exponent=2)
    sentiment, score = _pick_sentiment()
    published_at = _random_timestamp(date_from, date_to)
    post_id = hashlib.md5(seed.encode()).hexdigest()[:8]
    subreddit_name = subreddit[2:] if subreddit.startswith("r/") else subreddit

    return {
        "external_id": f"rd_{post_id}",
        "platform": "reddit",
        "vendor": "socialvault",
        "author_username": username,
        "author_display_name": username,
        "author_followers": 0,
        "bio": None,
        "body": body,
        "url": f"https://www.reddit.com/{subreddit}/comments/{post_id}/",
        "published_at": published_at,
        "likes": upvotes,
        "shares": shares,
        "comments": comments,
        "views": 0,
        "engagement_score": 0.0,
        "sentiment": sentiment,
        "sentiment_score": score,
        "hashtags": [],
        "mentions": [],
        "media_urls": [],
        "language": "en",
        "extra_metadata": {
            "subreddit": subreddit_name,
            "score": upvotes,
        },
    }


PLATFORM_GENERATORS = {
    "twitter": _generate_twitter_post,
    "tiktok": _generate_tiktok_post,
    "youtube": _generate_youtube_post,
    "reddit": _generate_reddit_post,
    "facebook": _generate_facebook_post,
    "pinterest": _generate_pinterest_post,
}

SOCIALVAULT_TIKTOK_DEFAULT_LOOKBACK_DAYS = 730


class MockSocialVaultAdapter(VendorAdapter):
    """Generates synthetic data for legacy tests and non-production callers."""

    def get_supported_platforms(self) -> List[str]:
        return list(PLATFORM_GENERATORS.keys())

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
        if cancellation:
            cancellation.raise_if_cancelled()
        count = min(max_results, random.randint(40, 150))
        gen = PLATFORM_GENERATORS.get(platform, _generate_facebook_post)
        results = [gen(query, i, date_from, date_to) for i in range(count)]
        if platform.lower() in {"twitter", "x"}:
            for result in results:
                result["vendor"] = "socialvault"
        if progress:
            await progress.before_request()
            await progress.page_received(new_posts=len(results))
        return results


class SocialVaultAdapter(VendorAdapter):
    """Real SociaVault API adapter."""

    BASE_URL = "https://api.sociavault.com/v1/scrape"
    TIKTOK_SEARCH_ENDPOINT = "tiktok/search/keyword"
    TWITTER_SEARCH_ENDPOINT = "twitter/search"
    YOUTUBE_SEARCH_ENDPOINT = "youtube/search"
    REDDIT_SEARCH_ENDPOINT = "reddit/search"
    GOOGLE_SEARCH_ENDPOINT = "google/search"
    FACEBOOK_GROUP_POSTS_ENDPOINT = "facebook/group/posts"
    FACEBOOK_PROFILE_POSTS_ENDPOINT = "facebook/profile/posts"

    def __init__(self):
        self.api_key = settings.SOCIALVAULT_API_KEY
        self._mock = MockSocialVaultAdapter()

    def get_supported_platforms(self) -> List[str]:
        return list(PLATFORM_GENERATORS.keys())

    async def _before_provider_request(
        self,
        progress: Optional[ProviderProgressTracker],
    ) -> bool:
        if not progress:
            return True
        try:
            await progress.before_request()
            return True
        except PaginationSafeguardReached as exc:
            reason = {
                "ProviderRepeatedCursor": "repeated_cursor",
                "ProviderMaximumPagesReached": "maximum_pages_reached",
                "ProviderNoProgressTimeout": "no_progress_timeout",
            }.get(type(exc).__name__)
            if reason:
                await progress.record_stop(reason=reason)
            logger.warning(
                "Stopping SociaVault pagination: reason=%s safeguard=%s",
                reason or "pagination_safeguard", type(exc).__name__,
            )
            return False

    async def _record_provider_page(
        self,
        progress: Optional[ProviderProgressTracker],
        *,
        new_posts: int,
        cursor: object = None,
    ) -> bool:
        if not progress:
            return True
        try:
            await progress.page_received(
                new_posts=new_posts,
                cursor=cursor,
            )
            return True
        except PaginationSafeguardReached as exc:
            reason = {
                "ProviderRepeatedCursor": "repeated_cursor",
                "ProviderMaximumPagesReached": "maximum_pages_reached",
                "ProviderNoProgressTimeout": "no_progress_timeout",
            }.get(type(exc).__name__)
            if reason:
                await progress.record_stop(reason=reason)
            logger.warning(
                "Stopping SociaVault pagination: reason=%s safeguard=%s",
                reason or "pagination_safeguard", type(exc).__name__,
            )
            return False

    def _preserve_completed_pages(
        self,
        platform: str,
        exc: Exception,
        *,
        completed_pages: int,
        collected_posts: int,
    ) -> bool:
        """Return partial results when a later SociaVault page request fails."""
        if completed_pages <= 0:
            logger.error(
                "SociaVault %s request failed before the first page completed; "
                "no posts are available to preserve and the platform will fail: %s",
                platform,
                safe_provider_error("socialvault", exc),
            )
            return False
        logger.warning(
            "SociaVault %s pagination failed after %s successful page(s); "
            "preserving %s collected posts and returning them to the worker: %s",
            platform,
            completed_pages,
            collected_posts,
            safe_provider_error("socialvault", exc),
        )
        return True

    def _should_restart_pagination(
        self,
        exc: Exception,
        *,
        completed_pages: int,
        collected_posts: int,
        max_results: int,
        restarts: int,
    ) -> bool:
        response = getattr(exc, "response", None)
        if getattr(response, "status_code", None) != 404 or restarts >= 1:
            return False
        if completed_pages <= 0 or completed_pages > settings.SOCIALVAULT_EARLY_RESTART_MAX_PAGES:
            return False
        return collected_posts < max_results * settings.SOCIALVAULT_EARLY_RESTART_MAX_TARGET_RATIO

    def _log_pagination_restart(self, platform: str, completed_pages: int) -> None:
        logger.warning(
            "SociaVault %s continuation cursor was rejected early after %s page(s); "
            "restarting the search once with deduplication",
            platform,
            completed_pages,
        )

    def _log_completed_page(
        self,
        platform: str,
        *,
        page_number: int,
        stats: ProviderPageStats,
        collected_posts: int,
    ) -> None:
        logger.info(
            "SociaVault %s page completed: page=%s accepted_posts=%s "
            "collected_posts=%s next_page=%s raw_items=%s duplicates=%s "
            "filtered_by_date=%s malformed=%s cursor_only=%s credits_used=%s",
            platform,
            page_number,
            stats.accepted_items,
            collected_posts,
            stats.has_continuation,
            stats.raw_items,
            stats.duplicate_items,
            stats.filtered_items,
            stats.malformed_items,
            stats.cursor_only,
            stats.credits_used,
        )

    async def _apply_page_decision(
        self, platform: str, *, stats: ProviderPageStats, no_progress_pages: int,
        repeated: bool, collected_posts: int, requested_posts: int,
        page_number: int, progress: Optional[ProviderProgressTracker],
    ) -> bool:
        from app.services.budget_service import current_budget
        budget = current_budget.get()
        if budget:
            for key, value in {"pages": 1, "raw_items": stats.raw_items,
                "duplicates": stats.duplicate_items, "out_of_range": stats.filtered_items,
                "malformed": stats.malformed_items}.items():
                budget.metrics[key] = budget.metrics.get(key, 0) + value
            budget.metrics.setdefault("unique_yield_by_page", []).append(stats.accepted_items)
        decision = evaluate_provider_page(
            stats=stats, consecutive_no_progress_pages=no_progress_pages,
            continuation_repeated=repeated, collected_posts=collected_posts,
            requested_posts=requested_posts,
        )
        if decision.should_continue:
            return True
        logger.info(
            "Stopping SociaVault pagination: platform=%s reason=%s page=%s "
            "collected_posts=%s next_cursor_present=%s",
            platform.lower(), decision.stop_reason, page_number, collected_posts,
            stats.has_continuation,
        )
        if progress:
            await progress.record_stop(
                reason=decision.stop_reason or "provider_exhausted",
                details={"raw_items": stats.raw_items,
                         "accepted_items": stats.accepted_items,
                         "credits_used": stats.credits_used},
            )
        return False

    async def _get(
        self,
        client: httpx.AsyncClient,
        url: str,
        *,
        params: dict,
        cancellation: Optional[CancellationSignal] = None,
    ):
        async def request():
            response = await client.get(
                url,
                headers={"X-API-Key": self.api_key},
                params=params,
                timeout=settings.SOCIALVAULT_REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            return response

        pagination_request = any(
            params.get(key) not in (None, "")
            for key in ("cursor", "after", "continuationToken", "next_page_id")
        )
        retry_statuses = frozenset({404}) if pagination_request else frozenset()
        pagination_404_retries = (
            settings.SOCIALVAULT_PAGINATION_404_RETRIES
            if pagination_request
            else None
        )
        from app.services.budget_service import current_budget, current_endpoint
        budget = current_budget.get()
        endpoint = urlparse(url).path.removeprefix("/v1/scrape")
        key = budget.cache_key(endpoint, params) if budget else None
        if budget:
            cached = await budget.cached(key)
            if cached is not None:
                return httpx.Response(200, json=cached, request=httpx.Request("GET", url))
        token = current_endpoint.set(endpoint)
        try:
            response = await socialvault_request_controller.run_async(
                request, cancellation=cancellation,
                additional_retry_status_codes=retry_statuses,
                additional_status_max_retries=pagination_404_retries,
            )
            if budget:
                await budget.cache(key, response.json())
            return response
        finally:
            current_endpoint.reset(token)

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
        if cancellation:
            cancellation.raise_if_cancelled()
        if not self.api_key:
            logger.warning(
                "SociaVault collection skipped: platform=%s reason=missing_api_key",
                platform,
            )
            return []

        normalized_platform = platform.lower()
        logger.info(
            "SociaVault collection started: platform=%s max_results=%s "
            "date_from=%s date_to=%s",
            normalized_platform,
            max_results,
            date_from,
            date_to,
        )

        try:
            if normalized_platform in {"twitter", "x"}:
                results = await self._search_twitter(
                    query, date_from, date_to, max_results, cancellation, progress
                )
            elif normalized_platform == "tiktok":
                results = await self._search_tiktok(
                    query, date_from, date_to, max_results, cancellation, progress
                )
            elif normalized_platform == "youtube":
                results = await self._search_youtube(
                    query, date_from, date_to, max_results, cancellation, progress
                )
            elif normalized_platform == "reddit":
                results = await self._search_reddit(
                    query, date_from, date_to, max_results, cancellation, progress
                )
            elif normalized_platform == "facebook":
                results = await self._search_facebook(
                    query, date_from, date_to, max_results, cancellation, progress
                )
            else:
                results = []
        except CollectionCancelled:
            raise
        except Exception as exc:
            logger.error(
                "SociaVault collection failed without returnable results: "
                "platform=%s action=platform_failed error=%s",
                normalized_platform,
                safe_provider_error("socialvault", exc),
            )
            raise

        logger.info(
            "SociaVault collection returned results to worker: platform=%s posts=%s",
            normalized_platform,
            len(results),
        )
        return results

    async def _search_twitter(
        self,
        query: str,
        date_from: Optional[datetime],
        date_to: Optional[datetime],
        max_results: int,
        cancellation: Optional[CancellationSignal] = None,
        progress: Optional[ProviderProgressTracker] = None,
    ) -> List[dict]:
        results: List[dict] = []
        seen_external_ids = set()
        cursor: Optional[str] = None
        no_progress_pages = 0
        completed_pages = 0
        pagination_restarts = 0

        async with httpx.AsyncClient() as client:
            while len(results) < max_results:
                if not await self._before_provider_request(progress):
                    break
                params = {"query": query, "type": "Latest"}
                if cursor:
                    params["cursor"] = cursor

                try:
                    response = await self._get(
                        client,
                        f"{self.BASE_URL}/{self.TWITTER_SEARCH_ENDPOINT}",
                        params=params,
                        cancellation=cancellation,
                    )
                except CollectionCancelled:
                    break
                except Exception as exc:
                    if self._should_restart_pagination(
                        exc,
                        completed_pages=completed_pages,
                        collected_posts=len(results),
                        max_results=max_results,
                        restarts=pagination_restarts,
                    ):
                        pagination_restarts += 1
                        self._log_pagination_restart("Twitter", completed_pages)
                        cursor = None
                        no_progress_pages = 0
                        continue
                    if self._preserve_completed_pages(
                        "Twitter",
                        exc,
                        completed_pages=completed_pages,
                        collected_posts=len(results),
                    ):
                        break
                    raise

                payload = response.json()
                data = payload.get("data", {}) if isinstance(payload, dict) else {}
                page_added = 0
                duplicates = filtered = malformed = 0
                raw_tweets = self._twitter_tweet_results(data)
                for tweet in raw_tweets:
                    try:
                        post = self._normalize_twitter_post(tweet)
                    except (AttributeError, TypeError, ValueError):
                        logger.warning("Skipping malformed SociaVault Twitter result")
                        malformed += 1
                        continue
                    external_id = post.get("external_id")
                    if not external_id or external_id in seen_external_ids:
                        duplicates += 1
                        continue
                    seen_external_ids.add(external_id)
                    if not self._in_date_range(post.get("published_at"), date_from, date_to):
                        filtered += 1
                        continue
                    results.append(post)
                    page_added += 1
                    if len(results) >= max_results:
                        break

                completed_pages += 1

                if cancellation and cancellation.is_cancelled:
                    break
                no_progress_pages = no_progress_pages + 1 if page_added == 0 else 0
                cursor_data = data.get("cursor") or {}
                next_cursor = cursor_data.get("bottom") if isinstance(cursor_data, dict) else None
                stats = ProviderPageStats(
                    raw_items=len(raw_tweets), accepted_items=page_added,
                    duplicate_items=duplicates, filtered_items=filtered,
                    malformed_items=malformed, has_continuation=bool(next_cursor),
                    credits_used=payload.get("credits_used") if isinstance(payload, dict) else None,
                )
                self._log_completed_page(
                    "Twitter",
                    page_number=completed_pages,
                    stats=stats,
                    collected_posts=len(results),
                )
                if not await self._record_provider_page(
                    progress,
                    new_posts=page_added,
                    cursor=next_cursor,
                ):
                    break
                if not await self._apply_page_decision(
                    "Twitter", stats=stats, no_progress_pages=no_progress_pages,
                    repeated=next_cursor == cursor and next_cursor is not None,
                    collected_posts=len(results), requested_posts=max_results,
                    page_number=completed_pages, progress=progress,
                ):
                    break
                cursor = next_cursor

        return results[:max_results]

    def _twitter_tweet_results(self, data: dict) -> List[dict]:
        timeline = ((data.get("result") or {}).get("timeline") or {})
        tweets = []
        for instruction in self._dict_values(timeline.get("instructions")):
            for entry in self._dict_values(instruction.get("entries")):
                content = entry.get("content") or {}
                item_contents = [content.get("itemContent")]
                for module_item in self._dict_values(content.get("items")):
                    item = module_item.get("item") or module_item
                    if isinstance(item, dict):
                        item_contents.append(item.get("itemContent"))
                for item_content in item_contents:
                    if not isinstance(item_content, dict):
                        continue
                    result = ((item_content.get("tweet_results") or {}).get("result"))
                    if not isinstance(result, dict):
                        continue
                    if isinstance(result.get("tweet"), dict):
                        result = result["tweet"]
                    if result.get("rest_id") or (result.get("legacy") or {}).get("id_str"):
                        tweets.append(result)
        return tweets

    async def _search_tiktok(
        self,
        query: str,
        date_from: Optional[datetime],
        date_to: Optional[datetime],
        max_results: int,
        cancellation: Optional[CancellationSignal] = None,
        progress: Optional[ProviderProgressTracker] = None,
    ) -> List[dict]:
        results: List[dict] = []
        seen_external_ids = set()
        cursor: Optional[int] = None
        completed_pages = 0
        pagination_restarts = 0
        no_progress_pages = 0
        effective_date_from, effective_date_to = self._tiktok_date_window(date_from, date_to)

        async with httpx.AsyncClient() as client:
            while len(results) < max_results:
                if not await self._before_provider_request(progress):
                    break
                params = {
                    "query": query,
                    "date_posted": "all-time",
                    "sort_by": "date-posted",
                }
                if cursor is not None:
                    params["cursor"] = cursor

                try:
                    response = await self._get(
                        client,
                        f"{self.BASE_URL}/{self.TIKTOK_SEARCH_ENDPOINT}",
                        params=params,
                        cancellation=cancellation,
                    )
                except CollectionCancelled:
                    break
                except Exception as exc:
                    if self._should_restart_pagination(
                        exc,
                        completed_pages=completed_pages,
                        collected_posts=len(results),
                        max_results=max_results,
                        restarts=pagination_restarts,
                    ):
                        pagination_restarts += 1
                        self._log_pagination_restart("TikTok", completed_pages)
                        cursor = None
                        continue
                    if self._preserve_completed_pages(
                        "TikTok",
                        exc,
                        completed_pages=completed_pages,
                        collected_posts=len(results),
                    ):
                        break
                    raise

                payload = response.json()
                data = payload.get("data", {}) if isinstance(payload, dict) else {}
                page_results: List[dict] = []
                dated_page_results: List[dict] = []
                page_aged_out = False

                raw_items_list = self._dict_values(data.get("search_item_list"))
                duplicates = filtered = malformed = 0
                for item in raw_items_list:
                    try:
                        post = self._normalize_tiktok_post(item, effective_date_from, effective_date_to)
                    except (AttributeError, TypeError, ValueError):
                        malformed += 1
                        continue
                    external_id = post.get("external_id")
                    if not external_id or external_id in seen_external_ids:
                        duplicates += 1
                        continue
                    seen_external_ids.add(external_id)
                    published_at = post.get("published_at")
                    if isinstance(published_at, datetime):
                        dated_page_results.append(post)
                    if self._in_date_range(published_at, effective_date_from, effective_date_to):
                        page_results.append(post)
                    else:
                        filtered += 1

                results.extend(page_results[: max_results - len(results)])
                completed_pages += 1

                if cancellation and cancellation.is_cancelled:
                    break

                next_cursor = data.get("cursor")
                has_continuation = bool(data.get("has_more") and next_cursor is not None)
                no_progress_pages = no_progress_pages + 1 if not page_results else 0
                stats = ProviderPageStats(
                    raw_items=len(raw_items_list), accepted_items=len(page_results),
                    duplicate_items=duplicates, filtered_items=filtered,
                    malformed_items=malformed, has_continuation=has_continuation,
                    credits_used=payload.get("credits_used") if isinstance(payload, dict) else None,
                )
                self._log_completed_page(
                    "TikTok",
                    page_number=completed_pages,
                    stats=stats,
                    collected_posts=len(results),
                )
                if not await self._record_provider_page(
                    progress,
                    new_posts=len(page_results),
                    cursor=next_cursor,
                ):
                    break

                if effective_date_from and dated_page_results and all(
                    post["published_at"] < effective_date_from for post in dated_page_results
                ):
                    page_aged_out = True

                if page_aged_out:
                    break
                if not await self._apply_page_decision(
                    "TikTok", stats=stats, no_progress_pages=no_progress_pages,
                    repeated=next_cursor == cursor and next_cursor is not None,
                    collected_posts=len(results), requested_posts=max_results,
                    page_number=completed_pages, progress=progress,
                ):
                    break
                cursor = next_cursor

        return results[:max_results]

    async def _search_facebook(
        self,
        query: str,
        date_from: Optional[datetime],
        date_to: Optional[datetime],
        max_results: int,
        cancellation: Optional[CancellationSignal] = None,
        progress: Optional[ProviderProgressTracker] = None,
    ) -> List[dict]:
        results: List[dict] = []
        seen_external_ids = set()
        target_failures: List[Exception] = []
        successful_pages = 0

        async with httpx.AsyncClient() as client:
            targets = await self._discover_facebook_urls(
                client,
                query,
                cancellation,
                progress,
            )
            for target in targets:
                if cancellation and cancellation.is_cancelled:
                    break
                if len(results) >= max_results:
                    break
                cursor: Optional[str] = None
                pagination_restarts = 0
                no_progress_pages = 0

                while len(results) < max_results:
                    if not await self._before_provider_request(progress):
                        break
                    endpoint = (
                        self.FACEBOOK_GROUP_POSTS_ENDPOINT
                        if target["kind"] == "group"
                        else self.FACEBOOK_PROFILE_POSTS_ENDPOINT
                    )
                    params = {"url": target["url"]}
                    if target["kind"] == "group":
                        params["sort_by"] = self._facebook_group_sort(date_from, date_to)
                    if cursor:
                        params["cursor"] = cursor

                    try:
                        response = await self._get(
                            client,
                            f"{self.BASE_URL}/{endpoint}",
                            params=params,
                            cancellation=cancellation,
                        )
                    except CollectionCancelled:
                        break
                    except Exception as exc:
                        if self._should_restart_pagination(
                            exc,
                            completed_pages=successful_pages,
                            collected_posts=len(results),
                            max_results=max_results,
                            restarts=pagination_restarts,
                        ):
                            pagination_restarts += 1
                            self._log_pagination_restart("Facebook", successful_pages)
                            cursor = None
                            continue
                        target_failures.append(exc)
                        logger.warning(
                            "SociaVault Facebook %s target failed after %s collected posts; "
                            "preserving results and continuing to the next target: %s",
                            target["kind"],
                            len(results),
                            safe_provider_error("socialvault", exc),
                        )
                        break

                    successful_pages += 1
                    payload = response.json()
                    data = payload.get("data", {}) if isinstance(payload, dict) else {}
                    page_added = 0
                    duplicates = filtered = malformed = 0
                    raw_items_list = self._dict_values(data.get("posts"))
                    for item in raw_items_list:
                        try:
                            post = self._normalize_facebook_post(item, target)
                        except (AttributeError, TypeError, ValueError):
                            malformed += 1
                            continue
                        external_id = post.get("external_id")
                        if not external_id or external_id in seen_external_ids:
                            duplicates += 1
                            continue
                        seen_external_ids.add(external_id)
                        if not self._in_date_range(post.get("published_at"), date_from, date_to):
                            filtered += 1
                            continue
                        results.append(post)
                        page_added += 1
                        if len(results) >= max_results:
                            break

                    if cancellation and cancellation.is_cancelled:
                        break
                    next_cursor = data.get("cursor")
                    no_progress_pages = no_progress_pages + 1 if page_added == 0 else 0
                    stats = ProviderPageStats(
                        raw_items=len(raw_items_list), accepted_items=page_added,
                        duplicate_items=duplicates, filtered_items=filtered,
                        malformed_items=malformed, has_continuation=bool(next_cursor),
                        credits_used=payload.get("credits_used") if isinstance(payload, dict) else None,
                    )
                    self._log_completed_page(
                        "Facebook",
                        page_number=successful_pages,
                        stats=stats,
                        collected_posts=len(results),
                    )
                    if not await self._record_provider_page(
                        progress,
                        new_posts=page_added,
                        cursor=(
                            f"{target['url']}:{next_cursor}"
                            if next_cursor
                            else None
                        ),
                    ):
                        break
                    if not await self._apply_page_decision(
                        "Facebook", stats=stats, no_progress_pages=no_progress_pages,
                        repeated=next_cursor == cursor and next_cursor is not None,
                        collected_posts=len(results), requested_posts=max_results,
                        page_number=successful_pages, progress=progress,
                    ):
                        break
                    cursor = next_cursor

        if not results and target_failures and successful_pages == 0:
            logger.error(
                "SociaVault Facebook failed before any post page completed; "
                "failed_targets=%s no posts are available to preserve",
                len(target_failures),
            )
            raise target_failures[-1]
        return results[:max_results]

    async def _discover_facebook_urls(
        self,
        client: httpx.AsyncClient,
        query: str,
        cancellation: Optional[CancellationSignal] = None,
        progress: Optional[ProviderProgressTracker] = None,
    ) -> List[dict]:
        if not await self._before_provider_request(progress):
            return []
        response = await self._get(
            client,
            f"{self.BASE_URL}/{self.GOOGLE_SEARCH_ENDPOINT}",
            params={"query": f"public facebook groups {query}"},
            cancellation=cancellation,
        )

        payload = response.json()
        data = payload.get("data", {}) if isinstance(payload, dict) else {}
        targets = self._classify_facebook_urls(data.get("results"))
        await self._record_provider_page(
            progress,
            new_posts=len(targets),
            cursor="facebook-discovery",
        )
        return targets

    def _classify_facebook_urls(self, results: Any) -> List[dict]:
        targets = []
        seen_urls = set()
        for item in self._dict_values(results):
            url = self._normalize_facebook_url(item.get("url"))
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            parsed = urlparse(url)
            kind = "group" if "/groups/" in parsed.path.lower() else "profile"
            targets.append({"url": url, "kind": kind})
        return targets

    def _normalize_facebook_url(self, value: Any) -> Optional[str]:
        if not isinstance(value, str) or not value:
            return None
        parsed = urlparse(value.strip())
        host = parsed.netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        if host not in {"facebook.com", "m.facebook.com"}:
            return None
        path = parsed.path.rstrip("/") or "/"
        segments = [segment for segment in path.split("/") if segment]
        if len(segments) >= 2 and segments[0].lower() == "groups":
            path = f"/groups/{segments[1]}"
        elif len(segments) >= 3 and segments[1].lower() in {
            "posts",
            "photos",
            "videos",
        }:
            path = f"/{segments[0]}"
        return urlunparse(("https", "www.facebook.com", path + "/", "", "", ""))

    def _facebook_group_sort(
        self,
        date_from: Optional[datetime],
        date_to: Optional[datetime],
    ) -> str:
        return "CHRONOLOGICAL" if date_from or date_to else "TOP_POSTS"

    async def _search_reddit(
        self,
        query: str,
        date_from: Optional[datetime],
        date_to: Optional[datetime],
        max_results: int,
        cancellation: Optional[CancellationSignal] = None,
        progress: Optional[ProviderProgressTracker] = None,
    ) -> List[dict]:
        results: List[dict] = []
        seen_external_ids = set()
        after: Optional[str] = None
        no_progress_pages = 0
        completed_pages = 0
        pagination_restarts = 0
        timeframe = self._reddit_timeframe(date_from, date_to)

        async with httpx.AsyncClient() as client:
            while len(results) < max_results:
                if not await self._before_provider_request(progress):
                    break
                params = {
                    "query": query,
                    "sort": "relevance",
                    "trim": "true",
                    "timeframe": timeframe,
                }
                if after:
                    params["after"] = after

                try:
                    response = await self._get(
                        client,
                        f"{self.BASE_URL}/{self.REDDIT_SEARCH_ENDPOINT}",
                        params=params,
                        cancellation=cancellation,
                    )
                except CollectionCancelled:
                    break
                except Exception as exc:
                    if self._should_restart_pagination(
                        exc,
                        completed_pages=completed_pages,
                        collected_posts=len(results),
                        max_results=max_results,
                        restarts=pagination_restarts,
                    ):
                        pagination_restarts += 1
                        self._log_pagination_restart("Reddit", completed_pages)
                        after = None
                        no_progress_pages = 0
                        continue
                    if self._preserve_completed_pages(
                        "Reddit",
                        exc,
                        completed_pages=completed_pages,
                        collected_posts=len(results),
                    ):
                        break
                    raise

                payload = response.json()
                data = payload.get("data", {}) if isinstance(payload, dict) else {}
                page_added = 0
                duplicates = filtered = malformed = 0
                raw_items_list = self._dict_values(data.get("posts"))
                for item in raw_items_list:
                    try:
                        post = self._normalize_reddit_post(item)
                    except (AttributeError, TypeError, ValueError):
                        malformed += 1
                        continue
                    external_id = post.get("external_id")
                    if not external_id or external_id in seen_external_ids:
                        duplicates += 1
                        continue
                    seen_external_ids.add(external_id)
                    if not self._in_date_range(post.get("published_at"), date_from, date_to):
                        filtered += 1
                        continue
                    results.append(post)
                    page_added += 1
                    if len(results) >= max_results:
                        break

                completed_pages += 1

                if cancellation and cancellation.is_cancelled:
                    break
                no_progress_pages = no_progress_pages + 1 if page_added == 0 else 0
                next_after = data.get("after")
                stats = ProviderPageStats(
                    raw_items=len(raw_items_list), accepted_items=page_added,
                    duplicate_items=duplicates, filtered_items=filtered,
                    malformed_items=malformed, has_continuation=bool(next_after),
                    credits_used=payload.get("credits_used") if isinstance(payload, dict) else None,
                )
                self._log_completed_page(
                    "Reddit",
                    page_number=completed_pages,
                    stats=stats,
                    collected_posts=len(results),
                )
                if not await self._record_provider_page(
                    progress,
                    new_posts=page_added,
                    cursor=next_after,
                ):
                    break
                if not await self._apply_page_decision(
                    "Reddit", stats=stats, no_progress_pages=no_progress_pages,
                    repeated=next_after == after and next_after is not None,
                    collected_posts=len(results), requested_posts=max_results,
                    page_number=completed_pages, progress=progress,
                ):
                    break
                after = next_after

        return results[:max_results]

    def _reddit_timeframe(
        self,
        date_from: Optional[datetime],
        date_to: Optional[datetime],
    ) -> str:
        if not date_from or not date_to:
            return "all"
        start = self._ensure_utc(date_from)
        end = self._ensure_utc(date_to)
        if not start or not end or end < start:
            return "all"

        days = (end.date() - start.date()).days + 1
        if days <= 1:
            return "day"
        if days <= 7:
            return "week"
        if days <= 31:
            return "month"
        if days <= 365:
            return "year"
        return "all"

    def _tiktok_date_window(
        self,
        date_from: Optional[datetime],
        date_to: Optional[datetime],
    ) -> tuple[Optional[datetime], Optional[datetime]]:
        effective_date_from = self._ensure_utc(date_from)
        effective_date_to = self._ensure_utc(date_to)
        if not effective_date_from and not effective_date_to:
            effective_date_from = (
                datetime.now(timezone.utc) - timedelta(days=SOCIALVAULT_TIKTOK_DEFAULT_LOOKBACK_DAYS)
            )
        return effective_date_from, effective_date_to

    def _ensure_utc(self, value: Optional[datetime]) -> Optional[datetime]:
        if not value:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def _in_date_range(
        self,
        published_at: Any,
        date_from: Optional[datetime],
        date_to: Optional[datetime],
    ) -> bool:
        if not isinstance(published_at, datetime):
            return True
        published_at = self._ensure_utc(published_at)
        if date_from and published_at.date() < date_from.date():
            return False
        if date_to and published_at.date() > date_to.date():
            return False
        return True

    async def _search_youtube(
        self,
        query: str,
        date_from: Optional[datetime],
        date_to: Optional[datetime],
        max_results: int,
        cancellation: Optional[CancellationSignal] = None,
        progress: Optional[ProviderProgressTracker] = None,
    ) -> List[dict]:
        results: List[dict] = []
        seen_external_ids = set()
        continuation_token: Optional[str] = None
        completed_pages = 0
        pagination_restarts = 0
        no_progress_pages = 0

        async with httpx.AsyncClient() as client:
            while len(results) < max_results:
                if not await self._before_provider_request(progress):
                    break
                params = {
                    "query": query,
                    "sortBy": "relevance",
                    "filter": "all",
                }
                if continuation_token:
                    params["continuationToken"] = continuation_token

                try:
                    response = await self._get(
                        client,
                        f"{self.BASE_URL}/{self.YOUTUBE_SEARCH_ENDPOINT}",
                        params=params,
                        cancellation=cancellation,
                    )
                except CollectionCancelled:
                    break
                except Exception as exc:
                    if self._should_restart_pagination(
                        exc,
                        completed_pages=completed_pages,
                        collected_posts=len(results),
                        max_results=max_results,
                        restarts=pagination_restarts,
                    ):
                        pagination_restarts += 1
                        self._log_pagination_restart("YouTube", completed_pages)
                        continuation_token = None
                        no_progress_pages = 0
                        continue
                    if self._preserve_completed_pages(
                        "YouTube",
                        exc,
                        completed_pages=completed_pages,
                        collected_posts=len(results),
                    ):
                        break
                    raise

                payload = response.json()
                data = payload.get("data", {}) if isinstance(payload, dict) else {}
                raw_items = (
                    self._dict_values(data.get("videos"))
                    + self._dict_values(data.get("shorts"))
                    + self._dict_values(data.get("lives"))
                )
                normalized_page = self._normalize_youtube_page(data, date_from, date_to)
                page_results = []
                duplicates = 0
                for post in normalized_page:
                    external_id = post.get("external_id")
                    if not external_id or external_id in seen_external_ids:
                        duplicates += 1
                        continue
                    seen_external_ids.add(external_id)
                    page_results.append(post)
                results.extend(page_results)
                completed_pages += 1
                no_progress_pages = no_progress_pages + 1 if not page_results else 0

                if cancellation and cancellation.is_cancelled:
                    break
                next_token = data.get("continuationToken")
                stats = ProviderPageStats(
                    raw_items=len(raw_items), accepted_items=len(page_results),
                    duplicate_items=duplicates,
                    filtered_items=max(0, len(raw_items) - len(normalized_page)),
                    has_continuation=bool(next_token),
                    credits_used=payload.get("credits_used") if isinstance(payload, dict) else None,
                )
                self._log_completed_page(
                    "YouTube",
                    page_number=completed_pages,
                    stats=stats,
                    collected_posts=len(results),
                )
                if not await self._record_provider_page(
                    progress,
                    new_posts=len(page_results),
                    cursor=next_token,
                ):
                    break
                if not await self._apply_page_decision(
                    "YouTube", stats=stats, no_progress_pages=no_progress_pages,
                    repeated=next_token == continuation_token and next_token is not None,
                    collected_posts=len(results), requested_posts=max_results,
                    page_number=completed_pages, progress=progress,
                ):
                    break
                continuation_token = next_token

        return results[:max_results]

    def _normalize_tiktok_post(
        self,
        item: dict,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> dict:
        post = item.get("aweme_info") or item
        author = post.get("author") or {}
        stats = post.get("statistics") or {}
        video = post.get("video") or {}
        music = post.get("music") or {}

        external_id = str(post.get("aweme_id") or post.get("id_str") or post.get("id") or "")
        username = author.get("unique_id") or "unknown"
        body = post.get("desc") or ""
        views = self._to_int(stats.get("play_count"))
        likes = self._to_int(stats.get("digg_count"))
        comments = self._to_int(stats.get("comment_count"))
        shares = self._to_int(stats.get("share_count"))

        return {
            "external_id": external_id,
            "platform": "tiktok",
            "vendor": "socialvault",
            "author_username": username,
            "author_display_name": author.get("nickname") or username,
            "author_followers": self._to_int(author.get("follower_count")),
            "bio": author.get("signature"),
            "body": body,
            "url": f"https://www.tiktok.com/@{username}/video/{external_id}",
            "published_at": self._parse_datetime(post.get("create_time"), date_from, date_to),
            "likes": likes,
            "shares": shares,
            "comments": comments,
            "views": views,
            "engagement_score": self._engagement_score(likes, comments, shares, views),
            "sentiment": "neutral",
            "sentiment_score": 0.0,
            "hashtags": self._extract_hashtags(body),
            "mentions": self._extract_mentions(body),
            "media_urls": self._tiktok_media_urls(video),
            "language": post.get("desc_language") or "en",
            "extra_metadata": {
                "sec_uid": author.get("sec_uid"),
                "collect_count": self._to_int(stats.get("collect_count")),
                "duration_ms": self._to_int(video.get("duration")),
                "music_title": music.get("title"),
                "music_url": self._first_url((music.get("play_url") or {}).get("url_list")),
            },
        }

    def _normalize_twitter_post(self, tweet: dict) -> dict:
        legacy = tweet.get("legacy") or {}
        user_result = (((tweet.get("core") or {}).get("user_results") or {}).get("result") or {})
        if isinstance(user_result.get("result"), dict):
            user_result = user_result["result"]
        user_legacy = user_result.get("legacy") or {}

        external_id = str(tweet.get("rest_id") or legacy.get("id_str") or "")
        username = user_legacy.get("screen_name") or "unknown"
        body = legacy.get("full_text") or ""
        views = self._to_int((tweet.get("views") or {}).get("count"))
        likes = self._to_int(legacy.get("favorite_count"))
        shares = self._to_int(legacy.get("retweet_count"))
        comments = self._to_int(legacy.get("reply_count"))
        entities = legacy.get("entities") or {}

        hashtags = [
            f"#{item['text']}"
            for item in self._dict_values(entities.get("hashtags"))
            if item.get("text")
        ] or self._extract_hashtags(body)
        mentions = [
            f"@{item['screen_name']}"
            for item in self._dict_values(entities.get("user_mentions"))
            if item.get("screen_name")
        ] or self._extract_mentions(body)

        return {
            "external_id": external_id,
            "platform": "twitter",
            "vendor": "socialvault",
            "author_username": username,
            "author_display_name": user_legacy.get("name") or username,
            "author_followers": self._to_int(user_legacy.get("followers_count")),
            "bio": user_legacy.get("description"),
            "body": body,
            "url": f"https://x.com/user/status/{external_id}",
            "published_at": self._parse_datetime(legacy.get("created_at")),
            "likes": likes,
            "shares": shares,
            "comments": comments,
            "views": views,
            "engagement_score": self._engagement_score(likes, comments, shares, views),
            "sentiment": "neutral",
            "sentiment_score": 0.0,
            "hashtags": hashtags,
            "mentions": mentions,
            "media_urls": self._twitter_media_urls(legacy),
            "language": legacy.get("lang") or "en",
            "extra_metadata": {
                "quote_count": self._to_int(legacy.get("quote_count")),
                "bookmark_count": self._to_int(legacy.get("bookmark_count")),
                "conversation_id": legacy.get("conversation_id_str"),
                "in_reply_to_status_id": legacy.get("in_reply_to_status_id_str"),
                "user_id": user_result.get("rest_id") or legacy.get("user_id_str"),
                "verified": bool(user_legacy.get("verified")),
                "blue_verified": bool(user_result.get("is_blue_verified")),
                "profile_image_url": user_legacy.get("profile_image_url_https"),
                "source": tweet.get("source"),
            },
        }

    def _normalize_youtube_page(
        self,
        data: dict,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> List[dict]:
        posts = []
        for key in ("videos", "shorts", "lives"):
            posts.extend(
                self._normalize_youtube_post(item, date_from, date_to)
                for item in self._dict_values(data.get(key))
            )
        return posts

    def _normalize_youtube_post(
        self,
        item: dict,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> dict:
        channel = item.get("channel") or {}
        external_id = str(item.get("id") or "")
        channel_title = channel.get("title") or channel.get("handle") or ""
        channel_handle = channel.get("handle") or channel_title or "unknown"
        views = self._to_int(item.get("viewCountInt"))

        # SociaVault search does not include likes/comments for YouTube results.
        # Getting richer per-video metrics requires a separate video endpoint call
        # for each result, which costs 1 additional credit per video.
        return {
            "external_id": external_id,
            "platform": "youtube",
            "vendor": "socialvault",
            "author_username": str(channel_handle).lstrip("@"),
            "author_display_name": channel_title or channel_handle,
            "author_followers": 0,
            "bio": None,
            "body": item.get("title") or "",
            "url": item.get("url") or f"https://www.youtube.com/watch?v={external_id}",
            "published_at": self._parse_datetime(item.get("publishedTime"), date_from, date_to),
            "likes": 0,
            "shares": 0,
            "comments": 0,
            "views": views,
            "engagement_score": 0.0,
            "sentiment": "neutral",
            "sentiment_score": 0.0,
            "hashtags": self._extract_hashtags(item.get("title") or ""),
            "mentions": self._extract_mentions(item.get("title") or ""),
            "media_urls": [item["thumbnail"]] if item.get("thumbnail") else [],
            "language": "en",
            "extra_metadata": {
                "type": item.get("type"),
                "channel_id": channel.get("id"),
                "channel_thumbnail": channel.get("thumbnail"),
                "view_count_text": item.get("viewCountText"),
                "published_time_text": item.get("publishedTimeText"),
                "length_text": item.get("lengthText"),
                "length_seconds": item.get("lengthSeconds"),
                "badges": item.get("badges") or {},
            },
        }

    def _normalize_reddit_post(self, item: dict) -> dict:
        external_id = str(item.get("id") or item.get("name") or "")
        if external_id.startswith("t3_"):
            external_id = external_id[3:]
        title = item.get("title") or ""
        selftext = item.get("selftext") or item.get("body") or ""
        body = f"{title}\n\n{selftext}".strip() if selftext else title
        likes = self._to_int(item.get("ups") if item.get("ups") is not None else item.get("score"))
        comments = self._to_int(item.get("num_comments"))
        shares = self._to_int(item.get("total_awards_received"))
        subreddit = item.get("subreddit")

        return {
            "external_id": external_id,
            "platform": "reddit",
            "vendor": "socialvault",
            "author_username": item.get("author") or "unknown",
            "author_display_name": item.get("author") or "unknown",
            "author_followers": self._to_int(item.get("subreddit_subscribers")),
            "bio": None,
            "body": body,
            "url": item.get("url") or f"https://www.reddit.com/comments/{external_id}/",
            "published_at": self._parse_datetime(item.get("created_utc") or item.get("created")),
            "likes": likes,
            "shares": shares,
            "comments": comments,
            "views": 0,
            "engagement_score": 0.0,
            "sentiment": "neutral",
            "sentiment_score": 0.0,
            "hashtags": [],
            "mentions": self._extract_mentions(body),
            "media_urls": [],
            "language": "en",
            "extra_metadata": {
                "author_fullname": item.get("author_fullname"),
                "subreddit": subreddit,
                "name": item.get("name"),
                "downs": self._to_int(item.get("downs")),
                "upvote_ratio": item.get("upvote_ratio"),
                "score": self._to_int(item.get("score")),
                "is_video": bool(item.get("is_video")),
            },
        }

    def _normalize_facebook_post(self, item: dict, target: dict) -> dict:
        author = item.get("author") or {}
        video_details = item.get("videoDetails") or {}
        external_id = str(item.get("id") or item.get("postId") or item.get("url") or "")
        body = item.get("text") or item.get("message") or ""
        likes = self._to_int(item.get("reactionCount"))
        comments = self._to_int(item.get("commentCount"))
        author_name = author.get("name") or item.get("pageName") or "unknown"

        return {
            "external_id": external_id,
            "platform": "facebook",
            "vendor": "socialvault",
            "author_username": author_name,
            "author_display_name": author_name,
            "author_followers": 0,
            "bio": None,
            "body": body,
            "url": item.get("url") or target.get("url"),
            "published_at": self._parse_datetime(item.get("publishTime")),
            "likes": likes,
            "shares": 0,
            "comments": comments,
            "views": 0,
            "engagement_score": self._engagement_score(likes, comments, 0, 0),
            "sentiment": "neutral",
            "sentiment_score": 0.0,
            "hashtags": self._extract_hashtags(body),
            "mentions": self._extract_mentions(body),
            "media_urls": self._facebook_media_urls(item, video_details),
            "language": "en",
            "extra_metadata": {
                "source_url": target.get("url"),
                "source_type": target.get("kind"),
                "top_comments": item.get("topComments") or [],
                "raw": item,
            },
        }

    def _dict_values(self, value: Any) -> List[dict]:
        if isinstance(value, dict):
            return [item for item in value.values() if isinstance(item, dict)]
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        return []

    def _tiktok_media_urls(self, video: dict) -> List[str]:
        urls = []
        bit_rates = self._dict_values(video.get("bit_rate"))
        if bit_rates:
            urls.append(self._first_url(((bit_rates[0].get("play_addr") or {}).get("url_list"))))
        urls.append(self._first_url((video.get("play_addr") or {}).get("url_list")))
        urls.append(self._first_url((video.get("cover") or {}).get("url_list")))
        return [url for url in urls if url]

    def _facebook_media_urls(self, item: dict, video_details: dict) -> List[str]:
        urls = [
            video_details.get("hdUrl"),
            video_details.get("sdUrl"),
            video_details.get("thumbnailUrl"),
            self._first_url(item.get("image")),
        ]
        return [url for url in urls if url]

    def _twitter_media_urls(self, legacy: dict) -> List[str]:
        urls = []
        entities = legacy.get("extended_entities") or legacy.get("entities") or {}
        for media in self._dict_values(entities.get("media")):
            urls.append(media.get("media_url_https") or media.get("media_url"))
            variants = self._dict_values((media.get("video_info") or {}).get("variants"))
            video_variants = [
                variant for variant in variants
                if variant.get("url") and variant.get("content_type") != "application/x-mpegURL"
            ]
            if video_variants:
                best_variant = max(video_variants, key=lambda item: self._to_int(item.get("bitrate")))
                urls.append(best_variant.get("url"))
        return list(dict.fromkeys(url for url in urls if url))

    def _first_url(self, value: Any) -> Optional[str]:
        if isinstance(value, str):
            return value or None
        if isinstance(value, dict):
            return next((url for url in value.values() if url), None)
        if isinstance(value, list):
            return next((url for url in value if url), None)
        return None

    def _parse_datetime(
        self,
        value: Any,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> datetime:
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value, timezone.utc)
        if isinstance(value, str) and value:
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
            except ValueError:
                try:
                    return datetime.strptime(value, "%a %b %d %H:%M:%S %z %Y")
                except ValueError:
                    pass
        return _random_timestamp(date_from, date_to)

    def _to_int(self, value: Any) -> int:
        if value is None:
            return 0
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    def _engagement_score(self, likes: int, comments: int, shares: int, views: int) -> float:
        if views <= 0:
            return 0.0
        return round((likes + comments * 2 + shares * 3) / views * 100, 4)

    def _extract_hashtags(self, text: str) -> List[str]:
        return re.findall(r"#\w+", text or "")

    def _extract_mentions(self, text: str) -> List[str]:
        return re.findall(r"@\w[\w.]*", text or "")
