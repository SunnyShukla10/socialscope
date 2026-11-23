import asyncio
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import redis.asyncio as aioredis
from app.database import get_db
from app.config import settings

router = APIRouter()


@router.get("/api/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    async def database_ready():
        try:
            await asyncio.wait_for(db.execute(text("SELECT 1")), timeout=2)
            return True
        except Exception:
            # A failed query may leave the request's transaction unusable.
            try:
                await asyncio.wait_for(db.rollback(), timeout=2)
            except Exception:
                pass
            return False

    async def redis_ready():
        r = None
        try:
            r = aioredis.from_url(settings.REDIS_URL, socket_connect_timeout=2, socket_timeout=2)
            await asyncio.wait_for(r.ping(), timeout=2)
            return True
        except Exception:
            return False
        finally:
            if r is not None:
                try:
                    await asyncio.wait_for(r.aclose(), timeout=1)
                except Exception:
                    pass

    db_ok, redis_ok = await asyncio.gather(database_ready(), redis_ready())
    payload = {
        "status": "ok" if db_ok and redis_ok else "degraded",
        "database": db_ok,
        "redis": redis_ok,
    }
    return JSONResponse(status_code=200 if db_ok and redis_ok else 503, content=payload)
