from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
import uuid
from app.database import get_db
from app.schemas.search_job import (
    SearchJobCancellationOut,
    SearchJobCreate,
    SearchJobOut,
)
from app.services.search_service import SearchService
from app.services.auth_service import AuthService

router = APIRouter(prefix="/api/projects/{project_id}/jobs", tags=["search_jobs"])


@router.post("", response_model=SearchJobOut, status_code=status.HTTP_201_CREATED)
async def create_job(
    project_id: uuid.UUID,
    body: SearchJobCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(AuthService.get_current_user),
):
    service = SearchService(db)
    return await service.create_job(project_id, body, current_user.organization_id, actor=current_user)


@router.get("", response_model=List[SearchJobOut])
async def list_jobs(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(AuthService.get_current_user),
):
    service = SearchService(db)
    return await service.list_jobs(project_id, current_user.organization_id)


@router.get("/{job_id}", response_model=SearchJobOut)
async def get_job(
    project_id: uuid.UUID,
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(AuthService.get_current_user),
):
    service = SearchService(db)
    job = await service.get_job(project_id, job_id, current_user.organization_id)
    if not job:
        raise HTTPException(status_code=404, detail="Search job not found")
    return job


@router.post("/{job_id}/cancel", response_model=SearchJobCancellationOut)
async def cancel_job(
    project_id: uuid.UUID,
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(AuthService.get_current_user),
):
    service = SearchService(db)
    result = await service.cancel_job(
        project_id,
        job_id,
        current_user.organization_id,
        current_user,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Search job not found")
    return result
