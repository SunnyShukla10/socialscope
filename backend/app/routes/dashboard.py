from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.dashboard import DashboardSummary
from app.services.auth_service import AuthService
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
async def get_dashboard_summary(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(AuthService.get_current_user),
):
    return await DashboardService(db).get_summary(current_user.organization_id)


@router.get("/stats", response_model=DashboardSummary)
async def get_dashboard_stats_compat(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(AuthService.get_current_user),
):
    return await DashboardService(db).get_summary(current_user.organization_id)
