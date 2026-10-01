from datetime import datetime, timezone
from types import SimpleNamespace
import uuid

import httpx
import pytest

from app.adapters.provider_limits import (
    ProviderRepeated502Error,
    ProviderRetryBudgetExceeded,
    ProviderRequestController,
    safe_provider_error,
)
from app.adapters.provider_progress import (
    ProviderPageStats,
    ProviderMaximumPagesReached,
    ProviderNoProgressTimeout,
    ProviderProgressTracker,
    ProviderRepeatedCursor,
    evaluate_provider_page,
)
from app.adapters.router import VendorRouter
from app.adapters.socialvault_adapter import SocialVaultAdapter
from app.adapters.xpoz_adapter import XpozAdapter
from app.services.collection_lifecycle import platform_state
from app.workers.tasks import _record_provider_progress


def provider_error(status_code: int) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "https://provider.invalid")
    response = httpx.Response(status_code, request=request)
    return httpx.HTTPStatusError(
        f"{status_code} provider-token-secret",
        request=request,
        response=response,
    )


def test_cursor_only_page_stops_immediately_but_filtered_page_can_continue():
    empty = evaluate_provider_page(
        stats=ProviderPageStats(0, 0, has_continuation=True),
        consecutive_no_progress_pages=1, continuation_repeated=False,
        collected_posts=19, requested_posts=100,
    )
    filtered = evaluate_provider_page(
        stats=ProviderPageStats(20, 0, duplicate_items=20, has_continuation=True),
        consecutive_no_progress_pages=1, continuation_repeated=False,
        collected_posts=19, requested_posts=100,
    )

    assert empty.stop_reason == "empty_page_with_continuation"
    assert filtered.should_continue is True


def test_three_filtered_pages_and_repeated_cursor_stop():
    stats = ProviderPageStats(20, 0, duplicate_items=20, has_continuation=True)
    filtered = evaluate_provider_page(
        stats=stats, consecutive_no_progress_pages=3,
        continuation_repeated=False, collected_posts=19, requested_posts=100,
    )
    repeated = evaluate_provider_page(
        stats=stats, consecutive_no_progress_pages=1,
        continuation_repeated=True, collected_posts=19, requested_posts=100,
    )

    assert filtered.stop_reason == "consecutive_filtered_pages"
    assert repeated.stop_reason == "repeated_cursor"


@pytest.mark.asyncio
async def test_retry_time_budget_stops_excessive_backoff():
    attempts = 0
    sleeps = []

    async def operation():
        nonlocal attempts
        attempts += 1
        raise provider_error(500)

    async def no_wait(delay):
        sleeps.append(delay)

    controller = ProviderRequestController(
        provider="xpoz",
        max_concurrency=1,
        max_retries=5,
        retry_base_seconds=2,
        retry_time_budget_seconds=3,
        sleeper=no_wait,
    )

    with pytest.raises(ProviderRetryBudgetExceeded):
        await controller.run_async(operation)

    assert attempts == 2
    assert sleeps == [2]


@pytest.mark.asyncio
async def test_repeated_502_limit_fails_without_exposing_provider_details():
    attempts = 0

    async def operation():
        nonlocal attempts
        attempts += 1
        raise provider_error(502)

    async def no_wait(_delay):
        return None

    controller = ProviderRequestController(
        provider="xpoz",
        max_concurrency=1,
        max_retries=5,
        retry_base_seconds=0,
        max_repeated_502=2,
        sleeper=no_wait,
    )

    with pytest.raises(ProviderRepeated502Error) as error:
        await controller.run_async(operation)

    assert attempts == 2
    safe_error = safe_provider_error("xpoz", error.value)
    assert safe_error == "xpoz request failed with HTTP 502 (ProviderRepeated502Error)"
    assert "secret" not in safe_error


@pytest.mark.asyncio
async def test_meaningful_page_resets_no_progress_timer():
    now = 0.0
    tracker = ProviderProgressTracker(
        provider="xpoz",
        no_progress_timeout_seconds=10,
        max_pages=10,
        clock=lambda: now,
    )

    await tracker.before_request()
    now = 9
    await tracker.page_received(new_posts=4, cursor="page-1")
    now = 18
    await tracker.before_request()
    now = 20

    with pytest.raises(ProviderNoProgressTimeout):
        await tracker.before_request()


@pytest.mark.asyncio
async def test_maximum_pages_stops_before_an_extra_request():
    tracker = ProviderProgressTracker(
        provider="socialvault",
        no_progress_timeout_seconds=60,
        max_pages=2,
    )

    await tracker.before_request()
    await tracker.page_received(new_posts=2, cursor="page-1")
    await tracker.before_request()
    await tracker.page_received(new_posts=2, cursor="page-2")

    with pytest.raises(ProviderMaximumPagesReached):
        await tracker.before_request()

    assert tracker.requests_started == 2


@pytest.mark.asyncio
async def test_cursor_cycle_is_detected_even_when_not_consecutive():
    tracker = ProviderProgressTracker(
        provider="socialvault",
        no_progress_timeout_seconds=60,
        max_pages=10,
    )

    await tracker.before_request()
    await tracker.page_received(new_posts=1, cursor="cursor-a")
    await tracker.before_request()
    await tracker.page_received(new_posts=1, cursor="cursor-b")
    await tracker.before_request()

    with pytest.raises(ProviderRepeatedCursor):
        await tracker.page_received(new_posts=1, cursor="cursor-a")


@pytest.mark.asyncio
async def test_socialvault_max_pages_returns_received_posts_without_extra_page(
    monkeypatch,
):
    calls = 0

    class Response:
        def json(self):
            return {
                "data": {
                    "search_item_list": {
                        "0": {
                            "aweme_info": {
                                "aweme_id": "video-1",
                                "desc": "received",
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

    tracker = ProviderProgressTracker(
        provider="socialvault",
        no_progress_timeout_seconds=60,
        max_pages=1,
    )
    adapter = SocialVaultAdapter()
    monkeypatch.setattr(adapter, "_get", fake_get)

    posts = await adapter._search_tiktok(
        "test",
        None,
        None,
        100,
        progress=tracker,
    )

    assert calls == 1
    assert [post["external_id"] for post in posts] == ["video-1"]


@pytest.mark.asyncio
async def test_xpoz_repeated_502_safeguard_fails_platform_instead_of_hanging(
    monkeypatch,
):
    class Page:
        data = [
            SimpleNamespace(
                id="tweet-1",
                text="received",
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
            return None

    async def first_page(**kwargs):
        return Page()

    async def repeated_502(*args, **kwargs):
        raise ProviderRepeated502Error(
            "xpoz",
            502,
            "repeated HTTP 502 safeguard reached",
        )

    adapter = XpozAdapter()
    monkeypatch.setattr(adapter, "_call_twitter_search_posts", first_page)
    monkeypatch.setattr(adapter, "_run_sdk_call", repeated_502)
    monkeypatch.setattr(
        adapter,
        "_get_response_type",
        lambda: SimpleNamespace(FAST="fast", PAGING="paging"),
    )

    with pytest.raises(ProviderRepeated502Error):
        await adapter._search_twitter(
            "test",
            None,
            None,
            100,
            client=SimpleNamespace(),
        )


@pytest.mark.asyncio
async def test_router_reports_provider_page_progress():
    events = []

    class Adapter:
        async def search(self, *, progress, **kwargs):
            await progress.before_request()
            await progress.page_received(new_posts=3, cursor="page-1")
            return []

    async def record(platform, event):
        events.append((platform, event))

    router = VendorRouter()
    router._socialvault = Adapter()

    await router.search(
        query="test",
        platform="tiktok",
        progress_callback=record,
    )

    assert events == [
        (
            "tiktok",
            {
                "requests_started": 1,
                "new_posts": 3,
            },
        )
    ]


@pytest.mark.asyncio
async def test_provider_progress_updates_job_and_platform_heartbeat():
    job = SimpleNamespace(
        id=uuid.uuid4(),
        status="running",
        started_at=datetime.now(timezone.utc),
        last_progress_at=None,
        platform_states={"twitter": platform_state("running")},
    )

    class Result:
        def scalar_one_or_none(self):
            return job

    class Database:
        committed = False

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def execute(self, statement):
            return Result()

        async def commit(self):
            self.committed = True

    database = Database()

    await _record_provider_progress(
        lambda: database,
        job.id,
        "twitter",
        {"new_posts": 10},
    )

    assert database.committed is True
    assert job.last_progress_at is not None
    assert job.platform_states["twitter"]["status"] == "running"
    assert job.platform_states["twitter"]["last_progress_at"] is not None
