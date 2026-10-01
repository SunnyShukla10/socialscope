"""Tests for vendor adapters."""
import httpx
import pytest
from types import SimpleNamespace
from datetime import datetime, timezone, timedelta
from app.adapters.xpoz_adapter import (
    MockXpozAdapter,
    XpozAdapter,
    XPOZ_INSTAGRAM_POST_FIELDS,
    XPOZ_TWITTER_FIELDS,
    _build_xpoz_date_kwargs,
)
from app.adapters.socialvault_adapter import MockSocialVaultAdapter, SocialVaultAdapter
from app.adapters.router import VendorRouter


@pytest.mark.asyncio
async def test_mock_xpoz_search():
    adapter = MockXpozAdapter()
    results = await adapter.search(
        query="migraine treatment",
        platform="twitter",
        date_from=datetime.now(timezone.utc) - timedelta(days=30),
        date_to=datetime.now(timezone.utc),
        max_results=50,
    )
    assert len(results) > 0
    assert len(results) <= 50
    for post in results:
        assert "external_id" in post
        assert "body" in post
        assert "platform" in post
        assert post["platform"] == "twitter"


@pytest.mark.asyncio
async def test_mock_xpoz_supported_platforms():
    adapter = MockXpozAdapter()
    platforms = adapter.get_supported_platforms()
    assert "twitter" in platforms
    assert "instagram" in platforms
    assert "reddit" in platforms
    assert "tiktok" not in platforms


@pytest.mark.asyncio
async def test_mock_socialvault_search():
    adapter = MockSocialVaultAdapter()
    results = await adapter.search(
        query="electric vehicle charging",
        platform="tiktok",
        date_from=datetime.now(timezone.utc) - timedelta(days=30),
        date_to=datetime.now(timezone.utc),
        max_results=50,
    )
    assert len(results) > 0
    assert len(results) <= 50
    for post in results:
        assert "external_id" in post
        assert "body" in post
        assert post["platform"] == "tiktok"


@pytest.mark.asyncio
async def test_mock_socialvault_reddit_search():
    adapter = MockSocialVaultAdapter()
    results = await adapter.search(
        query="myasthenia gravis",
        platform="reddit",
        date_from=datetime.now(timezone.utc) - timedelta(days=30),
        date_to=datetime.now(timezone.utc),
        max_results=50,
    )

    assert len(results) > 0
    assert len(results) <= 50
    assert all(post["platform"] == "reddit" for post in results)
    assert all(post["vendor"] == "socialvault" for post in results)


@pytest.mark.asyncio
async def test_socialvault_tiktok_search_paginates_and_normalizes(monkeypatch):
    calls = []

    def make_item(idx):
        return {
            "aweme_info": {
                "aweme_id": f"video_{idx}",
                "desc": f"caption #{idx} @creator",
                "create_time": 1777473564 + idx,
                "statistics": {
                    "play_count": 100 + idx,
                    "digg_count": 10,
                    "comment_count": 2,
                    "share_count": 1,
                    "collect_count": 3,
                },
                "video": {
                    "duration": 12000,
                    "play_addr": {"url_list": {"0": f"https://video/{idx}.mp4"}},
                    "bit_rate": {
                        "0": {
                            "play_addr": {
                                "url_list": {"0": f"https://video/{idx}-hq.mp4"}
                            }
                        }
                    },
                    "cover": {"url_list": {"0": f"https://image/{idx}.jpg"}},
                },
                "author": {
                    "unique_id": "creator",
                    "nickname": "Creator",
                    "sec_uid": "secure-id",
                },
                "music": {
                    "title": "Sound",
                    "play_url": {"url_list": {"0": "https://audio.mp3"}},
                },
            }
        }

    pages = [
        {
            "success": True,
            "data": {
                "success": True,
                "search_item_list": {str(i): make_item(i) for i in range(30)},
                "cursor": 30,
                "has_more": 1,
            },
        },
        {
            "success": True,
            "data": {
                "success": True,
                "search_item_list": {str(i): make_item(i) for i in range(30, 40)},
                "cursor": 40,
                "has_more": 0,
            },
        },
    ]

    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self.payload

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url, headers, params, timeout):
            calls.append({"url": url, "headers": headers, "params": params, "timeout": timeout})
            return FakeResponse(pages[len(calls) - 1])

    monkeypatch.setattr("app.adapters.socialvault_adapter.httpx.AsyncClient", FakeClient)

    adapter = SocialVaultAdapter()
    adapter.api_key = "test-key"

    results = await adapter.search(
        query="myasthenia gravis",
        platform="tiktok",
        date_from=None,
        date_to=None,
        max_results=35,
    )

    assert len(results) == 35
    assert len(calls) == 2
    assert calls[0]["url"] == "https://api.sociavault.com/v1/scrape/tiktok/search/keyword"
    assert calls[0]["params"] == {
        "query": "myasthenia gravis",
        "date_posted": "all-time",
        "sort_by": "date-posted",
    }
    assert "trim" not in calls[0]["params"]
    assert calls[1]["params"]["cursor"] == 30
    assert results[0]["external_id"] == "video_0"
    assert results[0]["url"] == "https://www.tiktok.com/@creator/video/video_0"
    assert results[0]["media_urls"][0] == "https://video/0-hq.mp4"
    assert results[0]["extra_metadata"]["collect_count"] == 3


@pytest.mark.asyncio
async def test_socialvault_tiktok_search_filters_explicit_date_range(monkeypatch):
    calls = []

    def make_item(idx, create_time):
        return {
            "aweme_info": {
                "aweme_id": f"video_{idx}",
                "desc": f"caption {idx}",
                "create_time": create_time,
                "statistics": {},
                "video": {},
                "author": {"unique_id": "creator"},
                "music": {},
            }
        }

    pages = [
        {
            "success": True,
            "data": {
                "success": True,
                "search_item_list": {
                    "0": make_item(0, "2024-04-01T00:00:00Z"),
                    "1": make_item(1, "2024-03-31T23:59:59Z"),
                    "2": make_item(2, "2024-03-15T12:00:00Z"),
                    "3": make_item(3, "2024-02-29T23:59:59Z"),
                },
                "cursor": 4,
                "has_more": 0,
            },
        },
    ]

    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self.payload

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url, headers, params, timeout):
            calls.append({"url": url, "headers": headers, "params": params, "timeout": timeout})
            return FakeResponse(pages[len(calls) - 1])

    monkeypatch.setattr("app.adapters.socialvault_adapter.httpx.AsyncClient", FakeClient)

    adapter = SocialVaultAdapter()
    adapter.api_key = "test-key"

    results = await adapter.search(
        query="myasthenia gravis",
        platform="tiktok",
        date_from=datetime(2024, 3, 1, tzinfo=timezone.utc),
        date_to=datetime(2024, 3, 31, tzinfo=timezone.utc),
        max_results=10,
    )

    assert [post["external_id"] for post in results] == ["video_1", "video_2"]
    assert all(post["published_at"].strftime("%Y-%m-%d").startswith("2024-03") for post in results)


@pytest.mark.asyncio
async def test_socialvault_tiktok_search_defaults_to_recent_window(monkeypatch):
    calls = []

    def make_item(idx, create_time):
        return {
            "aweme_info": {
                "aweme_id": f"video_{idx}",
                "desc": f"caption {idx}",
                "create_time": create_time,
                "statistics": {},
                "video": {},
                "author": {"unique_id": "creator"},
                "music": {},
            }
        }

    pages = [
        {
            "success": True,
            "data": {
                "success": True,
                "search_item_list": {
                    "0": make_item(0, "2026-01-15T00:00:00Z"),
                    "1": make_item(1, "2010-01-15T00:00:00Z"),
                },
                "cursor": 2,
                "has_more": 0,
            },
        },
    ]

    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self.payload

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url, headers, params, timeout):
            calls.append({"url": url, "headers": headers, "params": params, "timeout": timeout})
            return FakeResponse(pages[len(calls) - 1])

    monkeypatch.setattr("app.adapters.socialvault_adapter.httpx.AsyncClient", FakeClient)

    adapter = SocialVaultAdapter()
    adapter.api_key = "test-key"

    results = await adapter.search(
        query="myasthenia gravis",
        platform="tiktok",
        date_from=None,
        date_to=None,
        max_results=10,
    )

    assert [post["external_id"] for post in results] == ["video_0"]


@pytest.mark.asyncio
async def test_socialvault_reddit_search_paginates_dedupes_and_filters_dates(monkeypatch):
    calls = []

    def make_post(idx, created_utc, post_id=None):
        post_id = post_id or f"post_{idx}"
        return {
            "id": post_id,
            "author": f"redditor_{idx}",
            "author_fullname": f"t2_{idx}",
            "subreddit": "MyastheniaGravis",
            "title": f"Myasthenia discussion {idx} @careteam",
            "downs": 0,
            "name": f"t3_{post_id}",
            "upvote_ratio": 0.95,
            "ups": 10 + idx,
            "total_awards_received": idx,
            "score": 20 + idx,
            "created": created_utc,
            "num_comments": 2 + idx,
            "url": f"https://www.reddit.com/r/MyastheniaGravis/comments/{post_id}/thread/",
            "subreddit_subscribers": 12345,
            "is_video": False,
            "created_utc": created_utc,
        }

    pages = [
        {
            "success": True,
            "data": {
                "success": True,
                "posts": {
                    "0": make_post(0, 1710460800, "in_range_1"),
                    "1": make_post(1, 1709164800, "too_old"),
                },
                "after": "next-page",
            },
        },
        {
            "success": True,
            "data": {
                "success": True,
                "posts": {
                    "0": make_post(2, 1710460800, "in_range_1"),
                    "1": make_post(3, 1711756800, "in_range_2"),
                },
                "after": None,
            },
        },
    ]

    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self.payload

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url, headers, params, timeout):
            calls.append({"url": url, "headers": headers, "params": params, "timeout": timeout})
            return FakeResponse(pages[len(calls) - 1])

    monkeypatch.setattr("app.adapters.socialvault_adapter.httpx.AsyncClient", FakeClient)

    adapter = SocialVaultAdapter()
    adapter.api_key = "test-key"

    results = await adapter.search(
        query="myasthenia gravis",
        platform="Reddit",
        date_from=datetime(2024, 3, 1, tzinfo=timezone.utc),
        date_to=datetime(2024, 3, 31, tzinfo=timezone.utc),
        max_results=10,
    )

    assert len(results) == 2
    assert len(calls) == 2
    assert calls[0]["url"] == "https://api.sociavault.com/v1/scrape/reddit/search"
    assert calls[0]["params"] == {
        "query": "myasthenia gravis",
        "sort": "relevance",
        "trim": "true",
        "timeframe": "month",
    }
    assert calls[1]["params"]["after"] == "next-page"
    assert [post["external_id"] for post in results] == ["in_range_1", "in_range_2"]
    assert results[0]["platform"] == "reddit"
    assert results[0]["vendor"] == "socialvault"
    assert results[0]["author_username"] == "redditor_0"
    assert results[0]["body"] == "Myasthenia discussion 0 @careteam"
    assert results[0]["likes"] == 10
    assert results[0]["comments"] == 2
    assert results[0]["shares"] == 0
    assert results[0]["mentions"] == ["@careteam"]
    assert results[0]["published_at"] == datetime.fromtimestamp(1710460800, tz=timezone.utc)
    assert results[0]["extra_metadata"]["subreddit"] == "MyastheniaGravis"


@pytest.mark.asyncio
async def test_socialvault_facebook_discovers_fetches_paginates_and_filters_dates(monkeypatch):
    calls = []

    google_payload = {
        "success": True,
        "data": {
            "success": True,
            "results": {
                "0": {
                    "title": "MG Support Group - Facebook",
                    "url": "https://www.facebook.com/groups/1678996449024744/?ref=share",
                    "description": "group",
                },
                "1": {
                    "title": "MG Foundation",
                    "url": "https://www.facebook.com/MyastheniaGravisFoundation/",
                    "description": "page",
                },
                "2": {
                    "title": "Not Facebook",
                    "url": "https://example.com/facebook",
                    "description": "ignore",
                },
            },
        },
    }

    group_page_1 = {
        "success": True,
        "data": {
            "posts": [
                {
                    "id": "fb_group_1",
                    "text": "Group post in range #MG",
                    "url": "https://www.facebook.com/groups/1678996449024744/posts/fb_group_1/",
                    "author": {"name": "Group Member"},
                    "reactionCount": 7,
                    "commentCount": 3,
                    "publishTime": "2024-03-15T12:00:00Z",
                    "topComments": [{"text": "Helpful"}],
                    "image": "https://image/group.jpg",
                },
                {
                    "id": "fb_group_old",
                    "text": "Old group post",
                    "author": {"name": "Group Member"},
                    "reactionCount": 10,
                    "commentCount": 1,
                    "publishTime": "2024-02-01T12:00:00Z",
                },
            ],
            "cursor": "group-next",
        },
    }
    group_page_2 = {
        "success": True,
        "data": {
            "posts": [
                {
                    "id": "fb_group_1",
                    "text": "Duplicate group post",
                    "author": {"name": "Group Member"},
                    "reactionCount": 99,
                    "commentCount": 99,
                    "publishTime": "2024-03-15T12:00:00Z",
                },
                {
                    "id": "fb_group_2",
                    "text": "Second group post",
                    "author": {"name": "Another Member"},
                    "reactionCount": 4,
                    "commentCount": 2,
                    "publishTime": "2024-03-20T12:00:00Z",
                },
            ],
            "cursor": None,
        },
    }
    profile_page = {
        "success": True,
        "data": {
            "posts": [
                {
                    "id": "fb_profile_1",
                    "text": "Page post in range",
                    "url": "https://www.facebook.com/MyastheniaGravisFoundation/posts/fb_profile_1/",
                    "author": {"name": "MG Foundation"},
                    "reactionCount": 11,
                    "commentCount": 5,
                    "publishTime": "2024-03-25T12:00:00Z",
                    "videoDetails": {
                        "hdUrl": "https://video/hd.mp4",
                        "sdUrl": "https://video/sd.mp4",
                        "thumbnailUrl": "https://video/thumb.jpg",
                    },
                }
            ],
            "cursor": None,
        },
    }

    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self.payload

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url, headers, params, timeout):
            calls.append({"url": url, "headers": headers, "params": params, "timeout": timeout})
            if url.endswith("/google/search"):
                return FakeResponse(google_payload)
            if url.endswith("/facebook/group/posts") and params.get("cursor") == "group-next":
                return FakeResponse(group_page_2)
            if url.endswith("/facebook/group/posts"):
                return FakeResponse(group_page_1)
            if url.endswith("/facebook/profile/posts"):
                return FakeResponse(profile_page)
            raise AssertionError(f"Unexpected URL {url}")

    monkeypatch.setattr("app.adapters.socialvault_adapter.httpx.AsyncClient", FakeClient)

    adapter = SocialVaultAdapter()
    adapter.api_key = "test-key"

    results = await adapter.search(
        query="myasthenia gravis",
        platform="facebook",
        date_from=datetime(2024, 3, 1, tzinfo=timezone.utc),
        date_to=datetime(2024, 3, 31, tzinfo=timezone.utc),
        max_results=3,
    )

    assert [post["external_id"] for post in results] == ["fb_group_1", "fb_group_2", "fb_profile_1"]
    assert calls[0]["url"] == "https://api.sociavault.com/v1/scrape/google/search"
    assert calls[0]["params"] == {"query": "public facebook groups myasthenia gravis"}
    assert calls[1]["url"] == "https://api.sociavault.com/v1/scrape/facebook/group/posts"
    assert calls[1]["params"] == {
        "url": "https://www.facebook.com/groups/1678996449024744/",
        "sort_by": "CHRONOLOGICAL",
    }
    assert calls[2]["params"]["cursor"] == "group-next"
    assert calls[3]["url"] == "https://api.sociavault.com/v1/scrape/facebook/profile/posts"
    assert calls[3]["params"] == {"url": "https://www.facebook.com/MyastheniaGravisFoundation/"}
    assert results[0]["platform"] == "facebook"
    assert results[0]["vendor"] == "socialvault"
    assert results[0]["author_username"] == "Group Member"
    assert results[0]["likes"] == 7
    assert results[0]["comments"] == 3
    assert results[0]["hashtags"] == ["#MG"]
    assert results[0]["media_urls"] == ["https://image/group.jpg"]
    assert results[0]["extra_metadata"]["source_type"] == "group"
    assert results[0]["extra_metadata"]["top_comments"] == [{"text": "Helpful"}]
    assert results[2]["media_urls"] == [
        "https://video/hd.mp4",
        "https://video/sd.mp4",
        "https://video/thumb.jpg",
    ]


@pytest.mark.asyncio
async def test_socialvault_facebook_preserves_posts_and_continues_after_target_timeout(
    monkeypatch,
    caplog,
):
    calls = []

    async def fake_discover(*args, **kwargs):
        return [
            {"url": "https://www.facebook.com/groups/football/", "kind": "group"},
            {"url": "https://www.facebook.com/FootballPage/", "kind": "profile"},
        ]

    class Response:
        def __init__(self, post_id, cursor=None):
            self.post_id = post_id
            self.cursor = cursor

        def json(self):
            return {
                "data": {
                    "posts": [
                        {
                            "id": self.post_id,
                            "text": f"Post {self.post_id}",
                            "author": {"name": "Football Author"},
                            "publishTime": "2026-07-30T12:00:00Z",
                        }
                    ],
                    "cursor": self.cursor,
                }
            }

    async def fake_get(client, url, *, params, cancellation=None):
        calls.append({"url": url, "params": params})
        if url.endswith("/facebook/group/posts") and params.get("cursor"):
            request = httpx.Request("GET", url)
            raise httpx.ReadTimeout("pagination timed out", request=request)
        if url.endswith("/facebook/group/posts"):
            return Response("group-post", cursor="group-next")
        if url.endswith("/facebook/profile/posts"):
            return Response("profile-post")
        raise AssertionError(f"Unexpected URL {url}")

    adapter = SocialVaultAdapter()
    monkeypatch.setattr(adapter, "_discover_facebook_urls", fake_discover)
    monkeypatch.setattr(adapter, "_get", fake_get)

    with caplog.at_level("WARNING", logger="app.adapters.socialvault_adapter"):
        results = await adapter._search_facebook("football", None, None, 10)

    assert [post["external_id"] for post in results] == [
        "group-post",
        "profile-post",
    ]
    assert calls[-1]["url"].endswith("/facebook/profile/posts")
    assert "preserving results and continuing to the next target" in caplog.text
    assert "socialvault request failed (ReadTimeout)" in caplog.text


def test_socialvault_facebook_classifies_and_dedupes_discovered_urls():
    adapter = SocialVaultAdapter()

    targets = adapter._classify_facebook_urls({
        "0": {"url": "https://www.facebook.com/groups/123/?ref=share"},
        "1": {"url": "https://facebook.com/groups/123/"},
        "2": {"url": "https://m.facebook.com/MyPage"},
        "3": {"url": "https://example.com/MyPage"},
        "4": {"url": "https://facebook.com/groups/456/posts/789/?ref=share"},
        "5": {"url": "https://facebook.com/AnotherPage/posts/987/"},
    })

    assert targets == [
        {"url": "https://www.facebook.com/groups/123/", "kind": "group"},
        {"url": "https://www.facebook.com/MyPage/", "kind": "profile"},
        {"url": "https://www.facebook.com/groups/456/", "kind": "group"},
        {"url": "https://www.facebook.com/AnotherPage/", "kind": "profile"},
    ]


def test_socialvault_facebook_group_sort_prefers_quality_without_dates():
    adapter = SocialVaultAdapter()

    assert adapter._facebook_group_sort(None, None) == "TOP_POSTS"
    assert adapter._facebook_group_sort(datetime(2024, 3, 1, tzinfo=timezone.utc), None) == "CHRONOLOGICAL"


@pytest.mark.parametrize(
    ("date_from", "date_to", "expected"),
    [
        (datetime(2024, 3, 1, tzinfo=timezone.utc), datetime(2024, 3, 1, tzinfo=timezone.utc), "day"),
        (datetime(2024, 3, 1, tzinfo=timezone.utc), datetime(2024, 3, 7, tzinfo=timezone.utc), "week"),
        (datetime(2024, 3, 1, tzinfo=timezone.utc), datetime(2024, 3, 31, tzinfo=timezone.utc), "month"),
        (datetime(2024, 1, 1, tzinfo=timezone.utc), datetime(2024, 12, 30, tzinfo=timezone.utc), "year"),
        (datetime(2024, 1, 1, tzinfo=timezone.utc), datetime(2025, 1, 1, tzinfo=timezone.utc), "all"),
        (None, datetime(2024, 3, 31, tzinfo=timezone.utc), "all"),
    ],
)
def test_socialvault_reddit_timeframe_derivation(date_from, date_to, expected):
    adapter = SocialVaultAdapter()

    assert adapter._reddit_timeframe(date_from, date_to) == expected


@pytest.mark.asyncio
async def test_socialvault_youtube_search_paginates_and_normalizes(monkeypatch):
    calls = []

    def make_video(idx, item_type="video"):
        return {
            "type": item_type,
            "id": f"yt_{idx}",
            "url": f"https://www.youtube.com/watch?v=yt_{idx}",
            "title": f"Myasthenia video {idx} #MG",
            "thumbnail": f"https://img.youtube.com/{idx}.jpg",
            "channel": {
                "id": "channel_1",
                "title": "MG Channel",
                "handle": "MGChannel",
                "thumbnail": "https://img.youtube.com/channel.jpg",
            },
            "viewCountText": "1,981 views",
            "viewCountInt": 1981 + idx,
            "publishedTimeText": "11 months ago",
            "publishedTime": "2025-06-06T21:49:40.060Z",
            "lengthText": "2:19",
            "lengthSeconds": 139,
            "badges": {"0": "CC"},
        }

    pages = [
        {
            "success": True,
            "data": {
                "success": True,
                "videos": {str(i): make_video(i) for i in range(30)},
                "shorts": {"0": make_video(30, "short")},
                "lives": {},
                "continuationToken": "next-page",
            },
        },
        {
            "success": True,
            "data": {
                "success": True,
                "videos": {str(i): make_video(i) for i in range(31, 36)},
                "shorts": {},
                "lives": {},
            },
        },
    ]

    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self.payload

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url, headers, params, timeout):
            calls.append({"url": url, "headers": headers, "params": params, "timeout": timeout})
            return FakeResponse(pages[len(calls) - 1])

    monkeypatch.setattr("app.adapters.socialvault_adapter.httpx.AsyncClient", FakeClient)

    adapter = SocialVaultAdapter()
    adapter.api_key = "test-key"

    results = await adapter.search(
        query="myasthenia gravis",
        platform="youtube",
        date_from=None,
        date_to=None,
        max_results=35,
    )

    assert len(results) == 35
    assert len(calls) == 2
    assert calls[0]["url"] == "https://api.sociavault.com/v1/scrape/youtube/search"
    assert calls[0]["params"] == {
        "query": "myasthenia gravis",
        "sortBy": "relevance",
        "filter": "all",
    }
    assert calls[1]["params"]["continuationToken"] == "next-page"
    assert results[0]["external_id"] == "yt_0"
    assert results[0]["platform"] == "youtube"
    assert results[0]["author_username"] == "MGChannel"
    assert results[0]["views"] == 1981
    assert results[0]["published_at"] == datetime(2025, 6, 6, 21, 49, 40, 60000, tzinfo=timezone.utc)
    assert results[0]["media_urls"] == ["https://img.youtube.com/0.jpg"]
    assert results[0]["extra_metadata"]["length_seconds"] == 139


@pytest.mark.asyncio
async def test_mock_socialvault_supported_platforms():
    adapter = MockSocialVaultAdapter()
    platforms = adapter.get_supported_platforms()
    assert "twitter" in platforms
    assert "tiktok" in platforms
    assert "youtube" in platforms
    assert "facebook" in platforms
    assert "pinterest" in platforms
    assert "reddit" in platforms


def test_vendor_router_selects_socialvault_for_twitter():
    router = VendorRouter()
    assert router.get_vendor_for_platform("twitter") == "socialvault"
    assert router.get_vendor_for_platform("x") == "socialvault"
    assert router.get_vendor_for_platform("instagram") == "xpoz"


def test_vendor_router_selects_socialvault_for_reddit():
    router = VendorRouter()

    assert router.get_vendor_for_platform("reddit") == "socialvault"
    assert router.get_vendor_for_platform("Reddit") == "socialvault"


def test_xpoz_instagram_normalizes_created_at_date_as_utc_datetime():
    adapter = XpozAdapter()
    post = SimpleNamespace(
        id="3606450040306139062_4836333238",
        username="nasa",
        full_name="NASA",
        caption="Moonrise",
        created_at_date="2026-05-03",
    )

    result = adapter._normalize_instagram_post(post)

    assert result["published_at"] == datetime(2026, 5, 3, tzinfo=timezone.utc)


def test_xpoz_instagram_requests_only_documented_post_fields():
    assert XPOZ_INSTAGRAM_POST_FIELDS == [
        "id",
        "username",
        "full_name",
        "caption",
        "media_type",
        "image_url",
        "video_url",
        "like_count",
        "comment_count",
        "reshare_count",
        "video_play_count",
        "created_at_date",
    ]


@pytest.mark.asyncio
async def test_xpoz_instagram_search_passes_documented_fields():
    calls = []

    class Instagram:
        async def search_posts(self, query, **kwargs):
            calls.append({"query": query, **kwargs})
            return SimpleNamespace(data=[])

    adapter = XpozAdapter()
    adapter.api_key = "test-key"
    results = await adapter._search_instagram(
        "research",
        None,
        None,
        40,
        client=SimpleNamespace(instagram=Instagram()),
    )

    assert results == []
    assert calls == [
        {
            "query": "research",
            "start_date": "2023-01-01",
            "limit": 40,
            "fields": XPOZ_INSTAGRAM_POST_FIELDS,
        }
    ]


@pytest.mark.asyncio
async def test_xpoz_search_connects_client_before_instagram_namespace(monkeypatch):
    events = []

    class Instagram:
        async def search_posts(self, query, **kwargs):
            events.append("search")
            return SimpleNamespace(data=[])

    class Client:
        connected = False

        async def connect(self):
            events.append("connect")
            self.connected = True

        @property
        def instagram(self):
            events.append("instagram")
            if not self.connected:
                raise RuntimeError("client must connect first")
            return Instagram()

        async def aclose(self):
            events.append("close")

    adapter = XpozAdapter()
    adapter.api_key = "test-key"
    monkeypatch.setattr(adapter, "_get_client", Client)

    results = await adapter.search(
        query="research",
        platform="instagram",
        date_from=None,
        date_to=None,
        max_results=40,
    )

    assert results == []
    assert events == ["connect", "instagram", "search", "close"]


@pytest.mark.asyncio
async def test_xpoz_instagram_failure_logs_redacted_diagnostics(caplog):
    secret = "secret-xpoz-api-key"

    class ProviderFailure(RuntimeError):
        operation_id = "operation-123"
        status_code = 422
        error = f"provider rejected api_key={secret}"

    class Instagram:
        async def search_posts(self, query, **kwargs):
            raise ProviderFailure(
                f"invalid request Authorization: Bearer leaked-token {secret}"
            )

    adapter = XpozAdapter()
    adapter.api_key = secret
    with caplog.at_level("ERROR", logger="app.adapters.xpoz_adapter"):
        with pytest.raises(ProviderFailure):
            await adapter._search_instagram(
                "research",
                None,
                None,
                40,
                client=SimpleNamespace(instagram=Instagram()),
            )

    assert "Xpoz Instagram SDK call failed" in caplog.text
    assert "exception_type=ProviderFailure" in caplog.text
    assert "status_code=422" in caplog.text
    assert "operation_id=operation-123" in caplog.text
    assert "provider rejected api_key=[redacted]" in caplog.text
    assert "Authorization: Bearer [redacted]" in caplog.text
    assert "traceback=" in caplog.text
    assert secret not in caplog.text
    assert "leaked-token" not in caplog.text


def test_xpoz_twitter_does_not_request_created_at_field():
    assert "created_at" not in XPOZ_TWITTER_FIELDS
    assert "created_at_date" in XPOZ_TWITTER_FIELDS


def test_xpoz_date_kwargs_defaults_to_recent_start():
    assert _build_xpoz_date_kwargs(None, None) == {"start_date": "2023-01-01"}


def test_xpoz_date_kwargs_formats_provided_dates():
    kwargs = _build_xpoz_date_kwargs(
        datetime(2023, 1, 2, 4, 5, tzinfo=timezone.utc),
        datetime(2024, 3, 4, 4, 5, tzinfo=timezone.utc),
    )

    assert kwargs == {"start_date": "2023-01-02", "end_date": "2024-03-04"}


def test_xpoz_twitter_normalizes_integer_created_at_as_utc_datetime():
    adapter = XpozAdapter()
    post = SimpleNamespace(
        id="1770621710",
        text="Super Bowl post",
        author_username="sportsfan",
        created_at=1770621710,
    )

    result = adapter._normalize_twitter_post(post)

    assert result["published_at"] == datetime.fromtimestamp(1770621710, tz=timezone.utc)


def test_xpoz_twitter_normalizes_integer_created_at_date_as_utc_datetime():
    adapter = XpozAdapter()
    post = SimpleNamespace(
        id="1770621710",
        text="Super Bowl post",
        author_username="sportsfan",
        created_at_date=1770621710,
    )

    result = adapter._normalize_twitter_post(post)

    assert result["published_at"] == datetime.fromtimestamp(1770621710, tz=timezone.utc)


@pytest.mark.asyncio
async def test_socialvault_twitter_search_paginates_dedupes_and_normalizes(monkeypatch):
    calls = []

    def tweet(tweet_id, *, include_optional=True):
        legacy = {
            "id_str": tweet_id,
            "full_text": "Hello #Research @participant",
            "created_at": "Thu Jul 30 02:03:26 +0000 2026",
            "favorite_count": 12,
            "retweet_count": 3,
            "reply_count": 4,
            "quote_count": 2,
            "bookmark_count": 5,
            "lang": "en",
            "conversation_id_str": "conversation-1",
            "entities": {
                "hashtags": [{"text": "Research"}],
                "user_mentions": [{"screen_name": "participant"}],
            },
        }
        result = {
            "rest_id": tweet_id,
            "legacy": legacy,
            "views": {"count": "101"},
            "core": {
                "user_results": {
                    "result": {
                        "rest_id": "user-1",
                        "is_blue_verified": True,
                        "legacy": {
                            "screen_name": "researcher",
                            "name": "Researcher Name",
                            "followers_count": 987,
                            "description": "Research bio",
                            "verified": False,
                        },
                    }
                }
            },
        }
        if not include_optional:
            result = {
                "rest_id": tweet_id,
                "legacy": {
                    "id_str": tweet_id,
                    "full_text": "Minimal tweet",
                    "created_at": "Thu Jul 30 03:03:26 +0000 2026",
                },
            }
        return result

    pages = [
        {
            "data": {
                "cursor": {"bottom": "next-page", "top": "previous-page"},
                "result": {
                    "timeline": {
                        "instructions": [
                            {"type": "TimelineClearCache"},
                            {
                                "type": "TimelineAddEntries",
                                "entries": [
                                    {
                                        "entryId": "cursor-top",
                                        "content": {"entryType": "TimelineTimelineCursor"},
                                    },
                                    {
                                        "entryId": "tweet-1",
                                        "content": {
                                            "itemContent": {
                                                "tweet_results": {"result": tweet("1")}
                                            }
                                        },
                                    },
                                    {
                                        "entryId": "module",
                                        "content": {
                                            "items": [
                                                {
                                                    "item": {
                                                        "itemContent": {
                                                            "tweet_results": {
                                                                "result": {"tweet": tweet("1")}
                                                            }
                                                        }
                                                    }
                                                }
                                            ]
                                        },
                                    },
                                ],
                            },
                        ]
                    }
                },
            }
        },
        {
            "data": {
                "cursor": {"bottom": None},
                "result": {
                    "timeline": {
                        "instructions": [
                            {
                                "entries": [
                                    {
                                        "content": {
                                            "itemContent": {
                                                "tweet_results": {
                                                    "result": tweet("2", include_optional=False)
                                                }
                                            }
                                        }
                                    }
                                ]
                            }
                        ]
                    }
                },
            }
        },
    ]

    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self.payload

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url, **kwargs):
            calls.append({"url": url, **kwargs})
            return FakeResponse(pages[len(calls) - 1])

    monkeypatch.setattr("app.adapters.socialvault_adapter.httpx.AsyncClient", FakeClient)
    adapter = SocialVaultAdapter()
    adapter.api_key = "test-key"

    results = await adapter._search_twitter(
        "research", None, None, 10
    )

    assert [post["external_id"] for post in results] == ["1", "2"]
    assert calls[0]["url"].endswith("/twitter/search")
    assert calls[0]["params"] == {"query": "research", "type": "Latest"}
    assert calls[0]["headers"] == {"X-API-Key": "test-key"}
    assert calls[1]["params"]["cursor"] == "next-page"
    assert results[0]["vendor"] == "socialvault"
    assert results[0]["platform"] == "twitter"
    assert results[0]["url"] == "https://x.com/user/status/1"
    assert results[0]["published_at"] == datetime(2026, 7, 30, 2, 3, 26, tzinfo=timezone.utc)
    assert results[0]["views"] == 101
    assert results[0]["likes"] == 12
    assert results[0]["shares"] == 3
    assert results[0]["comments"] == 4
    assert results[0]["author_username"] == "researcher"
    assert results[0]["author_followers"] == 987
    assert results[0]["hashtags"] == ["#Research"]
    assert results[0]["mentions"] == ["@participant"]
    assert results[0]["extra_metadata"]["quote_count"] == 2
    assert results[0]["extra_metadata"]["bookmark_count"] == 5
    assert results[1]["views"] == 0
    assert results[1]["author_username"] == "unknown"


@pytest.mark.asyncio
async def test_socialvault_twitter_preserves_posts_when_later_cursor_returns_404(
    monkeypatch,
    caplog,
):
    calls = 0

    class Response:
        def json(self):
            return {
                "data": {
                    "cursor": {"bottom": "rejected-cursor"},
                    "result": {
                        "timeline": {
                            "instructions": [
                                {
                                    "entries": [
                                        {
                                            "content": {
                                                "itemContent": {
                                                    "tweet_results": {
                                                        "result": {
                                                            "rest_id": "tweet-1",
                                                            "legacy": {
                                                                "full_text": "Collected tweet",
                                                                "created_at": "Thu Jul 30 02:03:26 +0000 2026",
                                                            },
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    ]
                                }
                            ]
                        }
                    },
                }
            }

    async def fake_get(client, url, *, params, cancellation=None):
        nonlocal calls
        calls += 1
        if calls == 1:
            return Response()
        request = httpx.Request("GET", url)
        response = httpx.Response(404, request=request)
        raise httpx.HTTPStatusError(
            "cursor not found",
            request=request,
            response=response,
        )

    adapter = SocialVaultAdapter()
    adapter.api_key = "test-key"
    monkeypatch.setattr(adapter, "_get", fake_get)

    with caplog.at_level("WARNING", logger="app.adapters.socialvault_adapter"):
        results = await adapter._search_twitter("research", None, None, 10)

    assert [post["external_id"] for post in results] == ["tweet-1"]
    assert calls == 3
    assert "restarting the search once with deduplication" in caplog.text
    assert "preserving 1 collected posts" in caplog.text


@pytest.mark.asyncio
async def test_socialvault_twitter_early_cursor_failure_restarts_with_fresh_cursor(
    monkeypatch,
):
    calls = 0

    class Response:
        def __init__(self, tweet_id, cursor):
            self.tweet_id = tweet_id
            self.cursor = cursor

        def json(self):
            return {
                "data": {
                    "cursor": {"bottom": self.cursor},
                    "result": {
                        "timeline": {
                            "instructions": [{"entries": [{"content": {"itemContent": {
                                "tweet_results": {"result": {
                                    "rest_id": self.tweet_id,
                                    "legacy": {"full_text": self.tweet_id},
                                }}
                            }}}]}]
                        }
                    },
                }
            }

    async def fake_get(client, url, *, params, cancellation=None):
        nonlocal calls
        calls += 1
        if calls == 1:
            return Response("tweet-1", "rejected-cursor")
        if calls == 2:
            request = httpx.Request("GET", url)
            response = httpx.Response(404, request=request)
            raise httpx.HTTPStatusError(
                "cursor not found", request=request, response=response
            )
        if calls == 3:
            assert "cursor" not in params
            return Response("tweet-1", "fresh-cursor")
        assert params["cursor"] == "fresh-cursor"
        return Response("tweet-2", None)

    adapter = SocialVaultAdapter()
    monkeypatch.setattr(adapter, "_get", fake_get)

    results = await adapter._search_twitter("research", None, None, 10)

    assert [post["external_id"] for post in results] == ["tweet-1", "tweet-2"]
    assert calls == 4


@pytest.mark.asyncio
async def test_socialvault_twitter_initial_404_still_fails(monkeypatch):
    async def fake_get(client, url, *, params, cancellation=None):
        request = httpx.Request("GET", url)
        response = httpx.Response(404, request=request)
        raise httpx.HTTPStatusError(
            "search not found",
            request=request,
            response=response,
        )

    adapter = SocialVaultAdapter()
    monkeypatch.setattr(adapter, "_get", fake_get)

    with pytest.raises(httpx.HTTPStatusError):
        await adapter._search_twitter("research", None, None, 10)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("platform", "payload", "expected_id"),
    [
        (
            "reddit",
            {
                "data": {
                    "posts": {
                        "0": {
                            "id": "reddit-1",
                            "title": "Collected Reddit post",
                            "author": "researcher",
                            "created_utc": 1777473564,
                        }
                    },
                    "after": "next-reddit-page",
                }
            },
            "reddit-1",
        ),
        (
            "tiktok",
            {
                "data": {
                    "search_item_list": {
                        "0": {
                            "aweme_info": {
                                "aweme_id": "tiktok-1",
                                "desc": "Collected TikTok post",
                                "create_time": 1777473564,
                                "author": {"unique_id": "researcher"},
                            }
                        }
                    },
                    "cursor": 30,
                    "has_more": 1,
                }
            },
            "tiktok-1",
        ),
        (
            "youtube",
            {
                "data": {
                    "videos": {
                        "0": {
                            "id": "youtube-1",
                            "title": "Collected YouTube post",
                            "channel": {"handle": "researcher"},
                        }
                    },
                    "shorts": {},
                    "lives": {},
                    "continuationToken": "next-youtube-page",
                }
            },
            "youtube-1",
        ),
    ],
)
async def test_socialvault_paginated_platforms_preserve_posts_after_later_timeout(
    monkeypatch,
    caplog,
    platform,
    payload,
    expected_id,
):
    calls = 0

    class Response:
        def json(self):
            return payload

    async def fake_get(client, url, *, params, cancellation=None):
        nonlocal calls
        calls += 1
        if calls == 1:
            return Response()
        raise httpx.ReadTimeout("later page timed out", request=httpx.Request("GET", url))

    adapter = SocialVaultAdapter()
    adapter.api_key = "test-key"
    monkeypatch.setattr(adapter, "_get", fake_get)

    with caplog.at_level("INFO", logger="app.adapters.socialvault_adapter"):
        results = await adapter.search(platform=platform, query="research", date_from=None, date_to=None)

    assert [post["external_id"] for post in results] == [expected_id]
    assert calls == 2
    assert "page completed: page=1 accepted_posts=1 collected_posts=1 next_page=True" in caplog.text
    assert "pagination failed after 1 successful page(s)" in caplog.text
    assert "preserving 1 collected posts" in caplog.text
    assert "socialvault request failed (ReadTimeout)" in caplog.text
    assert f"collection returned results to worker: platform={platform} posts=1" in caplog.text


@pytest.mark.asyncio
async def test_socialvault_reddit_initial_timeout_still_fails(monkeypatch):
    async def fake_get(client, url, *, params, cancellation=None):
        raise httpx.ReadTimeout("initial page timed out", request=httpx.Request("GET", url))

    adapter = SocialVaultAdapter()
    monkeypatch.setattr(adapter, "_get", fake_get)

    with pytest.raises(httpx.ReadTimeout):
        await adapter._search_reddit("research", None, None, 10)


@pytest.mark.asyncio
async def test_xpoz_twitter_search_uses_paging_and_respects_max_results(monkeypatch):
    calls = []

    class FakeResponseType:
        PAGING = "paging"

    class FakePagination:
        def __init__(self, page_number, total_rows=5, total_pages=3):
            self.page_number = page_number
            self.total_rows = total_rows
            self.total_pages = total_pages

    class FakePage:
        def __init__(self, items, page_number, next_page=None):
            self.data = items
            self.pagination = FakePagination(page_number)
            self._next_page = next_page

        def has_next_page(self):
            return self._next_page is not None

        def next_page(self):
            return self._next_page

    def tweet(idx, created_at="2023-02-01"):
        return SimpleNamespace(
            id=f"tweet_{idx}",
            text=f"tweet text {idx}",
            author_username="mg_research",
            created_at_date=created_at,
            like_count=idx,
            retweet_count=idx,
            reply_count=idx,
            impression_count=idx,
        )

    page3 = FakePage([tweet(4)], 3)
    page2 = FakePage([tweet(2), tweet(3)], 2, page3)
    page1 = FakePage([tweet(0), tweet(1)], 1, page2)

    class FakeTwitter:
        def search_posts(self, *args, **kwargs):
            calls.append({"args": args, "kwargs": kwargs})
            return page1

    class FakeClient:
        twitter = FakeTwitter()

    adapter = XpozAdapter()
    monkeypatch.setattr(adapter, "_get_client", lambda: FakeClient())
    monkeypatch.setattr(adapter, "_get_response_type", lambda: FakeResponseType)

    results = await adapter._search_twitter(
        query="Myasthenia Gravis",
        date_from=datetime(2023, 1, 1, tzinfo=timezone.utc),
        date_to=None,
        max_results=3,
    )

    assert len(results) == 3
    assert [result["external_id"] for result in results] == ["tweet_0", "tweet_1", "tweet_2"]
    assert calls == [
        {
            "args": ("Myasthenia Gravis",),
            "kwargs": {"response_type": "paging", "start_date": "2023-01-01"},
        }
    ]


@pytest.mark.asyncio
async def test_xpoz_twitter_search_filters_date_to_across_pages(monkeypatch):
    class FakeResponseType:
        PAGING = "paging"

    class FakePage:
        def __init__(self, items):
            self.data = items
            self.pagination = SimpleNamespace(page_number=1, total_rows=len(items), total_pages=1)

        def has_next_page(self):
            return False

    page = FakePage([
        SimpleNamespace(id="old", text="old", author_username="u", created_at_date="2023-01-01"),
        SimpleNamespace(id="new", text="new", author_username="u", created_at_date="2024-01-01"),
    ])

    class FakeTwitter:
        def search_posts(self, *args, **kwargs):
            return page

    class FakeClient:
        twitter = FakeTwitter()

    adapter = XpozAdapter()
    monkeypatch.setattr(adapter, "_get_client", lambda: FakeClient())
    monkeypatch.setattr(adapter, "_get_response_type", lambda: FakeResponseType)

    results = await adapter._search_twitter(
        query="Myasthenia Gravis",
        date_from=None,
        date_to=datetime(2023, 12, 31, tzinfo=timezone.utc),
        max_results=10,
    )

    assert [result["external_id"] for result in results] == ["old"]


@pytest.mark.asyncio
async def test_xpoz_twitter_search_returns_partial_results_when_next_page_fails(monkeypatch):
    async def no_wait(_delay):
        return None

    monkeypatch.setattr(
        "app.adapters.xpoz_adapter.xpoz_request_controller._sleep",
        no_wait,
    )

    class FakeResponseType:
        PAGING = "paging"

    class FakePagination:
        page_number = 1
        total_rows = 200
        total_pages = 2

    class FakePage:
        data = [
            SimpleNamespace(
                id="tweet_1",
                text="tweet text 1",
                author_username="mg_research",
                created_at_date="2023-02-01",
            )
        ]
        pagination = FakePagination()

        def has_next_page(self):
            return True

        def next_page(self):
            raise RuntimeError("429 Too Many Requests")

    class FakeTwitter:
        def search_posts(self, *args, **kwargs):
            return FakePage()

    class FakeClient:
        twitter = FakeTwitter()

    adapter = XpozAdapter()
    monkeypatch.setattr(adapter, "_get_client", lambda: FakeClient())
    monkeypatch.setattr(adapter, "_get_response_type", lambda: FakeResponseType)

    results = await adapter._search_twitter(
        query="Myasthenia Gravis",
        date_from=datetime(2023, 1, 1, tzinfo=timezone.utc),
        date_to=None,
        max_results=10,
    )

    assert [result["external_id"] for result in results] == ["tweet_1"]


@pytest.mark.asyncio
async def test_xpoz_twitter_search_stops_when_pages_stop_adding_posts(monkeypatch):
    class FakeResponseType:
        PAGING = "paging"

    class FakePagination:
        def __init__(self, page_number):
            self.page_number = page_number
            self.total_rows = 500
            self.total_pages = 5

    class FakePage:
        def __init__(self, items, page_number):
            self.data = items
            self.pagination = FakePagination(page_number)

        def has_next_page(self):
            return True

        def next_page(self):
            return duplicate_page

    first_page = FakePage(
        [
            SimpleNamespace(id="tweet_1", text="tweet text 1", author_username="u", created_at_date="2023-02-01"),
            SimpleNamespace(id="tweet_2", text="tweet text 2", author_username="u", created_at_date="2023-02-01"),
        ],
        1,
    )
    duplicate_page = FakePage(
        [
            SimpleNamespace(id="tweet_1", text="tweet text 1", author_username="u", created_at_date="2023-02-01"),
            SimpleNamespace(id="tweet_2", text="tweet text 2", author_username="u", created_at_date="2023-02-01"),
        ],
        1,
    )

    class FakeTwitter:
        def search_posts(self, *args, **kwargs):
            return first_page

    class FakeClient:
        twitter = FakeTwitter()

    adapter = XpozAdapter()
    monkeypatch.setattr(adapter, "_get_client", lambda: FakeClient())
    monkeypatch.setattr(adapter, "_get_response_type", lambda: FakeResponseType)

    results = await adapter._search_twitter(
        query="Myasthenia Gravis",
        date_from=datetime(2023, 1, 1, tzinfo=timezone.utc),
        date_to=None,
        max_results=10,
    )

    assert [result["external_id"] for result in results] == ["tweet_1", "tweet_2"]


def test_xpoz_reddit_normalizes_created_at_date_as_utc_datetime():
    adapter = XpozAdapter()
    post = SimpleNamespace(
        id="abc123",
        title="Helpful thread",
        selftext="Longer body",
        author_username="example_user",
        created_at_date="2026-05-03",
    )

    result = adapter._normalize_reddit_post(post)

    assert result["published_at"] == datetime(2026, 5, 3, tzinfo=timezone.utc)


def test_vendor_router_selects_socialvault_for_tiktok():
    router = VendorRouter()
    assert router.get_vendor_for_platform("tiktok") == "socialvault"
    assert router.get_vendor_for_platform("youtube") == "socialvault"
    assert router.get_vendor_for_platform("facebook") == "socialvault"


@pytest.mark.asyncio
async def test_vendor_router_search():
    router = VendorRouter()
    results = await router.search(
        query="test query",
        platform="twitter",
        date_from=datetime.now(timezone.utc) - timedelta(days=30),
        date_to=datetime.now(timezone.utc),
        max_results=20,
    )
    assert results == []


@pytest.mark.asyncio
async def test_vendor_router_raises_adapter_errors():
    class BrokenAdapter:
        async def search(self, **kwargs):
            raise RuntimeError("502 Bad Gateway")

    router = VendorRouter()
    router._socialvault = BrokenAdapter()

    with pytest.raises(RuntimeError, match="502 Bad Gateway"):
        await router.search(
            query="test query",
            platform="twitter",
            date_from=None,
            date_to=None,
            max_results=20,
        )
