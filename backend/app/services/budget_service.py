"""Credit reservations are serialized by a PostgreSQL pull row lock.

No automatic refunds: ambiguous failures and worker crashes retain their debit.
SociaVault prices are endpoint-specific documented maxima (docs checked 2026-09-28).
Xpoz operations have request safeguards only; its internal billing is unbounded here.
"""
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
import hashlib
import json
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert
from app.models.collection_pull import CollectionPull, ProviderUsage, ProviderCache, RunPost

COMPARISON = ("twitter", "reddit", "youtube")
COSTS = {
    "/twitter/search": 1, "/reddit/search": 1, "/youtube/search": 1,
    "/tiktok/search/keyword": 1, "/google/search": 1, "/facebook/group/posts": 1, "/facebook/profile/posts": 1,
}
PREVIEW_REQUESTS = {"facebook": 2, "instagram": 3}
FRESH_SECONDS = 900
MAX_PULL_POSTS = 5000
current_budget: ContextVar = ContextVar("collection_budget", default=None)
current_endpoint: ContextVar = ContextVar("provider_endpoint", default="sdk_operation")


class BudgetStopped(Exception):
    """Safe, displayable explanation. Never contains provider exception text."""


def comparison_allocations(platforms, limit):
    selected = [p for p in COMPARISON if p in platforms]
    return {p: limit // len(selected) + (i < limit % len(selected))
            for i, p in enumerate(selected)} if selected else {}


def charged(row):
    return max(row.reserved, row.reported or 0)


@dataclass
class BudgetContext:
    sessions: object
    pull_id: object
    job_id: object
    platform: str
    mode: str
    fingerprint: str
    stop_reason: str | None = None
    metrics: dict = field(default_factory=dict)

    def stop(self, reason):
        self.stop_reason = reason
        raise BudgetStopped(reason)

    async def reserve(self, provider, endpoint):
        if provider == "socialvault":
            if endpoint not in COSTS:
                self.stop("unsupported_cost: endpoint has no verified maximum cost")
            cost = COSTS[endpoint]
        elif provider == "xpoz" and self.platform not in COMPARISON:
            cost = 0  # NOT a claim that Xpoz is free; credits remain unknown.
        else:
            self.stop("unsupported_cost: provider is not approved for this budget")
        async with self.sessions() as db:
            pull = (await db.execute(select(CollectionPull).where(
                CollectionPull.id == self.pull_id).with_for_update())).scalar_one()
            from app.models.search_job import SearchJob
            job = await db.get(SearchJob, self.job_id)
            if not job or job.status not in {"running", "queued", "pending"}:
                self.stop("cancelled_or_inactive: no further requests allowed")
            accepted = (await db.execute(select(func.count(func.distinct(RunPost.post_id)))
                .join(SearchJob, SearchJob.id == RunPost.job_id)
                .where(SearchJob.pull_id == self.pull_id))).scalar_one()
            if accepted >= MAX_PULL_POSTS:
                self.stop("post_limit: pull has reached 5000 unique posts including previews")
            rows = (await db.execute(select(ProviderUsage).where(
                ProviderUsage.pull_id == self.pull_id))).scalars().all()
            if any(r.reported is not None and r.reported > r.reserved for r in rows):
                self.stop("cost_schedule_changed: reported cost exceeded reservation; review pricing")
            own = [r for r in rows if r.platform == self.platform]
            if len(own) >= pull.request_limit:
                self.stop("request_limit: pull request allowance exhausted")
            if self.mode == "preview" and sum(r.job_id == self.job_id for r in own) >= PREVIEW_REQUESTS.get(self.platform, 1):
                self.stop("preview_limit: small search preview allowance reached")
            if self.platform in COMPARISON:
                used = sum(charged(r) for r in rows if r.platform in COMPARISON)
                if used + cost > pull.comparison_limit:
                    self.stop("comparison_budget: shared comparison allowance exhausted")
            if provider == "socialvault" and sum(charged(r) for r in own) + cost > pull.platform_limits.get(self.platform, 0):
                self.stop("platform_budget: remaining allocation cannot fund this request")
            usage = ProviderUsage(pull_id=self.pull_id, job_id=self.job_id,
                platform=self.platform, provider=provider, endpoint=endpoint, reserved=cost)
            db.add(usage)
            await db.commit()  # Durable before any network operation.
            return usage.id

    async def settle(self, usage_id, result=None, unknown=False):
        async with self.sessions() as db:
            row = (await db.execute(select(ProviderUsage).where(
                ProviderUsage.id == usage_id).with_for_update())).scalar_one()
            row.state = "unknown" if unknown or row.provider == "xpoz" else "estimated"
            row.estimated = row.reserved if row.provider == "socialvault" and not unknown else None
            try:
                payload = result.json()
                reported = payload.get("credits_used")
                if isinstance(reported, int) and not isinstance(reported, bool) and reported >= 0:
                    row.reported = reported
                    row.state = "reported"
            except (AttributeError, ValueError, TypeError):
                pass
            await db.commit()

    async def execute(self, provider, endpoint, operation):
        usage_id = await self.reserve(provider, endpoint)
        try:
            result = await operation()
        except BaseException:
            await self.settle(usage_id, unknown=True)
            raise
        await self.settle(usage_id, result=result)
        return result

    def cache_key(self, endpoint, params):
        return hashlib.sha256(json.dumps([self.fingerprint, self.platform, endpoint, params],
            sort_keys=True, default=str).encode()).hexdigest()

    async def cached(self, key):
        async with self.sessions() as db:
            row = await db.get(ProviderCache, (self.pull_id, key))
            if row and (row.created_at.replace(tzinfo=timezone.utc) if row.created_at.tzinfo is None else row.created_at) >= datetime.now(timezone.utc) - timedelta(seconds=FRESH_SECONDS):
                return row.payload
        return None

    async def cache(self, key, payload):
        async with self.sessions() as db:
            await db.execute(insert(ProviderCache).values(pull_id=self.pull_id, key=key,
                payload=payload).on_conflict_do_update(index_elements=["pull_id", "key"],
                set_={"payload": payload, "created_at": datetime.now(timezone.utc)}))
            await db.commit()


async def usage_summary(db, pull):
    rows = (await db.execute(select(ProviderUsage).where(ProviderUsage.pull_id == pull.id))).scalars().all()
    by_platform = {}
    for platform in pull.platforms:
        own = [r for r in rows if r.platform == platform]
        by_platform[platform] = {
            "requests": len(own), "reserved": sum(r.reserved for r in own if r.state == "reserved"),
            "estimated": sum(r.estimated or 0 for r in own if r.state == "estimated"),
            "reported": sum(r.reported or 0 for r in own),
            "unknown_requests": sum(r.state in {"reserved", "unknown"} for r in own),
            "charged_allowance": sum(charged(r) for r in own),
            "credit_limit": pull.platform_limits.get(platform),
            "credits_bounded": platform != "instagram",
        }
    used = sum(charged(r) for r in rows if r.platform in COMPARISON)
    return {"pull_id": str(pull.id), "comparison_limit": pull.comparison_limit,
        "comparison_remaining": max(0, pull.comparison_limit - used),
        "request_limit_per_platform": pull.request_limit, "platforms": by_platform,
        "scope": "This installation and pull only; shared provider account usage is not globally capped."}
