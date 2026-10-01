from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import uuid
from datetime import datetime
from app.database import get_db
from app.schemas.analytics import (
    AnalyticsSummaryResponse,
    KPIOverview,
    PlatformResponse,
    VolumeResponse,
    WordMapResponse,
)
from app.services.analytics_service import AnalyticsService
from app.services.auth_service import AuthService

router = APIRouter(prefix="/api/projects/{project_id}/analytics", tags=["analytics"])


@router.get("/overview", response_model=KPIOverview)
async def get_overview(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(AuthService.get_current_user),
):
    service = AnalyticsService(db)
    return await service.get_overview(project_id, current_user.organization_id)


@router.get("/volume", response_model=VolumeResponse)
async def get_volume(
    project_id: uuid.UUID,
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(AuthService.get_current_user),
):
    service = AnalyticsService(db)
    return await service.get_volume(
        project_id, current_user.organization_id, date_from, date_to
    )


@router.get("/platforms", response_model=PlatformResponse)
async def get_platforms(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(AuthService.get_current_user),
):
    service = AnalyticsService(db)
    return await service.get_platforms(project_id, current_user.organization_id)


@router.get("/wordmap", response_model=WordMapResponse)
async def get_wordmap(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(AuthService.get_current_user),
):
    service = AnalyticsService(db)
    return await service.get_wordmap(project_id, current_user.organization_id)


