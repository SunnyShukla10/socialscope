from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas.auth import LoginRequest, TokenResponse, UserOut
from app.services.auth_service import AuthService
from app.services.activity_service import ActivityService

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    auth_service = AuthService(db)
    user = await auth_service.authenticate(request.email, request.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = auth_service.create_access_token({"sub": str(user.id), "ver": user.token_version})
    await ActivityService(db).log(organization_id=user.organization_id, actor=user,
        action="login_succeeded", target_type="user", target_id=str(user.id))
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserOut)
async def me(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(AuthService.get_current_user),
):
    return current_user
