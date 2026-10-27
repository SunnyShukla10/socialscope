"""Project ownership checks shared by list/dashboard queries and API routes."""
import uuid
from fastapi import Depends, HTTPException
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.project import Project
from app.services.auth_service import AuthService


def visible_projects(organization_id, user):
    ownership = Project.owner_user_id == user.id
    # Preserve access to legacy/unassigned data for organization administrators only.
    if user.role == "admin":
        ownership = or_(ownership, Project.owner_user_id.is_(None))
    return and_(Project.organization_id == organization_id, ownership)


async def require_owned_project(project_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                                user=Depends(AuthService.get_current_user)):
    project = await db.scalar(select(Project).where(Project.id == project_id,
        visible_projects(user.organization_id, user)))
    if project is None:
        raise HTTPException(404, "Project not found")
    return project
