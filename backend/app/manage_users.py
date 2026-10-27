"""Interactive operator commands; passwords are never command-line arguments."""
import argparse
import asyncio
import warnings
from getpass import getpass, GetPassWarning
from sqlalchemy import func, select
from app.database import AsyncSessionLocal, engine
from app.models.user import User
from app.models.organization import Organization
from app.schemas.pilot import MemberCreate, validate_password
from app.services.user_service import lock_organization, reset_password


async def ensure_admin(db, *, email, password, organization_slug="local",
                       organization_name="SocialScope Workspace", full_name="Research Administrator"):
    """Create a missing account only. Existing users and their details are untouched."""
    existing = await db.scalar(select(User).where(func.lower(User.email) == email.strip().lower()))
    if existing:
        return existing, False
    payload = MemberCreate(email=email, full_name=full_name, password=password)
    org = await db.scalar(select(Organization).where(Organization.slug == organization_slug))
    if not org:
        org = Organization(slug=organization_slug, name=organization_name, plan="pilot")
        db.add(org)
        await db.flush()
    user = User(organization_id=org.id, email=payload.email, full_name=payload.full_name,
        role="admin", hashed_password=User.hash_password(password))
    db.add(user)
    await db.flush()
    from app.services.activity_service import ActivityService
    await ActivityService(db).log(organization_id=org.id, actor_label="Operator",
        action="account_created", target_type="user", target_id=str(user.id), target_label=user.email)
    return user, True


def read_password():
    # Refuse getpass's echoing fallback when no secure terminal is available.
    with warnings.catch_warnings():
        warnings.simplefilter("error", GetPassWarning)
        try:
            password = getpass("New password (12+ characters, maximum 72 UTF-8 bytes): ")
            validate_password(password)
            if password != getpass("Confirm password: "):
                raise ValueError("Passwords do not match")
        except GetPassWarning:
            raise ValueError("Use an interactive terminal with hidden password input") from None
    return password


async def run(command):
    email = input("Account email: ").strip().lower()
    async with AsyncSessionLocal() as db:
        if command == "bootstrap":
            if await db.scalar(select(User.id).where(func.lower(User.email) == email)):
                print("Account already exists; nothing changed.")
                return
            slug = input("Organization slug [local]: ").strip() or "local"
            name = input("Organization name [SocialScope Workspace]: ").strip() or "SocialScope Workspace"
            full_name = input("Administrator name: ").strip()
            await ensure_admin(db, email=email, password=read_password(),
                organization_slug=slug, organization_name=name, full_name=full_name)
            print_message = "Administrator created."
        else:
            user = await db.scalar(select(User).where(func.lower(User.email) == email))
            if not user:
                raise ValueError("Account not found")
            password = read_password()
            await lock_organization(db, user.organization_id)
            await db.refresh(user)
            await reset_password(db, user, password)
            print_message = "Password reset; previous tokens invalidated. Account status unchanged."
        await db.commit()
        print(print_message)


async def main(command):
    try:
        await run(command)
    except (ValueError, EOFError):
        print("No changes saved. Check the account, required fields, and password requirements.")
        raise SystemExit(1) from None
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["bootstrap", "reset-password"])
    asyncio.run(main(parser.parse_args().command))
