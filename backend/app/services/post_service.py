from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from typing import List, Optional
import logging
import uuid
from datetime import datetime
from app.models.normalized_post import NormalizedPost
from app.models.project import Project
from app.schemas.post import PostListResponse, PostOut

logger = logging.getLogger(__name__)


class PostService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_posts(
        self,
        project_id: uuid.UUID,
        organization_id: uuid.UUID,
        platform: Optional[List[str]] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        search: Optional[str] = None,
        sort_by: str = "date",
        page: int = 1,
        per_page: int = 25,
        scope: str = "included",
        run_id: Optional[uuid.UUID] = None,
    ) -> PostListResponse:
        logger.info(
            "Listing posts: project_id=%s page=%s per_page=%s platform=%s",
            project_id,
            page,
            per_page,
            platform,
        )
        # Verify project belongs to org
        proj_result = await self.db.execute(
            select(Project).where(
                Project.id == project_id, Project.organization_id == organization_id
            )
        )
        project = proj_result.scalar_one_or_none()
        if not project:
            logger.warning("Posts project not found: project_id=%s", project_id)
            return PostListResponse(items=[], total=0, page=page, per_page=per_page, total_pages=0)

        conditions = [NormalizedPost.project_id == project_id]
        if scope != "all":
            conditions.append(NormalizedPost.excluded.is_(scope == "excluded"))
        if run_id:
            from app.models.collection_pull import RunPost
            conditions.append(NormalizedPost.id.in_(select(RunPost.post_id).where(RunPost.job_id == run_id)))

        if platform:
            conditions.append(NormalizedPost.platform.in_(platform))
        if date_from:
            conditions.append(NormalizedPost.published_at >= date_from)
        if date_to:
            conditions.append(NormalizedPost.published_at <= date_to)
        if search:
            conditions.append(NormalizedPost.body.ilike(f"%{search}%"))

        where_clause = and_(*conditions)

        # Count total
        count_result = await self.db.execute(
            select(func.count()).select_from(NormalizedPost).where(where_clause)
        )
        total = count_result.scalar_one()

        engagement_total = (
            func.coalesce(NormalizedPost.likes, 0)
            + func.coalesce(NormalizedPost.comments, 0)
            + func.coalesce(NormalizedPost.views, 0)
            + func.coalesce(NormalizedPost.shares, 0)
        )

        if sort_by in ("engagement", "most_engaged"):
            order_col = engagement_total.desc()
        elif sort_by == "oldest":
            order_col = NormalizedPost.published_at.asc()
        else:
            order_col = NormalizedPost.published_at.desc()

        offset = (page - 1) * per_page
        result = await self.db.execute(
            select(NormalizedPost)
            .where(where_clause)
            .order_by(order_col)
            .offset(offset)
            .limit(per_page)
        )
        rows = result.scalars().all()
        logger.info("Posts selected: project_id=%s count=%s total=%s", project_id, len(rows), total)

        total_pages = (total + per_page - 1) // per_page if total > 0 else 0

        return PostListResponse(
            items=[PostOut.model_validate(p) for p in rows],
            total=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages,
        )

    async def set_exclusion(
        self,
        project_id: uuid.UUID,
        post_id: uuid.UUID,
        organization_id: uuid.UUID,
        excluded: bool,
    ) -> bool:
        result = await self.db.execute(
            select(NormalizedPost)
            .join(Project, Project.id == NormalizedPost.project_id)
            .where(
                NormalizedPost.id == post_id,
                NormalizedPost.project_id == project_id,
                Project.organization_id == organization_id,
            )
        )
        post = result.scalar_one_or_none()
        if not post:
            return False
        post.excluded = excluded
        await self.db.flush()
        logger.info("Updated exclusion: project_id=%s post_id=%s", project_id, post_id)
        return True
