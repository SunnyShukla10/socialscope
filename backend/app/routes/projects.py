from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
import uuid
from app.database import get_db
from app.schemas.project import ProjectCreate, ProjectLaunchCreate, ProjectUpdate, ProjectOut
from app.services.project_service import ProjectService
from app.services.auth_service import AuthService

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("", response_model=List[ProjectOut])
async def list_projects(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(AuthService.get_current_user),
):
    service = ProjectService(db)
    return await service.list_projects(current_user.organization_id)


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
async def create_project(
    body: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(AuthService.get_current_user),
):
    service = ProjectService(db)
    return await service.create_project(body, current_user.organization_id, actor=current_user)


@router.post("/launch", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
async def launch_project(
    body: ProjectLaunchCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(AuthService.get_current_user),
):
    service = ProjectService(db)
    return await service.launch_project(body, current_user.organization_id, actor=current_user)


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(AuthService.get_current_user),
):
    service = ProjectService(db)
    project = await service.get_project(project_id, current_user.organization_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.patch("/{project_id}", response_model=ProjectOut)
async def update_project(
    project_id: uuid.UUID,
    body: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(AuthService.get_current_user),
):
    service = ProjectService(db)
    project = await service.update_project(project_id, body, current_user.organization_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(AuthService.get_current_user),
):
    service = ProjectService(db)
    deleted = await service.delete_project(project_id, current_user.organization_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Project not found")
