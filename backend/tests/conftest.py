"""Offline API fixtures. SQLite is not evidence of PostgreSQL lock correctness."""
import uuid
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB
from app.main import app
from app.database import get_db
from app.models import Base, Organization, User
from app.services.auth_service import AuthService

@compiles(JSONB, "sqlite")
def jsonb_as_json(type_, compiler, **kw): return "JSON"

@pytest_asyncio.fixture
async def sessions():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()

@pytest_asyncio.fixture
async def client(sessions):
    async def override_db():
        async with sessions() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
    app.dependency_overrides[get_db] = override_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()

@pytest_asyncio.fixture
async def seed_org_and_user(sessions):
    async with sessions() as db:
        org=Organization(name="Test Research", slug="test")
        db.add(org); await db.flush()
        user=User(organization_id=org.id, email="test@example.com", full_name="Test User",
            role="admin", hashed_password=User.hash_password("test-password"))
        db.add(user); await db.commit()
        return org,user,"test-password"

@pytest.fixture
def auth_headers(seed_org_and_user):
    _, user, _ = seed_org_and_user
    return {"Authorization": "Bearer " + AuthService(None).create_access_token({"sub":str(user.id)})}

