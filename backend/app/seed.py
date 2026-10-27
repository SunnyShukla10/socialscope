"""Create the configured initial administrator only when missing."""
import asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from app.config import settings
from app.manage_users import ensure_admin


async def seed():
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as db:
            _, created = await ensure_admin(db, email=settings.LOCAL_ADMIN_EMAIL,
                password=settings.LOCAL_ADMIN_PASSWORD)
            await db.commit()
        print("Initial administrator created." if created else "Existing account preserved; no changes made.")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
