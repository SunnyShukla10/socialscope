from sqlalchemy.ext.asyncio import AsyncSession
from pathlib import Path
from sqlalchemy import select, func, delete
from typing import List, Optional
import uuid
import logging
from app.models.project import Project
from app.models.search_job import SearchJob
from app.models.normalized_post import NormalizedPost
from app.models.export_job import ExportJob
from app.models.activity_event import ActivityEvent
from app.schemas.project import ProjectCreate, ProjectLaunchCreate, ProjectUpdate
from app.models.user import User
from app.services.activity_service import ActivityService
from app.services.search_service import SearchService
from app.services.query_validation import validate_query

logger = logging.getLogger(__name__)


class ProjectService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_projects(self, organization_id: uuid.UUID) -> List[dict]:
        result = await self.db.execute(
            select(Project).where(Project.organization_id == organization_id).order_by(
                Project.created_at.desc()
            )
        )
        projects = result.scalars().all()
        output = []
        for project in projects:
            job_count = await self._count_jobs(project.id)
            post_count = await self._count_posts(project.id)
            p = self._project_dict(project)
            p["job_count"] = job_count
            p["post_count"] = post_count
            output.append(p)
        return output

    async def create_project(
        self, data: ProjectCreate, organization_id: uuid.UUID, actor: User | None = None
    ) -> dict:
        settings = {
            "research_question": data.research_question,
            "boolean_query": data.boolean_query,
            "target_platforms": data.platforms or [],
            "date_from": data.date_from,
            "date_to": data.date_to,
            "max_results_per_platform": data.max_results_per_platform,
        }
        settings = {k: v for k, v in settings.items() if v not in (None, [], "")}
        project = Project(
            organization_id=organization_id,
            name=data.name,
            description=data.description,
            domain=data.domain,
            settings=settings,
        )
        self.db.add(project)
        await self.db.flush()
        await ActivityService(self.db).log(
            organization_id=organization_id,
            project_id=project.id,
            actor=actor,
            action="project_created",
            target_type="project",
            target_id=str(project.id),
            target_label=project.name,
        )
        await self.db.refresh(project)
        p = self._project_dict(project)
        p["job_count"] = 0
        p["post_count"] = 0
        return p

    async def launch_project(
        self, data: ProjectLaunchCreate, organization_id: uuid.UUID, actor: User | None = None
    ) -> dict:
        validate_query(data.initial_job.query, data.initial_job.platforms)
        project = await self.create_project(data, organization_id, actor=actor)
        await SearchService(self.db).create_job(
            project["id"],
            data.initial_job,
            organization_id,
            actor=actor,
        )
        launched_project = await self.get_project(project["id"], organization_id)
        return launched_project or project

    async def get_project(
        self, project_id: uuid.UUID, organization_id: uuid.UUID
    ) -> Optional[dict]:
        result = await self.db.execute(
            select(Project).where(
                Project.id == project_id,
                Project.organization_id == organization_id,
            )
        )
        project = result.scalar_one_or_none()
        if not project:
            return None
        p = self._project_dict(project)
        p["job_count"] = await self._count_jobs(project.id)
        p["post_count"] = await self._count_posts(project.id)
        return p

    async def update_project(
        self, project_id: uuid.UUID, data: ProjectUpdate, organization_id: uuid.UUID
    ) -> Optional[dict]:
        result = await self.db.execute(
            select(Project).where(
                Project.id == project_id,
                Project.organization_id == organization_id,
            )
        )
        project = result.scalar_one_or_none()
        if not project:
            return None
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(project, key, value)
        await self.db.flush()
        await self.db.refresh(project)
        p = self._project_dict(project)
        p["job_count"] = await self._count_jobs(project.id)
        p["post_count"] = await self._count_posts(project.id)
        return p

    async def delete_project(
        self, project_id: uuid.UUID, organization_id: uuid.UUID
    ) -> bool:
        result = await self.db.execute(
            select(Project).where(
                Project.id == project_id,
                Project.organization_id == organization_id,
            )
        )
        project = result.scalar_one_or_none()
        if not project:
            return False

        active = (await self.db.execute(select(SearchJob.id).where(
            SearchJob.project_id == project_id,
            SearchJob.status.in_(["pending", "queued", "running", "cancelling"])
        ).limit(1))).scalar_one_or_none()
        if active:
            from fastapi import HTTPException
            raise HTTPException(409, "Cancel active collections and wait for them to finish before deleting this project")

        export_result = await self.db.execute(
            select(ExportJob.file_path).where(ExportJob.project_id == project_id)
        )
        for file_path in export_result.scalars().all():
            if not file_path:
                continue
            try:
                Path(file_path).unlink(missing_ok=True)
            except OSError:
                logger.warning("Failed to remove export file during project delete: %s", file_path)

        await self.db.execute(delete(ActivityEvent).where(ActivityEvent.project_id == project_id))
        await self.db.execute(
            delete(Project).where(
                Project.id == project_id,
                Project.organization_id == organization_id,
            )
        )
        return True

    async def _count_jobs(self, project_id: uuid.UUID) -> int:
        result = await self.db.execute(
            select(func.count()).where(SearchJob.project_id == project_id)
        )
        return result.scalar_one()

    async def _count_posts(self, project_id: uuid.UUID) -> int:
        result = await self.db.execute(
            select(func.count()).where(NormalizedPost.project_id == project_id)
        )
        return result.scalar_one()

    def _project_dict(self, project: Project) -> dict:
        settings = project.settings or {}
        return {
            **project.__dict__.copy(),
            "research_question": settings.get("research_question"),
            "boolean_query": settings.get("boolean_query"),
            "platforms": settings.get("target_platforms") or settings.get("platforms") or [],
            "date_from": settings.get("date_from"),
            "date_to": settings.get("date_to"),
            "max_results_per_platform": settings.get("max_results_per_platform"),
        }
