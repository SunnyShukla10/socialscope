import csv
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from app.models.export_job import ExportJob
from app.models.normalized_post import NormalizedPost
from app.models.account import Account
from app.models.project import Project
from app.schemas.export import ExportRequest, ExportJobOut
from app.models.user import User
from app.services.activity_service import ActivityService

EXPORTS_DIR = "/tmp/socialscope_exports"
logger = logging.getLogger(__name__)

EXISTING_CSV_COLUMNS = [
    "id",
    "platform",
    "author_username",
    "author_display_name",
    "author_followers",
    "published_at",
    "body",
    "likes",
    "shares",
    "comments",
    "views",
    "engagement_score",
    "hashtags",
    "url",
]
CSV_COLUMNS = EXISTING_CSV_COLUMNS + ["provider", "collected_at", "excluded", "analysis_scope", "collection_context", "known_limitations"]

class ExportService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_export(
        self,
        project_id: uuid.UUID,
        organization_id: uuid.UUID,
        request: ExportRequest,
        actor: User | None = None,
    ) -> ExportJobOut:
        logger.info(
            "Creating export job: project_id=%s format=%s platform=%s",
            project_id,
            request.format,
            request.platform,
        )
        # Verify project
        proj_result = await self.db.execute(
            select(Project).where(
                Project.id == project_id, Project.organization_id == organization_id
            )
        )
        project = proj_result.scalar_one_or_none()
        if not project:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Project not found")

        export_job = ExportJob(
            project_id=project_id,
            format=request.format,
            filters={
                "platform": request.platform,
                "date_from": request.date_from.isoformat() if request.date_from else None,
                "date_to": request.date_to.isoformat() if request.date_to else None,
                "search": request.search,
                "scope": request.scope,
            },
            status="processing",
        )
        self.db.add(export_job)
        await self.db.flush()
        await self.db.refresh(export_job)
        logger.info("Export job created: export_id=%s project_id=%s", export_job.id, project_id)

        # Run export synchronously so the file is available immediately
        try:
            file_path, row_count = await self._generate_csv(
                project_id=project_id,
                export_id=export_job.id,
                platform=request.platform,
                date_from=request.date_from,
                date_to=request.date_to,
                search=request.search,
                scope=request.scope,
            )
            export_job.file_path = file_path
            export_job.row_count = row_count
            export_job.file_size_bytes = os.path.getsize(file_path)
            export_job.status = "completed"
            export_job.completed_at = datetime.now(timezone.utc)
            await ActivityService(self.db).log(
                organization_id=organization_id,
                project_id=project_id,
                actor=actor,
                action="csv_export_generated",
                target_type="export",
                target_id=str(export_job.id),
                target_label=project.name,
                metadata={"format": request.format, "row_count": row_count},
            )
            logger.info(
                "Export job completed: export_id=%s project_id=%s rows=%s",
                export_job.id,
                project_id,
                row_count,
            )
        except Exception as e:
            export_job.status = "failed"
            export_job.error_message = "Export could not be generated. Check API logs using this export ID."
            logger.error("Export job failed: export_id=%s project_id=%s type=%s", export_job.id, project_id, type(e).__name__)

        await self.db.flush()
        await self.db.refresh(export_job)

        return self._to_schema(export_job)

    async def get_export(
        self, export_id: uuid.UUID, project_id: uuid.UUID
    ) -> Optional[ExportJob]:
        result = await self.db.execute(
            select(ExportJob).where(
                ExportJob.id == export_id, ExportJob.project_id == project_id
            )
        )
        return result.scalar_one_or_none()

    async def list_exports(
        self, project_id: uuid.UUID, organization_id: uuid.UUID
    ) -> List[ExportJobOut]:
        logger.info("Listing export jobs: project_id=%s", project_id)
        proj_result = await self.db.execute(
            select(Project).where(
                Project.id == project_id, Project.organization_id == organization_id
            )
        )
        project = proj_result.scalar_one_or_none()
        if not project:
            logger.warning("Export list project not found: project_id=%s", project_id)
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Project not found")

        result = await self.db.execute(
            select(ExportJob)
            .where(ExportJob.project_id == project_id)
            .order_by(ExportJob.created_at.desc())
        )
        exports = [self._to_schema(job) for job in result.scalars().all()]
        logger.info("Listed export jobs: project_id=%s count=%s", project_id, len(exports))
        return exports

    async def _generate_csv(
        self,
        project_id: uuid.UUID,
        export_id: uuid.UUID,
        platform: Optional[List[str]] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        search: Optional[str] = None,
        scope: str = "included",
    ):
        logger.info(
            "Generating export CSV: export_id=%s project_id=%s platform=%s",
            export_id,
            project_id,
            platform,
        )
        conditions = [NormalizedPost.project_id == project_id]
        if scope != "all":
            conditions.append(NormalizedPost.excluded.is_(scope == "excluded"))
        if platform:
            conditions.append(NormalizedPost.platform.in_(platform))
        if date_from:
            conditions.append(NormalizedPost.published_at >= date_from)
        if date_to:
            conditions.append(NormalizedPost.published_at <= date_to)
        if search:
            conditions.append(NormalizedPost.body.ilike(f"%{search}%"))

        result = await self.db.execute(
            select(NormalizedPost, Account)
            .outerjoin(Account, NormalizedPost.account_id == Account.id)
            .where(and_(*conditions))
            .order_by(NormalizedPost.published_at.desc())
        )
        rows = result.all()
        logger.info("Export posts selected: export_id=%s count=%s", export_id, len(rows))

        os.makedirs(EXPORTS_DIR, exist_ok=True)
        file_path = os.path.join(EXPORTS_DIR, f"export_{export_id}.csv")

        from app.models.collection_pull import RunPost
        from app.models.search_job import SearchJob
        from app.models.query_version import QueryVersion
        provenance = (await self.db.execute(select(RunPost.post_id, RunPost.encountered_at, SearchJob, QueryVersion.boolean_query)
            .join(SearchJob, SearchJob.id == RunPost.job_id)
            .join(QueryVersion, QueryVersion.search_job_id == SearchJob.id)
            .where(SearchJob.project_id == project_id, QueryVersion.is_active.is_(True)))).all()
        contexts = {}
        for post_id, encountered_at, run, query in provenance:
            contexts.setdefault(str(post_id), []).append({"run_id": str(run.id), "pull_id": str(run.pull_id),
                "mode": run.mode, "query": query, "date_from": run.date_from.isoformat() if run.date_from else None,
                "date_to": run.date_to.isoformat() if run.date_to else None,
                "encountered_at": encountered_at.isoformat(), "status": run.status})
        self._write_csv(file_path, rows, contexts, scope)

        logger.info("Export CSV written: export_id=%s file_path=%s", export_id, file_path)
        return file_path, len(rows)

    def _write_csv(self, file_path: str, rows, contexts=None, scope="included") -> None:
        # Spreadsheet programs can execute formula-looking cells; quote those as text.
        def safe(value):
            if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
                return "'" + value
            return value
        with open(file_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(CSV_COLUMNS)
            for post, account in rows:
                values = [str(post.id), post.platform, post.author_username, post.author_display_name,
                    post.author_followers, post.published_at.isoformat() if post.published_at else "",
                    post.body, post.likes, post.shares, post.comments, post.views, post.engagement_score,
                    ",".join(str(h) for h in post.hashtags), post.url or "", post.vendor,
                    post.collected_at.isoformat() if post.collected_at else "", post.excluded, scope,
                    json.dumps((contexts or {}).get(str(post.id), [])),
                    "Search results, not a representative sample. Dates do not guarantee full coverage. Missing engagement may be stored as zero."]
                writer.writerow([safe(v) for v in values])

    def _to_schema(self, job: ExportJob) -> ExportJobOut:
        download_url = None
        if job.status == "completed" and job.file_path:
            download_url = f"/api/projects/{job.project_id}/exports/{job.id}/download"
        return ExportJobOut(
            id=job.id,
            project_id=job.project_id,
            status=job.status,
            format=job.format,
            filters=job.filters,
            file_path=job.file_path,
            file_size_bytes=job.file_size_bytes,
            row_count=job.row_count,
            error_message=job.error_message,
            created_at=job.created_at,
            completed_at=job.completed_at,
            download_url=download_url,
        )
