"""FastAPI dependency for injecting audit context into route handlers.

Extracts request metadata (IP address, User-Agent) and the authenticated
user's identity from the JWT-validated request state.  Returns a plain dict
that can be spread into ``AuditLogger.log_async()``::

    from app.middleware.audit import get_audit_context

    @router.post("/")
    async def create_something(
        ...,
        audit_ctx: dict = Depends(get_audit_context),
    ):
        await AuditLogger.log_async(
            db=db,
            action=AuditActions.SOMETHING_CREATED,
            category="something",
            **audit_ctx,
        )
"""

from __future__ import annotations

import ipaddress
import logging

from fastapi import Request

logger = logging.getLogger(__name__)


def get_audit_context(request: Request) -> dict:
    """Extract audit-relevant metadata from the incoming request.

    Returns a dict with keys that align with the ``AuditLogger`` keyword
    arguments:

    - ``ip_address`` -- client IP (supports ``X-Forwarded-For`` behind
      a reverse proxy).
    - ``user_agent`` -- truncated to 500 characters.
    - ``actor_email`` -- extracted from the request state after JWT
      validation by ``get_current_user``, otherwise ``None``.
    - ``actor_role`` -- likewise sourced from request state.
    """
    # Prefer X-Forwarded-For when running behind a load balancer / proxy.
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        # Take the leftmost (original client) IP, validated as a proper address.
        candidate = forwarded_for.split(",")[0].strip()
        try:
            ipaddress.ip_address(candidate)
            ip_address = candidate
        except ValueError:
            logger.warning(
                "X-Forwarded-For contains an invalid IP %r; falling back to connection IP",
                candidate,
            )
            ip_address = request.client.host if request.client else None
    else:
        ip_address = request.client.host if request.client else None

    user_agent = request.headers.get("user-agent", "")[:500] or None

    # Auth dependency (get_current_user) attaches these to request.state.
    actor_email: str | None = getattr(request.state, "actor_email", None)
    actor_role: str | None = getattr(request.state, "actor_role", None)

    return {
        "ip_address": ip_address,
        "user_agent": user_agent,
        "actor_email": actor_email,
        "actor_role": actor_role,
    }
