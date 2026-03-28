"""AI Avatar Revenue OS — FastAPI Application."""
import logging
import time

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from apps.api.config import get_settings
from apps.api.routers import (
    auth, brands, health, organizations, avatars, offers,
    accounts, content, decisions, jobs, providers, dashboard,
    settings as settings_router, discovery, pipeline, analytics,
)

settings = get_settings()

log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.ConsoleRenderer() if settings.api_env == "development" else structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(log_level),
)

logger = structlog.get_logger()

app = FastAPI(
    title="AI Avatar Revenue OS",
    description="Production-grade autonomous content monetization platform",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    redirect_slashes=False,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.api_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next) -> Response:
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - start
    logger.info(
        "request",
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        duration_ms=round(elapsed * 1000, 2),
    )
    return response


if settings.sentry_dsn:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    sentry_sdk.init(dsn=settings.sentry_dsn, integrations=[FastApiIntegration()])

app.include_router(health.router, tags=["Health"])
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(organizations.router, prefix="/api/v1/organizations", tags=["Organizations"])
app.include_router(brands.router, prefix="/api/v1/brands", tags=["Brands"])
app.include_router(avatars.router, prefix="/api/v1/avatars", tags=["Avatars"])
app.include_router(offers.router, prefix="/api/v1/offers", tags=["Offers"])
app.include_router(accounts.router, prefix="/api/v1/accounts", tags=["Creator Accounts"])
app.include_router(content.router, prefix="/api/v1/content", tags=["Content Pipeline"])
app.include_router(decisions.router, prefix="/api/v1/decisions", tags=["Decisions"])
app.include_router(jobs.router, prefix="/api/v1/jobs", tags=["System Jobs"])
app.include_router(providers.router, prefix="/api/v1/providers", tags=["Provider Profiles"])
app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["Dashboard"])
app.include_router(settings_router.router, prefix="/api/v1/settings", tags=["Settings"])
app.include_router(discovery.router, prefix="/api/v1/brands", tags=["Discovery & Scoring"])
app.include_router(pipeline.router, prefix="/api/v1/pipeline", tags=["Content Pipeline"])
app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["Analytics & Attribution"])
