from fastapi import APIRouter, Depends
from app.config import settings
from app.services.auth_service import AuthService
router = APIRouter(prefix="/api/sources", tags=["sources"])
@router.get("")
async def sources(user=Depends(AuthService.get_current_user)):
    return {"version": "0.1.0-pilot", "build": settings.BUILD_ID,
        "max_posts": 5000, "preview_fresh_seconds": 900,
        "credential_mode": "Shared organization provider accounts",
        "account_limit_warning": "Collections use provider credits. Start with a preview and a focused query, and check your provider balance before larger pulls.",
        "sources": [{"platform":p,"provider": "xpoz" if p=="instagram" else "socialvault",
            "configured": bool(settings.XPOZ_API_KEY if p=="instagram" else settings.SOCIALVAULT_API_KEY),
            "comparison":p in {"twitter","reddit","youtube"},
            "limitations": "Existing Xpoz search returns at most 300 results; credit cost depends on provider billing." if p=="instagram" else "Dates filter retrieved results; complete historical coverage is not guaranteed."}
            for p in ["instagram","tiktok","facebook","twitter","reddit","youtube"]]}
