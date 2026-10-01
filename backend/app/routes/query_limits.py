from fastapi import APIRouter

from app.services.query_validation import query_limits_payload


router = APIRouter(prefix="/api/query-limits", tags=["query_limits"])


@router.get("")
async def get_query_limits() -> dict:
    """Return non-sensitive application safeguards used by the project wizard."""
    return query_limits_payload()
