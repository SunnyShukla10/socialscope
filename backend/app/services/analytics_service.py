from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from typing import Optional, List
import uuid
import re
import string
import unicodedata
import math
from datetime import datetime, timedelta
from collections import Counter, defaultdict
from app.models.normalized_post import NormalizedPost
from app.models.project import Project
from app.schemas.analytics import (
    KPIOverview,
    VolumeResponse,
    VolumeDataPoint,
    PlatformResponse,
    PlatformDataPoint,
    WordMapResponse,
    WordMapNode,
    WordMapEdge,
)


HASHTAG_RE = re.compile(r"(?<!\w)#([\w][\w\-]*)", re.UNICODE)
URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
MENTION_RE = re.compile(r"@\w+", re.UNICODE)
TOKEN_RE = re.compile(r"[a-z][a-z0-9']*", re.IGNORECASE)
STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "but", "by", "can", "do",
    "for", "from", "had", "has", "have", "he", "her", "his", "how", "i", "if",
    "in", "is", "it", "its", "me", "my", "not", "of", "on", "or", "our",
    "she", "so", "than", "that", "the", "their", "them", "then", "there", "this",
    "to", "up", "was", "we", "were", "what", "when", "with", "you", "your",
    "rt", "amp", "via", "http", "https", "t", "co", "com", "www",
    "like", "just", "really", "thing", "get", "got", "know",
}


class AnalyticsService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _verify_project(self, project_id: uuid.UUID, organization_id: uuid.UUID) -> bool:
        result = await self.db.execute(
            select(Project).where(
                Project.id == project_id, Project.organization_id == organization_id
            )
        )
        return result.scalar_one_or_none() is not None

    async def get_overview(self, project_id: uuid.UUID, organization_id: uuid.UUID) -> KPIOverview:
        if not await self._verify_project(project_id, organization_id):
            return KPIOverview(
                total_posts=0,
                unique_authors=0,
                platforms_count=0,
                top_hashtags=[],
                total_engagement=0,
            )

        result = await self.db.execute(
            select(NormalizedPost).where(NormalizedPost.project_id == project_id, NormalizedPost.excluded.is_(False))
        )
        posts = result.scalars().all()

        if not posts:
            return KPIOverview(
                total_posts=0,
                unique_authors=0,
                platforms_count=0,
                top_hashtags=[],
                total_engagement=0,
            )

        total = len(posts)
        unique_authors = len(
            {
                str(post.account_id) if post.account_id else f"{post.platform}:{post.author_username}"
                for post in posts
                if post.account_id or post.author_username
            }
        )
        platforms = set(p.platform for p in posts)
        total_engagement = sum(p.likes + p.shares + p.comments for p in posts)

        hashtag_counts = Counter()
        hashtag_display: dict[str, str] = {}
        for post in posts:
            for normalized, display in self.extract_hashtags(post.body, post.hashtags):
                hashtag_counts[normalized] += 1
                hashtag_display.setdefault(normalized, display)

        top_hashtags = sorted(
            [
                {"tag": hashtag_display.get(tag, f"#{tag}"), "hashtag": hashtag_display.get(tag, f"#{tag}"), "count": count}
                for tag, count in hashtag_counts.items()
            ],
            key=lambda x: (-x["count"], x["tag"]),
        )[:10]

        return KPIOverview(
            total_posts=total,
            unique_authors=unique_authors,
            platforms_count=len(platforms),
            top_hashtags=top_hashtags,
            total_engagement=total_engagement,
        )

    async def get_volume(
        self,
        project_id: uuid.UUID,
        organization_id: uuid.UUID,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> VolumeResponse:
        if not await self._verify_project(project_id, organization_id):
            return VolumeResponse(data=[], platforms=[])

        conditions = [NormalizedPost.project_id == project_id, NormalizedPost.excluded.is_(False)]
        if date_from:
            conditions.append(NormalizedPost.published_at >= date_from)
        if date_to:
            conditions.append(NormalizedPost.published_at <= date_to)

        result = await self.db.execute(
            select(NormalizedPost.published_at, NormalizedPost.platform).where(
                and_(*conditions)
            )
        )
        rows = result.all()

        if not rows:
            return VolumeResponse(data=[], platforms=[])

        # Group by date and platform, then fill a complete date/platform grid.
        counts: dict = defaultdict(int)
        platforms_seen = set()
        dates_seen = []
        for pub_at, platform in rows:
            if pub_at:
                date_value = pub_at.date()
                date_str = date_value.strftime("%Y-%m-%d")
                counts[(date_str, platform)] += 1
                platforms_seen.add(platform)
                dates_seen.append(date_value)

        if not platforms_seen or not dates_seen:
            return VolumeResponse(data=[], platforms=[])

        start_date = date_from.date() if date_from else min(dates_seen)
        end_date = date_to.date() if date_to else max(dates_seen)
        if end_date < start_date:
            return VolumeResponse(data=[], platforms=sorted(platforms_seen))

        platforms = sorted(platforms_seen)
        all_dates = [
            (start_date + timedelta(days=offset)).strftime("%Y-%m-%d")
            for offset in range((end_date - start_date).days + 1)
        ]

        data = [
            VolumeDataPoint(date=date_str, platform=platform, count=counts.get((date_str, platform), 0))
            for date_str in all_dates
            for platform in platforms
        ]
        return VolumeResponse(data=data, platforms=platforms)

    async def get_platforms(
        self, project_id: uuid.UUID, organization_id: uuid.UUID
    ) -> PlatformResponse:
        if not await self._verify_project(project_id, organization_id):
            return PlatformResponse(data=[])

        result = await self.db.execute(
            select(
                NormalizedPost.platform,
                func.count(NormalizedPost.id).label("post_count"),
                func.sum(
                    NormalizedPost.likes + NormalizedPost.shares + NormalizedPost.comments
                ).label("total_engagement"),
            )
            .where(NormalizedPost.project_id == project_id, NormalizedPost.excluded.is_(False))
            .group_by(NormalizedPost.platform)
        )
        rows = result.all()

        data = [
            PlatformDataPoint(
                platform=row.platform,
                post_count=row.post_count,
                total_engagement=int(row.total_engagement or 0),
            )
            for row in rows
        ]
        return PlatformResponse(data=data)

    async def get_wordmap(
        self,
        project_id: uuid.UUID,
        organization_id: uuid.UUID,
        node_limit: int = 50,
        edge_limit: int = 100,
    ) -> WordMapResponse:
        if not await self._verify_project(project_id, organization_id):
            return WordMapResponse(nodes=[], edges=[])

        result = await self.db.execute(
            select(NormalizedPost.body).where(NormalizedPost.project_id == project_id, NormalizedPost.excluded.is_(False))
        )
        bodies = [row[0] for row in result.all() if row[0]]
        token_counts: Counter[str] = Counter()
        pair_counts: Counter[tuple[str, str]] = Counter()

        for body in bodies:
            tokens = self.tokenize_for_wordmap(body)
            token_counts.update(tokens)
            for index, token in enumerate(tokens):
                end = min(len(tokens), index + 3)
                for other in tokens[index + 1:end]:
                    if token == other:
                        continue
                    pair = tuple(sorted((token, other)))
                    pair_counts[pair] += 1

        sorted_pairs = sorted(pair_counts.items(), key=lambda item: (-item[1], item[0][0], item[0][1]))
        top_pair_count = self._top_cooccurrence_pair_count(len(sorted_pairs))
        top_pairs = sorted_pairs[:top_pair_count]

        node_weights: Counter[str] = Counter()
        edges = []
        for (a, b), count in top_pairs:
            node_weights[a] += count
            node_weights[b] += count
            edges.append(WordMapEdge(source=a, target=b, count=count, weight=count))

        edge_nodes = {edge.source for edge in edges} | {edge.target for edge in edges}
        nodes = [
            WordMapNode(id=token, label=token, count=count, value=count)
            for token, count in sorted(node_weights.items(), key=lambda item: (-item[1], item[0]))
            if token in edge_nodes
        ]
        return WordMapResponse(nodes=nodes, edges=edges)

    def _top_cooccurrence_pair_count(self, pair_count: int) -> int:
        if pair_count <= 0:
            return 0
        return max(1, math.ceil(pair_count * 0.25))

    def extract_hashtags(self, body: str | None, stored_hashtags: list | None = None) -> list[tuple[str, str]]:
        raw_tags = []
        for tag in stored_hashtags or []:
            raw_tags.append(str(tag))
        raw_tags.extend(f"#{match.group(1)}" for match in HASHTAG_RE.finditer(body or ""))

        seen: set[str] = set()
        output: list[tuple[str, str]] = []
        for raw in raw_tags:
            normalized = self.normalize_hashtag(raw)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            output.append((normalized, f"#{normalized}"))
        return output

    def normalize_hashtag(self, value: str) -> str:
        text = unicodedata.normalize("NFKC", value or "").strip().lstrip("#")
        text = text.strip(string.punctuation + " \t\r\n").lower()
        text = re.sub(r"[^\w\-]", "", text, flags=re.UNICODE)
        text = text.replace("-", "")
        if not text:
            return ""
        return self._simple_lemma(text)

    def tokenize_for_wordmap(self, text: str) -> list[str]:
        normalized = unicodedata.normalize("NFKC", text or "").lower()
        normalized = URL_RE.sub(" ", normalized)
        normalized = MENTION_RE.sub(" ", normalized)
        normalized = normalized.translate(str.maketrans({p: " " for p in string.punctuation if p != "#"}))
        tokens = []
        for match in TOKEN_RE.finditer(normalized):
            token = self._simple_lemma(match.group(0).strip("'"))
            if len(token) < 3 or token.isnumeric() or token in STOPWORDS or not any(char.isalpha() for char in token):
                continue
            tokens.append(token)
        return tokens

    def _simple_lemma(self, token: str) -> str:
        if len(token) > 4 and token.endswith("ies"):
            return token[:-3] + "y"
        if len(token) > 5 and token.endswith("ments"):
            return token[:-1]
        if len(token) > 4 and token.endswith("s") and not token.endswith(("ss", "is")):
            return token[:-1]
        return token
