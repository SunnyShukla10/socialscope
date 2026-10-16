import asyncio
import csv
import json
import os
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
import httpx
import pytest
from sqlalchemy import select, func
from app.models import Organization, Project, SearchJob, NormalizedPost
from app.models.collection_pull import CollectionPull, ProviderUsage, RunPost
from app.services.budget_service import BudgetContext, BudgetStopped, usage_summary, current_budget, current_endpoint
from app.adapters.provider_limits import ProviderRequestController
from app.services.post_service import PostService
from app.workers.tasks import _persist_platform_posts

async def fixture_pull(sessions, platforms=None, limit=8, requests=20):
    platforms = platforms or ["twitter", "reddit", "youtube"]
    async with sessions() as db:
        org = Organization(name="Research", slug=str(uuid.uuid4()))
        db.add(org); await db.flush()
        project = Project(name="Transit", organization_id=org.id)
        db.add(project); await db.flush()
        pull = CollectionPull(project_id=project.id, platforms=platforms, comparison_limit=limit,
            platform_limits={p:20 for p in platforms}, request_limit=requests)
        db.add(pull); await db.flush()
        job = SearchJob(project_id=project.id, pull_id=pull.id, mode="collection", fingerprint="question",
            name="Run", status="running", platforms=platforms, requested_post_count=500,
            platform_allocations={p:100 for p in platforms})
        db.add(job); await db.commit()
        return org, project, pull, job

@pytest.mark.asyncio
@pytest.mark.parametrize("platform", ["twitter", "reddit", "youtube", "tiktok", "facebook", "instagram"])
async def test_collection_ignores_legacy_credit_and_request_caps(sessions, platform):
    _, _, pull, job = await fixture_pull(sessions, [platform], requests=1)
    preview = BudgetContext(sessions, pull.id, job.id, platform, "preview", "query")
    from app.services.budget_service import PREVIEW_REQUESTS
    for _ in range(PREVIEW_REQUESTS.get(platform, 1)):
        await preview.reserve("xpoz" if platform == "instagram" else "socialvault", "/twitter/search")
    with pytest.raises(BudgetStopped, match="preview_limit"):
        await preview.reserve("socialvault", "/twitter/search")
    full = BudgetContext(sessions, pull.id, job.id, platform, "collection", "query")
    for _ in range(25):
        await full.reserve("xpoz" if platform == "instagram" else "socialvault", "/twitter/search")
    async with sessions() as db:
        summary = await usage_summary(db, pull)
        assert summary["credit_cap"] is None
        assert summary["platforms"][platform]["requests"] == 25 + PREVIEW_REQUESTS.get(platform, 1)
        assert "charged_allowance" not in summary["platforms"][platform]
        assert "credit_limit" not in summary["platforms"][platform]


@pytest.mark.asyncio
async def test_unknown_endpoint_cost_does_not_block_collection(sessions):
    _, _, pull, job = await fixture_pull(sessions)
    ctx = BudgetContext(sessions, pull.id, job.id, "twitter", "collection", "q")
    called = False
    async def network():
        nonlocal called
        called = True
        return httpx.Response(200, json={"credits_used": 5})
    await ctx.execute("socialvault", "/new-route", network)
    assert called

@pytest.mark.asyncio
async def test_retry_reserves_each_attempt_and_timeout_is_not_refunded(sessions):
    _,_,pull,job=await fixture_pull(sessions,["twitter"])
    ctx=BudgetContext(sessions,pull.id,job.id,"twitter","collection","q")
    token=current_budget.set(ctx); ep=current_endpoint.set("/twitter/search")
    calls=0
    async def network():
        nonlocal calls; calls+=1
        if calls==1: raise httpx.ReadTimeout("potentially billed")
        return httpx.Response(200,json={"credits_used":1})
    async def no_wait(delay): pass
    try:
        await ProviderRequestController("socialvault",1,max_retries=1,sleeper=no_wait).run_async(network)
    finally:
        current_budget.reset(token);current_endpoint.reset(ep)
    async with sessions() as db:
        rows=(await db.execute(select(ProviderUsage))).scalars().all()
        assert [r.state for r in rows]==["unknown","reported"]
        assert sum(r.reserved for r in rows)==2
        assert (await usage_summary(db,pull))["credit_cap"] is None

@pytest.mark.asyncio
async def test_reported_cost_change_does_not_stop_future_requests(sessions):
    _,_,pull,job=await fixture_pull(sessions,["twitter"])
    ctx=BudgetContext(sessions,pull.id,job.id,"twitter","collection","q")
    uid=await ctx.reserve("socialvault","/twitter/search")
    await ctx.settle(uid,httpx.Response(200,json={"credits_used":2}))
    assert await ctx.reserve("socialvault","/twitter/search") is not None

@pytest.mark.asyncio
async def test_preview_cache_retains_payload_without_new_reservations(sessions):
    _,_,pull,job=await fixture_pull(sessions)
    preview=BudgetContext(sessions,pull.id,job.id,"twitter","preview","q")
    key=preview.cache_key("/twitter/search",{"query":"transit"})
    await preview.cache(key,{"data":{"posts":[{"id":"p1"}]},"credits_used":1})
    full=BudgetContext(sessions,pull.id,job.id,"twitter","collection","q")
    assert (await full.cached(key))["data"]["posts"][0]["id"]=="p1"
    assert await full.cached(full.cache_key("/twitter/search",{"query":"other"})) is None

@pytest.mark.asyncio
async def test_cancelled_job_cannot_reserve(sessions):
    _,_,pull,job=await fixture_pull(sessions)
    async with sessions() as db:
        stored=await db.get(SearchJob,job.id);stored.status="cancelling";await db.commit()
    with pytest.raises(BudgetStopped,match="cancelled_or_inactive"):
        await BudgetContext(sessions,pull.id,job.id,"twitter","collection","q").reserve("socialvault","/twitter/search")

@pytest.mark.asyncio
async def test_project_dedup_run_membership_and_exclusion_restore(sessions):
    org,project,pull,job=await fixture_pull(sessions,["twitter"])
    raw=({"external_id":"post-1","platform":"twitter","vendor":"socialvault","body":"Transit access","published_at":datetime.now(timezone.utc)},)
    async with sessions() as db:
        first=await db.get(SearchJob,job.id)
        assert (await _persist_platform_posts(db,first,"twitter",raw))[0]==1
        second=SearchJob(project_id=project.id,pull_id=pull.id,name="Second",status="running",
            platforms=["twitter"],platform_allocations={"twitter":100})
        db.add(second);await db.flush()
        assert (await _persist_platform_posts(db,second,"twitter",raw))[0]==1
        assert (await _persist_platform_posts(db,second,"twitter",raw))[0]==0
        await db.commit()
        assert (await db.execute(select(func.count(NormalizedPost.id)))).scalar_one()==1
        assert (await db.execute(select(func.count(RunPost.post_id)))).scalar_one()==2
        post=(await db.execute(select(NormalizedPost))).scalar_one()
        service=PostService(db)
        assert await service.set_exclusion(project.id,post.id,org.id,True)
        assert (await service.list_posts(project.id,org.id)).total==0
        assert (await service.list_posts(project.id,org.id,scope="excluded")).total==1
        assert await service.set_exclusion(project.id,post.id,org.id,False)
        assert (await service.list_posts(project.id,org.id)).total==1
        assert not await service.set_exclusion(project.id,post.id,uuid.uuid4(),True)

@pytest.mark.asyncio
async def test_direct_api_limits_and_preview_full_lifecycle(client, auth_headers, sessions, monkeypatch):
    monkeypatch.setattr("app.workers.tasks.run_collection_job.apply_async",lambda **kwargs:SimpleNamespace(id="mock-task"))
    p=(await client.post("/api/projects",headers=auth_headers,json={"name":"Research"})).json()
    path=f"/api/projects/{p['id']}/jobs"
    body={"name":"Preview","query":"transit","platforms":["x","reddit","youtube"],"requested_post_count":500,"mode":"preview"}
    for key,value in [("requested_post_count",5001),("platforms",["unapproved"])]:
        assert (await client.post(path,headers=auth_headers,json={**body,key:value})).status_code==422
    response=await client.post(path,headers=auth_headers,json=body)
    assert response.status_code==201,response.text
    preview=response.json();assert preview["platforms"]==["twitter","reddit","youtube"]
    async with sessions() as db:
        job=await db.get(SearchJob,uuid.UUID(preview["id"]));job.status="completed";job.completed_at=datetime.now(timezone.utc);await db.commit()
    reused=(await client.post(path,headers=auth_headers,json={**body,"pull_id":preview["pull_id"]})).json()
    assert reused["id"]==preview["id"]
    response=await client.post(path,headers=auth_headers,json={**body,"pull_id":preview["pull_id"],"mode":"collection"})
    assert response.status_code==201,response.text
    assert response.json()["pull_id"]==preview["pull_id"]
    assert response.json()["id"]!=preview["id"]
    assert (await client.post(path,headers=auth_headers,json={**body,"pull_id":preview["pull_id"],"mode":"collection"})).status_code==409

@pytest.mark.asyncio
async def test_real_postgres_concurrent_reservations():
    """Run explicitly with TEST_DATABASE_URL for a disposable socialscope_test database."""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from sqlalchemy.engine import make_url
    from sqlalchemy.schema import CreateSchema, DropSchema
    from app.models import Base
    url=os.environ.get("TEST_DATABASE_URL")
    if not url: pytest.skip("PostgreSQL integration requires TEST_DATABASE_URL; SQLite does not test row locks")
    assert make_url(url).database=="socialscope_test", "Use an isolated socialscope_test database"
    schema="scope_test_"+uuid.uuid4().hex
    admin=create_async_engine(url)
    async with admin.begin() as conn: await conn.execute(CreateSchema(schema))
    engine=create_async_engine(url,connect_args={"server_settings":{"search_path":schema}})
    try:
        async with engine.begin() as conn: await conn.run_sync(Base.metadata.create_all)
        sessions=async_sessionmaker(engine,expire_on_commit=False)
        _,_,pull,job=await fixture_pull(sessions)
        async def reserve(p):
            try: return await BudgetContext(sessions,pull.id,job.id,p,"collection","q").reserve("socialvault",f"/{p}/search")
            except BudgetStopped: return None
        results=await asyncio.gather(*(reserve(p) for p in pull.platforms for _ in range(12)))
        assert sum(r is not None for r in results)==36
        async with sessions() as db:
            assert sum(v["requests"] for v in (await usage_summary(db,pull))["platforms"].values()) == 36
    finally:
        await engine.dispose()
        async with admin.begin() as conn: await conn.execute(DropSchema(schema,cascade=True))
        await admin.dispose()


@pytest.mark.asyncio
async def test_pull_post_ceiling_includes_query_revisions(sessions, monkeypatch):
    monkeypatch.setattr("app.services.budget_service.MAX_PULL_POSTS", 2)
    _, project, pull, first = await fixture_pull(sessions, ["twitter"])
    def raw(i): return {"external_id":str(i), "platform":"twitter", "vendor":"socialvault", "body":"Transit"}
    async with sessions() as db:
        job = await db.get(SearchJob, first.id)
        assert (await _persist_platform_posts(db, job, "twitter", (raw(1), raw(2))))[0] == 2
        second = SearchJob(project_id=project.id, pull_id=pull.id, name="Revised", status="running",
            platforms=["twitter"], platform_allocations={"twitter":100})
        db.add(second); await db.flush()
        assert (await _persist_platform_posts(db, second, "twitter", (raw(2), raw(3))))[0] == 1
        await db.commit()
        assert (await db.execute(select(func.count(NormalizedPost.id)))).scalar_one() == 2
    with pytest.raises(BudgetStopped, match="post_limit"):
        await BudgetContext(sessions,pull.id,first.id,"twitter","collection","q").reserve("socialvault","/twitter/search")


@pytest.mark.asyncio
async def test_active_collection_prevents_project_deletion(sessions):
    from app.services.project_service import ProjectService
    from fastapi import HTTPException
    org, project, _, _ = await fixture_pull(sessions)
    async with sessions() as db:
        with pytest.raises(HTTPException) as caught:
            await ProjectService(db).delete_project(project.id, org.id)
        assert caught.value.status_code == 409
        assert await db.get(Project, project.id) is not None


@pytest.mark.asyncio
async def test_custom_distribution_survives_preview_resume_and_collection(client, auth_headers, sessions, monkeypatch):
    monkeypatch.setattr("app.workers.tasks.run_collection_job.apply_async", lambda **kwargs: SimpleNamespace(id="mock-task"))
    project = (await client.post("/api/projects", headers=auth_headers, json={"name": "Custom distribution"})).json()
    path = f"/api/projects/{project['id']}/jobs"
    body = {"name": "Custom", "query": "transit", "platforms": ["instagram", "tiktok", "facebook"],
            "requested_post_count": 500, "platform_percentages": {"facebook": 50}, "mode": "preview"}
    response = await client.post(path, headers=auth_headers, json=body)
    assert response.status_code == 201, response.text
    preview = response.json()
    assert preview["platform_percentages"] == {"facebook": 50}
    assert preview["platform_allocations"] == {"instagram": 20, "tiktok": 20, "facebook": 20}
    async with sessions() as db:
        stored = await db.get(SearchJob, uuid.UUID(preview["id"]))
        stored.status = "completed"
        stored.completed_at = datetime.now(timezone.utc)
        await db.commit()
    body["pull_id"] = preview["pull_id"]
    reused = (await client.post(path, headers=auth_headers, json=body)).json()
    assert reused["id"] == preview["id"]
    body["platform_percentages"] = {"facebook": 100}
    revised_response = await client.post(path, headers=auth_headers, json=body)
    assert revised_response.status_code == 201, revised_response.text
    revised = revised_response.json()
    assert revised["id"] != preview["id"]
    assert revised["platform_allocations"] == {"instagram": 0, "tiktok": 0, "facebook": 20}
    async with sessions() as db:
        stored = await db.get(SearchJob, uuid.UUID(revised["id"]))
        stored.status = "completed"
        stored.completed_at = datetime.now(timezone.utc)
        await db.commit()
    body.update(mode="collection", platform_percentages={"facebook": 50})
    full_response = await client.post(path, headers=auth_headers, json=body)
    assert full_response.status_code == 201, full_response.text
    full = full_response.json()
    assert full["platform_allocations"] == {"instagram": 78, "tiktok": 172, "facebook": 250}
    runs = (await client.get(path, headers=auth_headers)).json()
    assert next(r for r in runs if r["id"] == full["id"])["platform_percentages"] == {"facebook": 50}


@pytest.mark.asyncio
async def test_zero_allocation_never_calls_provider():
    from app.services.platform_collection import PlatformCollectionRequest, _collect_one
    class ForbiddenRouter:
        async def search(self, **kwargs):
            raise AssertionError("Zero-share platforms must not call the provider")
    result = await _collect_one(ForbiddenRouter(), PlatformCollectionRequest("facebook", "transit", None, None, 0))
    assert result.status == "completed"
    assert result.posts == ()


@pytest.mark.asyncio
async def test_legacy_budget_inputs_are_ignored_and_not_exposed(client, auth_headers, monkeypatch):
    monkeypatch.setattr("app.workers.tasks.run_collection_job.apply_async", lambda **kwargs: SimpleNamespace(id="mock-task"))
    project = (await client.post("/api/projects", headers=auth_headers, json={"name": "No credit caps"})).json()
    response = await client.post(f"/api/projects/{project['id']}/jobs", headers=auth_headers, json={
        "name": "Collection", "query": "transit", "platforms": ["twitter"], "requested_post_count": 500,
        "comparison_limit": 9999, "primary_credit_limit": 9999, "request_limit": 1,
    })
    assert response.status_code == 201, response.text
    assert response.json()["usage"]["credit_cap"] is None
    assert "comparison_remaining" not in response.json()["usage"]
    sources = (await client.get("/api/sources", headers=auth_headers)).json()
    assert "provider credits" in sources["account_limit_warning"]
