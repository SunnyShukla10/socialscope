from fastapi import APIRouter, Depends, HTTPException, Query, status, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid

from app.config import settings
from app.database import get_db
from app.schemas.activity import ActivityEventOut
from app.schemas.admin import AdminOverview, ApiKeyStatus
from app.services.activity_service import ActivityService
from app.services.auth_service import AuthService
from app.models.user import User
from app.models.feedback import Feedback
from app.schemas.pilot import MemberCreate, AdminUserOut, UserStatus, FeedbackOut, FeedbackReview
from app.services.user_service import create_member, set_user_status, delete_member

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
    offset: int = Query(0, ge=0),
    user_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin),
):
    return await ActivityService(db).latest(current_user.organization_id, limit=limit, offset=offset, user_id=user_id)


@router.get("/overview", response_model=AdminOverview)
async def admin_overview(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin),
):
    return AdminOverview(
        api_keys=_api_key_statuses(),
        audit_log=await ActivityService(db).latest(current_user.organization_id, limit=100),
    )


@router.get("/users", response_model=list[AdminUserOut])
async def list_users(limit: int = Query(100, ge=1, le=200), offset: int = Query(0, ge=0),
                     db: AsyncSession = Depends(get_db), admin=Depends(require_admin)):
    return list((await db.scalars(select(User).where(User.organization_id == admin.organization_id)
        .order_by(User.email, User.id).offset(offset).limit(limit))).all())


@router.post("/users", response_model=AdminUserOut, status_code=201)
async def add_user(body: MemberCreate, db: AsyncSession = Depends(get_db), admin=Depends(require_admin)):
    return await create_member(db, admin, body)


@router.patch("/users/{user_id}", response_model=AdminUserOut)
async def change_status(user_id: uuid.UUID, body: UserStatus,
                        db: AsyncSession = Depends(get_db), admin=Depends(require_admin)):
    return await set_user_status(db, admin, user_id, body.is_active)


@router.get("/feedback", response_model=list[FeedbackOut])
async def list_feedback(limit: int = Query(25, ge=1, le=100), offset: int = Query(0, ge=0),
                        db: AsyncSession = Depends(get_db), admin=Depends(require_admin)):
    return list((await db.scalars(select(Feedback).where(Feedback.organization_id == admin.organization_id)
        .order_by(Feedback.created_at.desc(), Feedback.id.desc()).offset(offset).limit(limit))).all())


@router.patch("/feedback/{feedback_id}", response_model=FeedbackOut)
async def review_feedback(feedback_id: uuid.UUID, body: FeedbackReview,
                          db: AsyncSession = Depends(get_db), admin=Depends(require_admin)):
    report = await db.scalar(select(Feedback).where(Feedback.id == feedback_id,
        Feedback.organization_id == admin.organization_id))
    if not report:
        raise HTTPException(404, "Feedback not found")
    report.reviewed = body.reviewed
    return report


@router.delete("/users/{user_id}", status_code=204)
async def remove_user(user_id: uuid.UUID, db: AsyncSession = Depends(get_db), admin=Depends(require_admin)):
    await delete_member(db, admin, user_id)
    return Response(status_code=204)
