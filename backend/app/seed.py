"""
Minimal local seed for SocialScope.

Creates only the default organization and admin login. It does not create
projects, jobs, posts, accounts, tags, exports.

Usage:
    python -m app.seed
"""
import asyncio
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.models.organization import Organization
from app.models.user import User


async def seed():
    print("Starting SocialScope local seed...")

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    SessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with SessionLocal() as db:
        result = await db.execute(select(Organization).where(Organization.slug == "local"))
        org = result.scalar_one_or_none()
        if not org:
            org = Organization(
                id=uuid.uuid4(),
                name="SocialScope Workspace",
                slug="local",
                plan="local",
            )
            db.add(org)
            await db.flush()

        result = await db.execute(select(User).where(User.email == settings.LOCAL_ADMIN_EMAIL))
        admin = result.scalar_one_or_none()
        if not admin:
            admin = User(
                id=uuid.uuid4(),
                organization_id=org.id,
                email=settings.LOCAL_ADMIN_EMAIL,
                hashed_password=User.hash_password(settings.LOCAL_ADMIN_PASSWORD),
                full_name="Alex Admin",
                role="admin",
            )
            db.add(admin)
        else:
            admin.organization_id = org.id
            admin.hashed_password = User.hash_password(settings.LOCAL_ADMIN_PASSWORD)
            admin.full_name = "Alex Admin"
            admin.role = "admin"

        await db.commit()

    await engine.dispose()
    print("Seed complete. Sign in using LOCAL_ADMIN_EMAIL and LOCAL_ADMIN_PASSWORD from your .env file.")


if __name__ == "__main__":
    asyncio.run(seed())
