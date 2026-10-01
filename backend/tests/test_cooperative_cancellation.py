import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from types import ModuleType
import sys
import uuid

import httpx
import pytest

from app.adapters.cancellation import CancellationSignal, CollectionCancelled
from app.adapters.provider_limits import ProviderRequestController
from app.adapters.socialvault_adapter import SocialVaultAdapter
from app.adapters.xpoz_adapter import XpozAdapter
from app.services.collection_lifecycle import (
    finalize_platform_cancellation,
    platform_state,
)
from app.services.platform_collection import (
    PlatformCollectionRequest,
    iter_platform_results,
)
from app.config import settings
from app.workers.tasks import _monitor_collection_cancellation


def collection_requests(*platforms):
    return tuple(
        PlatformCollectionRequest(
            platform=platform,
            query="test",
            date_from=None,
            date_to=None,
            max_results=10,
        )
        for platform in platforms
    )


@pytest.mark.asyncio
async def test_signal_stops_only_unfinished_platforms():
    signal = CancellationSignal()
    waiting = asyncio.Event()

    class Router:
        async def search(self, *, platform, cancellation, **kwargs):
            if platform == "tiktok":
                return [{"external_id": "saved", "platform": platform}]
            waiting.set()
            await cancellation.run(asyncio.Event().wait())

        def get_vendor_for_platform(self, platform):
            return "test"

    results = iter_platform_results(
        Router(),
        collection_requests("twitter", "tiktok", "youtube"),
        signal,
    )
    first = await anext(results)
    await waiting.wait()
    signal.cancel()
    remaining = [result async for result in results]
    by_platform = {
        result.platform: result
        for result in (first, *remaining)
    }

    assert by_platform["tiktok"].status == "completed"
    assert by_platform["tiktok"].posts[0]["external_id"] == "saved"
    assert by_platform["twitter"].status == "cancelled"
    assert by_platform["youtube"].status == "cancelled"


@pytest.mark.asyncio
async def test_cancellation_prevents_provider_retry():
    signal = CancellationSignal()
    attempts = 0

    async def operation():
        nonlocal attempts
        attempts += 1
        request = httpx.Request("GET", "https://provider.invalid")
        response = httpx.Response(502, request=request)
        raise httpx.HTTPStatusError(
            "temporary provider failure",
            request=request,
            response=response,
        )

    async def cancel_during_backoff(_delay):
        signal.cancel()

    controller = ProviderRequestController(
        provider="test",
        max_concurrency=1,
        max_retries=3,
        sleeper=cancel_during_backoff,
    )

    with pytest.raises(CollectionCancelled):
        await controller.run_async(operation, cancellation=signal)

    assert attempts == 1


@pytest.mark.asyncio
async def test_socialvault_keeps_received_page_and_stops_pagination(monkeypatch):
    signal = CancellationSignal()
    calls = 0

    class Response:
        def json(self):
            signal.cancel()
            return {
                "data": {
                    "search_item_list": {
                        "0": {
                            "aweme_info": {
                                "aweme_id": "video-1",
                                "desc": "first page",
                                "create_time": "2026-01-01T00:00:00Z",
                                "statistics": {},
                                "video": {},
                                "author": {"unique_id": "creator"},
                                "music": {},
                            }
                        }
                    },
                    "cursor": 30,
                    "has_more": 1,
                }
            }

    async def fake_get(*args, **kwargs):
        nonlocal calls
        calls += 1
        return Response()

    adapter = SocialVaultAdapter()
    monkeypatch.setattr(adapter, "_get", fake_get)

    posts = await adapter._search_tiktok(
        "test",
        None,
        None,
        100,
        signal,
    )

    assert calls == 1
    assert [post["external_id"] for post in posts] == ["video-1"]


@pytest.mark.asyncio
async def test_xpoz_keeps_received_page_and_does_not_request_next_page(monkeypatch):
    signal = CancellationSignal()
    next_page_calls = 0

    class Page:
        data = [
            SimpleNamespace(
                id="tweet-1",
                text="received page",
                author_username="researcher",
                created_at_date="2026-01-01",
            )
        ]
        pagination = SimpleNamespace(
            page_number=1,
            total_rows=200,
            total_pages=2,
        )

        def has_next_page(self):
            return True

        def next_page(self):
            nonlocal next_page_calls
            next_page_calls += 1
            return None

    client = SimpleNamespace(
        twitter=SimpleNamespace(search_posts=lambda *args, **kwargs: Page())
    )
    adapter = XpozAdapter()
    normalize = adapter._normalize_twitter_post

    def normalize_then_cancel(tweet):
        post = normalize(tweet)
        signal.cancel()
        return post

    monkeypatch.setattr(adapter, "_get_client", lambda: client)
    monkeypatch.setattr(
        adapter,
        "_get_response_type",
        lambda: SimpleNamespace(FAST="fast", PAGING="paging"),
    )
    monkeypatch.setattr(adapter, "_normalize_twitter_post", normalize_then_cancel)

    posts = await adapter._search_twitter(
        "test",
        None,
        None,
        100,
        signal,
    )

    assert [post["external_id"] for post in posts] == ["tweet-1"]
    assert next_page_calls == 0


def test_xpoz_prefers_async_sdk_client_with_configured_timeout(monkeypatch):
    created = {}
    xpoz_module = ModuleType("xpoz")

    class AsyncXpozClient:
        def __init__(self, api_key, timeout):
            created["api_key"] = api_key
            created["timeout"] = timeout

    xpoz_module.AsyncXpozClient = AsyncXpozClient
    monkeypatch.setitem(sys.modules, "xpoz", xpoz_module)

    adapter = XpozAdapter()
    adapter.api_key = "test-key"
    client = adapter._get_client()

    assert isinstance(client, AsyncXpozClient)
    assert created == {
        "api_key": "test-key",
        "timeout": settings.XPOZ_OPERATION_TIMEOUT_SECONDS,
    }


@pytest.mark.asyncio
async def test_database_monitor_signals_cancellation():
    signal = CancellationSignal()

    class Result:
        def scalar_one_or_none(self):
            return "cancelling"

    class Database:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def execute(self, statement):
            return Result()

    await _monitor_collection_cancellation(
        Database,
        uuid.uuid4(),
        signal,
        poll_seconds=0.01,
    )

    assert signal.is_cancelled


def test_finalizing_cancellation_preserves_completed_platforms_and_counts():
    cancelled_at = datetime.now(timezone.utc)
    states = finalize_platform_cancellation(
        ["twitter", "tiktok", "youtube"],
        {
            "twitter": platform_state("cancel_requested"),
            "tiktok": platform_state("completed", posts_collected=42),
            "youtube": platform_state("running", posts_collected=8),
        },
        cancelled_at=cancelled_at,
    )

    assert states["twitter"]["status"] == "cancelled"
    assert states["tiktok"]["status"] == "completed"
    assert states["tiktok"]["posts_collected"] == 42
    assert states["youtube"]["status"] == "cancelled"
    assert states["youtube"]["posts_collected"] == 8
