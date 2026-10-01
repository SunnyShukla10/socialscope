from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Literal
from pydantic import BaseModel
import logging
import uuid
from datetime import datetime
from app.database import get_db
from app.schemas.post import PostListResponse
from app.services.post_service import PostService
from app.services.auth_service import AuthService

router = APIRouter(prefix="/api/projects/{project_id}/posts", tags=["posts"])
logger = logging.getLogger(__name__)


@router.get("", response_model=PostListResponse)
async def list_posts(
    project_id: uuid.UUID,
    platform: Optional[List[str]] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    search: Optional[str] = Query(None),
    sort_by: str = Query("date"),
    scope: Literal["included", "excluded", "all"] = Query("included"),
    run_id: Optional[uuid.UUID] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(AuthService.get_current_user),
):
    logger.info(
        "List posts request: project_id=%s user_id=%s page=%s per_page=%s sort_by=%s",
        project_id,
        getattr(current_user, "id", None),
        page,
        per_page,
        sort_by,
    )
    service = PostService(db)
    try:
        response = await service.list_posts(
            project_id=project_id,
            organization_id=current_user.organization_id,
            platform=platform,
            date_from=date_from,
            date_to=date_to,
            search=search,
            sort_by=sort_by,
            page=page,
            per_page=per_page,
            scope=scope, run_id=run_id,
        )
    except Exception:
        logger.exception("List posts failed: project_id=%s", project_id)
        raise
    logger.info(
        "List posts succeeded: project_id=%s count=%s total=%s",
        project_id,
        len(response.items),
        response.total,
    )
    return response


class ExclusionRequest(BaseModel):
    excluded: bool

@router.patch("/{post_id}/exclusion")
async def set_exclusion(project_id: uuid.UUID, post_id: uuid.UUID, body: ExclusionRequest,
    db: AsyncSession = Depends(get_db), current_user=Depends(AuthService.get_current_user)):
    changed = await PostService(db).set_exclusion(project_id, post_id, current_user.organization_id, body.excluded)
    if not changed:
        raise HTTPException(404, "Post not found")
    return {"id": post_id, "excluded": body.excluded}
