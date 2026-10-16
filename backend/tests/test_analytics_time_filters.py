from datetime import datetime, timezone
import uuid
import pytest
from app.models import Project, SearchJob, NormalizedPost
from app.models.collection_pull import CollectionPull, RunPost


@pytest.fixture
async def time_data(sessions, seed_org_and_user):
    org, _, _ = seed_org_and_user
    async with sessions() as db:
        project = Project(name="Time filters", organization_id=org.id)
        other = Project(name="Other project", organization_id=org.id)
        db.add_all([project, other]); await db.flush()
        pulls = [CollectionPull(project_id=p.id, platforms=["tiktok", "instagram", "youtube"], platform_limits={})
                 for p in [project, project, other]]
        db.add_all(pulls); await db.flush()
        jobs = [SearchJob(project_id=p.project_id, pull_id=p.id, name="Run", status="completed",
                          platforms=p.platforms, mode="preview" if i == 0 else "collection")
                for i, p in enumerate([pulls[0], pulls[0], pulls[1], pulls[2]])]
        db.add_all(jobs); await db.flush()
        specs = [("tiktok", 1, 10, 2, 3, 100, False), ("instagram", 3, 5, 1, 0, 0, False),
                 ("tiktok", 3, 20, 4, 0, 200, False), ("tiktok", 2, 999, 0, 0, 0, True),
                 ("tiktok", None, 999, 0, 0, 0, False), ("youtube", 1, 0, 0, 0, 0, False)]
        posts = [NormalizedPost(project_id=project.id, platform=platform, vendor="fixture", external_id=str(i),
                    published_at=datetime(2026, 1, day, tzinfo=timezone.utc) if day else None,
                    likes=likes, comments=comments, shares=shares, views=views, excluded=excluded)
                 for i, (platform, day, likes, comments, shares, views, excluded) in enumerate(specs)]
        db.add_all(posts); await db.flush()
        for job_index, post_indices in [(0, [0]), (1, [0, 1, 3, 4]), (2, [2, 5])]:
            db.add_all([RunPost(job_id=jobs[job_index].id, post_id=posts[i].id) for i in post_indices])
        await db.commit()
        return project.id, [p.id for p in pulls], [j.id for j in jobs]


@pytest.mark.asyncio
async def test_pull_trends_deduplicate_preview_memberships_and_fill_days(client, auth_headers, time_data):
    project, pulls, _ = time_data
    base = f"/api/projects/{project}/analytics"
    volume = (await client.get(base + "/volume", headers=auth_headers, params={"pull_id": str(pulls[0])})).json()
    assert sum(row["count"] for row in volume["data"]) == 2
    assert volume["platforms"] == ["instagram", "tiktok"]
    assert all(row["count"] == 0 for row in volume["data"] if row["date"] == "2026-01-02")
    engagement = (await client.get(base + "/engagement", headers=auth_headers, params={"pull_id": str(pulls[0])})).json()
    assert engagement["metrics"] == ["likes", "comments", "shares", "views"]
    assert engagement["data"] == [
        {"date": "2026-01-01", "likes": 10, "comments": 2, "shares": 3, "views": 100},
        {"date": "2026-01-02", "likes": 0, "comments": 0, "shares": 0, "views": 0},
        {"date": "2026-01-03", "likes": 5, "comments": 1, "shares": 0, "views": 0},
    ]


@pytest.mark.asyncio
async def test_platform_and_pull_filters_intersect_for_both_charts(client, auth_headers, time_data):
    project, pulls, jobs = time_data
    base = f"/api/projects/{project}/analytics"
    params = {"pull_id": str(pulls[0]), "platform": "instagram"}
    volume = (await client.get(base + "/volume", headers=auth_headers, params=params)).json()
    assert volume["data"] == [{"date": "2026-01-03", "platform": "instagram", "count": 1}]
    engagement = (await client.get(base + "/engagement", headers=auth_headers, params=params)).json()
    assert engagement["metrics"] == ["likes", "comments"]
    assert engagement["data"][0]["likes"] == 5
    for endpoint in ["volume", "engagement"]:
        legacy = (await client.get(base + "/" + endpoint, headers=auth_headers, params={"run_id": str(jobs[0])})).json()
        assert len(legacy["data"]) == 1
        empty = (await client.get(base + "/" + endpoint, headers=auth_headers, params={"pull_id": str(pulls[0]), "platform": "reddit"})).json()
        assert empty["data"] == []
        foreign = (await client.get(base + "/" + endpoint, headers=auth_headers, params={"pull_id": str(pulls[2])})).json()
        assert foreign["data"] == []


@pytest.mark.asyncio
async def test_all_pulls_and_zero_engagement_and_date_bounds(client, auth_headers, time_data, sessions):
    project, pulls, _ = time_data
    base = f"/api/projects/{project}/analytics"
    volume = (await client.get(base + "/volume", headers=auth_headers)).json()
    assert sum(row["count"] for row in volume["data"]) == 4
    engagement = (await client.get(base + "/engagement", headers=auth_headers)).json()
    assert sum(row["likes"] for row in engagement["data"]) == 35
    zero = (await client.get(base + "/engagement", headers=auth_headers, params={"platform": "youtube"})).json()
    assert zero["metrics"] == []
    assert zero["data"][0]["views"] == 0
    bounded = (await client.get(base + "/engagement", headers=auth_headers, params={"date_from": "2026-01-02T00:00:00Z", "date_to": "2026-01-03T23:59:59Z"})).json()
    assert sum(row["likes"] for row in bounded["data"]) == 25
    invalid = await client.get(base + "/engagement", headers=auth_headers, params={"pull_id": "invalid"})
    assert invalid.status_code == 422
    unrelated = await client.get(f"/api/projects/{uuid.uuid4()}/analytics/engagement", headers=auth_headers)
    assert unrelated.json() == {"data": [], "metrics": []}

    from app.services.analytics_service import AnalyticsService
    async with sessions() as db:
        service = AnalyticsService(db)
        assert (await service.get_volume(project, uuid.uuid4())).data == []
        assert (await service.get_engagement(project, uuid.uuid4())).data == []
