"""Organization-scoped account administration, shared by API and operator tool."""
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from app.models.organization import Organization
from app.models.user import User
from app.schemas.pilot import validate_password
from app.services.activity_service import ActivityService


async def lock_organization(db, organization_id):
    # Serialize membership changes so concurrent requests cannot disable every admin.
    await db.execute(select(Organization).where(Organization.id == organization_id).with_for_update())


async def create_member(db, admin, payload):
    await lock_organization(db, admin.organization_id)
    await db.refresh(admin)
    if not admin.is_active or admin.role != "admin":
        raise HTTPException(403, "Admin access required")
    existing = await db.scalar(select(User.id).where(func.lower(User.email) == payload.email))
    if existing:
        raise HTTPException(409, "This email cannot be used for a new account")
    user = User(
        organization_id=admin.organization_id, full_name=payload.full_name,
        email=payload.email, role="member", is_active=True,
        hashed_password=User.hash_password(payload.password.get_secret_value()),
    )
    db.add(user)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "This email cannot be used for a new account") from None
    await ActivityService(db).log(
        organization_id=admin.organization_id, actor=admin,
        action="account_created", target_type="user", target_id=str(user.id), target_label=user.email,
    )
    return user


async def set_user_status(db, admin, user_id, is_active):
    await lock_organization(db, admin.organization_id)
    await db.refresh(admin)
    if not admin.is_active or admin.role != "admin":
        raise HTTPException(403, "Admin access required")
    user = await db.scalar(select(User).where(User.id == user_id, User.organization_id == admin.organization_id))
    if not user:
        raise HTTPException(404, "User not found")
    if user.is_active == is_active:
        return user
    if not is_active and user.role == "admin":
        count = await db.scalar(select(func.count()).select_from(User).where(
            User.organization_id == admin.organization_id, User.role == "admin", User.is_active.is_(True)))
        if count <= 1:
            raise HTTPException(409, "Cannot disable the last active administrator")
    user.is_active = is_active
    user.token_version += 1
    await ActivityService(db).log(
        organization_id=admin.organization_id, actor=admin,
        action="account_enabled" if is_active else "account_disabled",
        target_type="user", target_id=str(user.id), target_label=user.email,
    )
    return user


async def reset_password(db, user, password):
    validate_password(password)
    user.hashed_password = User.hash_password(password)
    user.token_version += 1
    await ActivityService(db).log(
        organization_id=user.organization_id, actor_label="Operator",
        action="account_password_reset", target_type="user", target_id=str(user.id), target_label=user.email,
    )
