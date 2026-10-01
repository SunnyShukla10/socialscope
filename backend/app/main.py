import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder

from app.config import settings
from app.database import engine

from app.routes import (
    health,
    auth,
    projects,
    search_jobs,
    queries,
    posts,
    analytics,
    sources,
    exports,
    dashboard,
    admin,
    query_limits,
)
from app.services.query_validation import QueryValidationError

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("SocialScope API starting up...")
    yield
    logger.info("SocialScope API shutting down...")
    await engine.dispose()


app = FastAPI(
    title="SocialScope API",
    description="Historical social media research pilot",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# ─── CORS ─────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routes ───────────────────────────────────────────────────────────────────
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(search_jobs.router)
app.include_router(queries.router)
app.include_router(posts.router)
app.include_router(analytics.router)
app.include_router(sources.router)
app.include_router(exports.router)
app.include_router(dashboard.router)
app.include_router(admin.router)
app.include_router(query_limits.router)


# ─── Root ─────────────────────────────────────────────────────────────────────
@app.get("/", include_in_schema=False)
async def root():
    return {"service": "SocialScope API", "version": "0.1.0", "docs": "/api/docs"}


# ─── Global exception handler ─────────────────────────────────────────────────
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    safe_errors = [{k: v for k, v in error.items() if k in {"loc", "msg", "type"}} for error in exc.errors()]
    logger.warning(
        "Request validation failed: method=%s path=%s errors=%s",
        request.method,
        request.url.path,
        safe_errors,
    )
    return JSONResponse(
        status_code=422,
        content=jsonable_encoder({"detail": safe_errors}, custom_encoder={ValueError: str}),
    )


@app.exception_handler(QueryValidationError)
async def query_validation_exception_handler(request: Request, exc: QueryValidationError):
    logger.warning(
        "Query validation failed: method=%s path=%s code=%s platform=%s provider=%s",
        request.method,
        request.url.path,
        exc.issue.code,
        exc.issue.platform,
        exc.issue.provider,
    )
    return JSONResponse(status_code=422, content=exc.issue.to_dict())


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc):
    logger.error(
        "Unhandled exception: method=%s path=%s error=%s",
        request.method,
        request.url.path,
        type(exc).__name__,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )
