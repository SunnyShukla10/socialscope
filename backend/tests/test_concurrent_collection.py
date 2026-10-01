import asyncio

import pytest

from app.services.platform_collection import (
    PlatformCollectionRequest,
    collect_platforms,
    iter_platform_results,
)


def _requests(*platforms):
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
async def test_multiple_platforms_begin_collection_concurrently():
    started = set()
    all_started = asyncio.Event()
    release = asyncio.Event()

    class Router:
        async def search(self, *, platform, **kwargs):
            started.add(platform)
            if len(started) == 3:
                all_started.set()
            await release.wait()
            return [{"external_id": f"{platform}-1", "platform": platform}]

        def get_vendor_for_platform(self, platform):
            return "test-provider"

    collection = asyncio.create_task(
        collect_platforms(Router(), _requests("twitter", "youtube", "reddit"))
    )
    await asyncio.wait_for(all_started.wait(), timeout=1)
    assert started == {"twitter", "youtube", "reddit"}

    release.set()
    results = await collection
    assert {result.status for result in results} == {"completed"}


@pytest.mark.asyncio
async def test_failed_platform_does_not_discard_successful_results():
    class Router:
        async def search(self, *, platform, **kwargs):
            if platform == "twitter":
                raise RuntimeError("502 provider-token-secret")
            return [{"external_id": "youtube-1", "platform": platform}]

        def get_vendor_for_platform(self, platform):
            return "socialvault"

    results = await collect_platforms(
        Router(),
        _requests("twitter", "youtube"),
    )
    by_platform = {result.platform: result for result in results}

    assert by_platform["twitter"].status == "failed"
    assert by_platform["twitter"].posts == ()
    assert by_platform["twitter"].error == "socialvault request failed with HTTP 502 (RuntimeError)"
    assert "secret" not in by_platform["twitter"].error
    assert by_platform["youtube"].status == "completed"
    assert by_platform["youtube"].posts[0]["external_id"] == "youtube-1"


@pytest.mark.asyncio
async def test_completed_platform_is_yielded_before_unrelated_platform_finishes():
    slow_started = asyncio.Event()
    slow_release = asyncio.Event()
    slow_finished = False

    class Router:
        async def search(self, *, platform, **kwargs):
            nonlocal slow_finished
            if platform == "twitter":
                slow_started.set()
                await slow_release.wait()
                slow_finished = True
            else:
                await slow_started.wait()
            return [{"external_id": f"{platform}-1", "platform": platform}]

        def get_vendor_for_platform(self, platform):
            return "test-provider"

    results = iter_platform_results(
        Router(),
        _requests("twitter", "tiktok"),
    )
    first_result = await anext(results)

    assert first_result.platform == "tiktok"
    assert first_result.status == "completed"
    assert slow_finished is False

    slow_release.set()
    remaining = [result async for result in results]
    assert [result.platform for result in remaining] == ["twitter"]
