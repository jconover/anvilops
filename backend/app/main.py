"""AnvilOps FastAPI application."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.v1.router import api_v1_router
from app.core.config import settings
from app.core.logging import configure_logging, generate_request_id, request_id_ctx

configure_logging(debug=settings.DEBUG)
logger = logging.getLogger(__name__)

# Service-level exception types whose messages should never leak to clients.
_UPSTREAM_EXCEPTIONS: tuple[str, ...] = (
    "AWXError",
    "PuppetError",
    "PortError",
    "PortConnectionError",
    "PortAuthError",
)


def _is_upstream_error(exc: Exception) -> bool:
    """Return True if *exc* originates from an upstream service integration."""
    return type(exc).__name__ in _UPSTREAM_EXCEPTIONS

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


@app.exception_handler(Exception)
async def _global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch unhandled exceptions and sanitise the response.

    In DEBUG mode the original message is returned for developer convenience.
    In production, upstream service errors are replaced with a generic message
    so that internal hostnames, stack traces, and service topology are never
    exposed to API consumers.
    """
    if settings.DEBUG:
        logger.exception("Unhandled exception (DEBUG): %s", exc)
        return JSONResponse(
            status_code=500,
            content={"detail": str(exc)},
        )

    if _is_upstream_error(exc):
        logger.exception("Upstream service error (sanitised): %s", exc)
        return JSONResponse(
            status_code=503,
            content={"detail": "An upstream service is temporarily unavailable."},
        )

    logger.exception("Unhandled exception (sanitised): %s", exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal error occurred. Please try again later."},
    )

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


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Attach a correlation ID to every request for structured logging."""

    async def dispatch(self, request: Request, call_next) -> Response:
        rid = request.headers.get("X-Request-ID") or generate_request_id()
        token = request_id_ctx.set(rid)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = rid
            return response
        finally:
            request_id_ctx.reset(token)


app.add_middleware(RequestIDMiddleware)

app.include_router(api_v1_router, prefix=settings.API_V1_PREFIX)


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "anvilops-api"}
