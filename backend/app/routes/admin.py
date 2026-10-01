from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.schemas.activity import ActivityEventOut
from app.schemas.admin import AdminOverview, ApiKeyStatus
from app.services.activity_service import ActivityService
from app.services.auth_service import AuthService

router = APIRouter(prefix="/api/admin", tags=["admin"])


def require_admin(current_user=Depends(AuthService.get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user


def _mask(value: str | None) -> str | None:
    if not value:
        return None
    return "Configured (hidden)"


def _api_key_statuses() -> list[ApiKeyStatus]:
    items = [
        ("xpoz", "Xpoz API Key", settings.XPOZ_API_KEY),
        ("socialvault", "SocialVault API Key", settings.SOCIALVAULT_API_KEY),
        ("openai", "OpenAI API Key", settings.OPENAI_API_KEY),
    ]
    return [
        ApiKeyStatus(
            key=key,
            label=label,
            status="present" if value else "missing",
            masked_value=_mask(value),
        )
        for key, label, value in items
    ]


@router.get("/audit-log", response_model=list[ActivityEventOut])
async def audit_log(
    limit: int = Query(100, ge=1, le=250),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin),
):
    return await ActivityService(db).latest(current_user.organization_id, limit=limit)


@router.get("/overview", response_model=AdminOverview)
async def admin_overview(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin),
):
    return AdminOverview(
        api_keys=_api_key_statuses(),
        audit_log=await ActivityService(db).latest(current_user.organization_id, limit=100),
    )
