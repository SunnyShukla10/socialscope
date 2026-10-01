from fastapi import APIRouter, Depends
from app.config import settings
from app.services.auth_service import AuthService
from app.services.budget_service import COSTS
router = APIRouter(prefix="/api/sources", tags=["sources"])
@router.get("")
async def sources(user=Depends(AuthService.get_current_user)):
    return {"version": "0.1.0-pilot", "build": settings.BUILD_ID,
        "max_posts": 5000, "preview_fresh_seconds": 900,
        "credential_mode": "Shared organization provider accounts",
        "account_limit_warning": "Limits apply to this pull on this installation. Other installations and SocialPulse can spend from the same account.",
        "sources": [{"platform":p,"provider": "xpoz" if p=="instagram" else "socialvault",
            "configured": bool(settings.XPOZ_API_KEY if p=="instagram" else settings.SOCIALVAULT_API_KEY),
            "comparison":p in {"twitter","reddit","youtube"},
            "limitations": "Existing Xpoz search returns at most 300 results; SDK operations limited, credit cost unknown." if p=="instagram" else "Dates filter retrieved results; complete historical coverage is not guaranteed."}
            for p in ["instagram","tiktok","facebook","twitter","reddit","youtube"]]}
