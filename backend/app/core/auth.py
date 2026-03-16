"""FastAPI dependencies for Cognito JWT authentication and authorization."""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from jwt import PyJWKClient

from app.core.config import settings

logger = logging.getLogger(__name__)


class AuthenticatedUser:
    """Represents a validated, authenticated user from a Cognito JWT."""

    def __init__(self, sub: str, email: str, groups: list[str], role: str):
        self.sub = sub
        self.email = email
        self.groups = groups
        self.role = role


# Cognito group name -> app role mapping (highest precedence first)
COGNITO_GROUP_TO_ROLE: dict[str, str] = {
    "Admin": "admin",
    "Approver": "approver",
    "Builder-Prod": "builder_prod",
    "Builder": "builder",
    "Viewer": "viewer",
}

ROLE_HIERARCHY: dict[str, int] = {
    "admin": 50,
    "approver": 40,
    "builder_prod": 30,
    "builder": 20,
    "viewer": 10,
}


def _resolve_highest_role(groups: list[str]) -> str:
    """Resolve the highest-precedence role from Cognito group names."""
    highest = "viewer"
    highest_level = ROLE_HIERARCHY["viewer"]
    for group in groups:
        mapped = COGNITO_GROUP_TO_ROLE.get(group)
        if mapped and ROLE_HIERARCHY.get(mapped, 0) > highest_level:
            highest = mapped
            highest_level = ROLE_HIERARCHY[mapped]
    return highest


@lru_cache(maxsize=1)
def _get_jwk_client() -> PyJWKClient:
    """Get a cached PyJWKClient for the Cognito JWKS endpoint."""
    jwks_url = (
        f"https://cognito-idp.{settings.COGNITO_REGION}.amazonaws.com/"
        f"{settings.COGNITO_USER_POOL_ID}/.well-known/jwks.json"
    )
    return PyJWKClient(jwks_url)


def _extract_token(request: Request) -> str | None:
    """Extract JWT from cookie or Authorization header."""
    # Prefer cookie (HttpOnly)
    token = request.cookies.get("anvilops_token")
    if token:
        return token
    # Fallback to Authorization header
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:]
    return None


async def get_current_user(request: Request) -> AuthenticatedUser:
    """FastAPI dependency that validates the JWT and returns the authenticated user.

    Raises 401 if no token or invalid token.
    """
    if not settings.COGNITO_USER_POOL_ID:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication not configured",
        )

    token = _extract_token(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        jwk_client = _get_jwk_client()
        signing_key = jwk_client.get_signing_key_from_jwt(token)

        issuer = (
            f"https://cognito-idp.{settings.COGNITO_REGION}.amazonaws.com/"
            f"{settings.COGNITO_USER_POOL_ID}"
        )

        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=issuer,
            audience=settings.COGNITO_CLIENT_ID or None,
            options={"require": ["exp", "iss", "sub"]},
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as e:
        logger.warning("JWT validation failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if payload.get("token_use") != "id":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    cognito_groups = payload.get("cognito:groups", [])
    role = _resolve_highest_role(cognito_groups)

    user = AuthenticatedUser(
        sub=payload["sub"],
        email=payload.get("email", ""),
        groups=cognito_groups,
        role=role,
    )

    # Attach to request.state for audit middleware
    request.state.actor_email = user.email
    request.state.actor_role = user.role

    return user


# Type alias for use in route signatures
CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]


def require_role(minimum_role: str):
    """Factory that returns a dependency checking the user has at least the given role."""
    min_level = ROLE_HIERARCHY.get(minimum_role, 0)

    async def check_role(user: CurrentUser) -> AuthenticatedUser:
        user_level = ROLE_HIERARCHY.get(user.role, 0)
        if user_level < min_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires at least '{minimum_role}' role",
            )
        return user

    return check_role
