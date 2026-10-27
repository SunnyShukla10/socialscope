"""Authenticated submission only; reports are read through admin routes."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.feedback import Feedback
from app.schemas.pilot import FeedbackCreate
from app.services.auth_service import AuthService

router = APIRouter(prefix="/api/feedback", tags=["feedback"])


@router.post("", status_code=201)
async def submit_feedback(body: FeedbackCreate, db: AsyncSession = Depends(get_db),
                          user=Depends(AuthService.get_current_user)):
    report = Feedback(
        organization_id=user.organization_id, user_id=user.id, submitter_label=user.email,
        kind=body.kind, message=body.message, page_path=body.page_path,
    )
    db.add(report)
    await db.flush()
    return {"id": report.id}
