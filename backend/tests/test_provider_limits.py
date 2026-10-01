import asyncio
import threading
import time
from types import SimpleNamespace

import httpx
import pytest

from app.adapters.provider_limits import (
    ProviderRequestController,
    SlidingWindowRateLimiter,
)
from app.adapters.xpoz_adapter import XpozAdapter
from app.models.normalized_post import NormalizedPost
from app.workers.tasks import _deduplicate_raw_posts


@pytest.mark.asyncio
async def test_xpoz_rate_limiter_stays_within_configured_window():
    current_time = 0.0
    acquisition_times = []

    def clock():
        return current_time

    async def advance_time(delay):
        nonlocal current_time
        current_time += delay

    limiter = SlidingWindowRateLimiter(
        max_requests=28,
        period_seconds=60,
        clock=clock,
        sleeper=advance_time,
    )

    for _ in range(29):
        await limiter.acquire()
        acquisition_times.append(current_time)

    assert acquisition_times[:28] == [0.0] * 28
    assert acquisition_times[28] == 60.0


@pytest.mark.asyncio
async def test_twitter_and_instagram_share_xpoz_concurrency_limit(monkeypatch):
    active = 0
    max_active = 0
    lock = threading.Lock()

    def track_call(result):
        nonlocal active, max_active
        with lock:
            active += 1
            max_active = max(max_active, active)
        time.sleep(0.03)
        with lock:
            active -= 1
        return result

    class Page:
        data = []
        pagination = SimpleNamespace(page_number=1, total_rows=0, total_pages=1)

        def has_next_page(self):
            return False

    class Client:
        twitter = SimpleNamespace(search_posts=lambda *args, **kwargs: track_call(Page()))
        instagram = SimpleNamespace(
            search_posts=lambda *args, **kwargs: track_call(SimpleNamespace(data=[]))
        )

    controller = ProviderRequestController(
        provider="xpoz",
        max_concurrency=1,
        max_retries=0,
    )
    monkeypatch.setattr(
        "app.adapters.xpoz_adapter.xpoz_request_controller",
        controller,
    )

    adapter = XpozAdapter()
    adapter.api_key = "test-key"
    monkeypatch.setattr(adapter, "_get_client", lambda: Client())
    monkeypatch.setattr(
        adapter,
        "_get_response_type",
        lambda: SimpleNamespace(FAST="fast", PAGING="paging"),
    )

    await asyncio.gather(
        adapter.search("query", "twitter", None, None, 10),
        adapter.search("query", "instagram", None, None, 10),
    )

    assert max_active == 1


@pytest.mark.asyncio
async def test_xpoz_pagination_passes_every_request_through_controller(monkeypatch):
    controlled_calls = []

    class SpyController:
        async def run_sync(self, operation):
            controlled_calls.append(operation)
            return operation()

    class Page:
        def __init__(self, page_number, next_page=None):
            self.data = []
            self.pagination = SimpleNamespace(
                page_number=page_number,
                total_rows=0,
                total_pages=2,
            )
            self._next_page = next_page

        def has_next_page(self):
            return self._next_page is not None

        def next_page(self):
            return self._next_page

    second_page = Page(2)
    first_page = Page(1, second_page)
    client = SimpleNamespace(
        twitter=SimpleNamespace(search_posts=lambda *args, **kwargs: first_page)
    )

    monkeypatch.setattr(
        "app.adapters.xpoz_adapter.xpoz_request_controller",
        SpyController(),
    )
    adapter = XpozAdapter()
    monkeypatch.setattr(adapter, "_get_client", lambda: client)
    monkeypatch.setattr(
        adapter,
        "_get_response_type",
        lambda: SimpleNamespace(FAST="fast", PAGING="paging"),
    )

    await adapter._search_twitter("query", None, None, 10)

    assert len(controlled_calls) == 2


@pytest.mark.asyncio
async def test_retry_after_is_respected_and_retry_result_is_deduplicated():
    sleeps = []
    attempts = 0
    duplicate = {"platform": "twitter", "external_id": "post-1"}

    async def no_wait(delay):
        sleeps.append(delay)

    async def operation():
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            request = httpx.Request("GET", "https://provider.invalid/posts")
            response = httpx.Response(429, request=request, headers={"Retry-After": "4"})
            raise httpx.HTTPStatusError(
                "rate limited",
                request=request,
                response=response,
            )
        return (duplicate, dict(duplicate))

    controller = ProviderRequestController(
        provider="xpoz",
        max_concurrency=2,
        max_retries=2,
        retry_base_seconds=1,
        sleeper=no_wait,
    )

    posts = await controller.run_async(operation)
    unique_posts = _deduplicate_raw_posts("twitter", posts)

    assert attempts == 2
    assert sleeps == [4.0]
    assert unique_posts == [duplicate]
    assert any(
        constraint.name == "uq_normalized_post_project_platform_external_id"
        for constraint in NormalizedPost.__table__.constraints
    )


@pytest.mark.asyncio
async def test_transport_timeout_is_retried():
    attempts = 0
    sleeps = []

    async def operation():
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            request = httpx.Request("GET", "https://provider.invalid/posts")
            raise httpx.ReadTimeout("temporary timeout", request=request)
        return "ok"

    async def no_wait(delay):
        sleeps.append(delay)

    controller = ProviderRequestController(
        provider="socialvault",
        max_concurrency=1,
        max_retries=1,
        retry_base_seconds=0.25,
        sleeper=no_wait,
    )

    assert await controller.run_async(operation) == "ok"
    assert attempts == 2
    assert sleeps == [0.25]


@pytest.mark.asyncio
async def test_optional_404_retry_is_bounded_without_changing_normal_policy():
    attempts = 0
    sleeps = []

    async def operation():
        nonlocal attempts
        attempts += 1
        request = httpx.Request("GET", "https://provider.invalid/posts?cursor=next")
        response = httpx.Response(404, request=request)
        raise httpx.HTTPStatusError("cursor rejected", request=request, response=response)

    async def no_wait(delay):
        sleeps.append(delay)

    controller = ProviderRequestController(
        provider="socialvault",
        max_concurrency=1,
        max_retries=3,
        retry_base_seconds=0.5,
        sleeper=no_wait,
    )

    with pytest.raises(httpx.HTTPStatusError):
        await controller.run_async(
            operation,
            additional_retry_status_codes=frozenset({404}),
            additional_status_max_retries=1,
        )

    assert attempts == 2
    assert sleeps == [0.5]
