import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas.query import QueryGenerateRequest, QueryGenerateResponse
from app.services.query_service import QueryService
from app.services.auth_service import AuthService

router = APIRouter(prefix="/api/llm", tags=["queries"])
logger = logging.getLogger(__name__)


@router.post("/generate-queries", response_model=QueryGenerateResponse)
async def generate_queries(
    body: QueryGenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(AuthService.get_current_user),
):
    logger.info(
        "Generate queries request: user_id=%s domain=%s question_length=%s",
        getattr(current_user, "id", None),
        body.domain,
        len(body.research_question),
    )
    service = QueryService()
    try:
        candidates = await service.generate_queries(body.research_question, body.domain)
    except Exception:
        logger.exception(
            "Generate queries failed: user_id=%s domain=%s",
            getattr(current_user, "id", None),
            body.domain,
        )
        raise
    logger.info(
        "Generate queries succeeded: user_id=%s domain=%s candidate_count=%s",
        getattr(current_user, "id", None),
        body.domain,
        len(candidates),
    )
    return QueryGenerateResponse(
        candidates=candidates,
        research_question=body.research_question,
        domain=body.domain,
    )
