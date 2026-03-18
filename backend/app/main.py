"""AnvilOps FastAPI application."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.api.v1.router import api_v1_router
from app.core.config import settings

logger = logging.getLogger(__name__)

# Trust X-Forwarded-Proto from ALB so redirects use the correct scheme.
try:
    from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
except ImportError:  # pragma: no cover
    ProxyHeadersMiddleware = None

limiter = Limiter(key_func=get_remote_address, default_limits=[settings.RATE_LIMIT_DEFAULT])


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("AnvilOps API starting")

    # Seed default server templates
    try:
        from app.db.session import async_session_maker
        from app.services.template_seed import seed_default_templates

        async with async_session_maker() as session:
            await seed_default_templates(session)
            await session.commit()
        logger.info("Template seeding complete")
    except Exception as exc:
        logger.warning("Template seeding skipped: %s", exc)

    yield
    logger.info("AnvilOps API shutting down")


app = FastAPI(
    title="AnvilOps API",
    description="Self-service server provisioning platform",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ProxyHeadersMiddleware must be outermost so downstream middleware sees
# the real client scheme/IP forwarded by the ALB.
if ProxyHeadersMiddleware is not None:
    app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=settings.TRUSTED_PROXY_HOSTS)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Request-ID"],
)

app.include_router(api_v1_router, prefix=settings.API_V1_PREFIX)


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "anvilops-api"}
