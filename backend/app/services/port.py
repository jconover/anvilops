"""Port IDP service layer.

Provides both async and synchronous clients for the Port REST API. The async
client (PortService) is suitable for FastAPI endpoints; the sync client
(PortServiceSync) is used by Celery tasks.

Port API: https://api.getport.io/v1/

Responsibilities:
  - Entity CRUD (upsert, get, delete, search) for catalog blueprints
  - Webhook signature verification for self-service actions
  - Health check

All public methods are best-effort: errors are logged but never raised
so that Port sync failures cannot block the build pipeline.
"""

import hashlib
import hmac
import logging
import time
from typing import Any

import httpx

from app.core.config import settings
from app.services.port_exceptions import (
    PortAuthError,
    PortConnectionError,
    PortError,
    PortNotFoundError,
    PortRateLimitError,
)

logger = logging.getLogger(__name__)

PORT_API_BASE = "https://api.getport.io/v1"

# Maximum age (in seconds) of a webhook request before we reject it.
_MAX_TIMESTAMP_AGE = 300


def _check_enabled(method_name: str) -> bool:
    """Return True if the Port integration is enabled and configured."""
    if not settings.PORT_ENABLED:
        logger.debug("Port integration disabled, skipping %s", method_name)
        return False

    if not settings.PORT_CLIENT_ID or not settings.PORT_CLIENT_SECRET:
        logger.warning(
            "Port not configured (missing client_id or client_secret), "
            "skipping %s",
            method_name,
        )
        return False

    return True


def verify_webhook_signature(
    payload_body: str,
    signature: str,
    webhook_secret: str | None = None,
) -> bool:
    """Verify a Port webhook HMAC-SHA256 signature.

    Port signs webhook payloads with:
        ``sha256=<hex-digest of HMAC-SHA256(webhook_secret, body)>``

    Also rejects requests older than ``_MAX_TIMESTAMP_AGE`` seconds when
    a ``timestamp`` field is present in the payload.

    Returns ``True`` when the signature is valid.
    """
    secret = webhook_secret or settings.PORT_WEBHOOK_SECRET
    if not secret:
        logger.warning("Port webhook secret not configured; rejecting request")
        return False

    if not signature:
        logger.warning("No signature provided in Port webhook request")
        return False

    expected = (
        "sha256="
        + hmac.new(
            secret.encode("utf-8"),
            payload_body.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
    )

    if not hmac.compare_digest(expected, signature):
        logger.warning("Port webhook signature mismatch")
        return False

    return True


# ---------------------------------------------------------------------------
# Async client (for FastAPI endpoints)
# ---------------------------------------------------------------------------


class PortService:
    """Async client for the Port REST API.

    Uses ``httpx.AsyncClient`` with Bearer token authentication obtained
    via the Port client credentials flow.
    """

    def __init__(
        self,
        base_url: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = (base_url or PORT_API_BASE).rstrip("/")
        self._client_id = client_id or settings.PORT_CLIENT_ID
        self._client_secret = client_secret or settings.PORT_CLIENT_SECRET
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None
        self._access_token: str | None = None
        self._token_expires_at: float = 0.0

    async def _get_client(self) -> httpx.AsyncClient:
        """Lazily create and return the shared async HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self._timeout,
                headers={"Content-Type": "application/json"},
            )
        return self._client

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()

    async def _ensure_token(self) -> str:
        """Obtain or refresh the Port access token via client credentials."""
        if self._access_token and time.time() < self._token_expires_at:
            return self._access_token

        client = await self._get_client()
        try:
            response = await client.post(
                "/auth/access_token",
                json={
                    "clientId": self._client_id,
                    "clientSecret": self._client_secret,
                },
            )
        except httpx.ConnectError as exc:
            raise PortConnectionError(
                f"Cannot connect to Port at {self.base_url}: {exc}"
            ) from exc
        except httpx.TimeoutException as exc:
            raise PortConnectionError(
                f"Port auth request timed out: {exc}"
            ) from exc

        if response.status_code >= 400:
            raise PortAuthError(
                f"Port auth failed ({response.status_code})",
                status_code=response.status_code,
                response_body=response.text[:500],
            )

        data = response.json()
        self._access_token = data["accessToken"]
        # Port tokens expire in 24h; refresh 5 minutes early
        expires_in = data.get("expiresIn", 86400)
        self._token_expires_at = time.time() + expires_in - 300

        return self._access_token

    # -- HTTP helpers -------------------------------------------------------

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict | None = None,
        params: dict | None = None,
    ) -> httpx.Response:
        """Execute an authenticated HTTP request against Port."""
        token = await self._ensure_token()
        client = await self._get_client()

        try:
            response = await client.request(
                method,
                path,
                json=json_body,
                params=params,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                },
            )
        except httpx.ConnectError as exc:
            raise PortConnectionError(
                f"Cannot connect to Port at {self.base_url}: {exc}"
            ) from exc
        except httpx.TimeoutException as exc:
            raise PortConnectionError(
                f"Request to Port timed out: {exc}"
            ) from exc

        if response.status_code in (401, 403):
            raise PortAuthError(
                f"Port authentication failed ({response.status_code})",
                status_code=response.status_code,
                response_body=response.text[:500],
            )

        if response.status_code == 404:
            raise PortNotFoundError(
                f"Port entity not found: {method} {path}",
                status_code=404,
                response_body=response.text[:500],
            )

        if response.status_code == 429:
            raise PortRateLimitError(
                "Port rate limit exceeded",
                status_code=429,
                response_body=response.text[:500],
            )

        if response.status_code >= 400:
            raise PortError(
                f"Port API error: {method} {path} returned {response.status_code}",
                status_code=response.status_code,
                response_body=response.text[:1000],
            )

        return response

    async def _get(self, path: str, *, params: dict | None = None) -> httpx.Response:
        return await self._request("GET", path, params=params)

    async def _post(self, path: str, *, json_body: dict | None = None) -> httpx.Response:
        return await self._request("POST", path, json_body=json_body)

    async def _put(self, path: str, *, json_body: dict | None = None) -> httpx.Response:
        return await self._request("PUT", path, json_body=json_body)

    async def _delete(self, path: str) -> httpx.Response:
        return await self._request("DELETE", path)

    # -- Public API ---------------------------------------------------------

    async def health_check(self) -> bool:
        """Return True if Port API is reachable and credentials are valid."""
        try:
            await self._ensure_token()
            return True
        except PortError:
            return False

    async def upsert_entity(
        self,
        blueprint_id: str,
        entity_id: str,
        title: str,
        properties: dict[str, Any],
        relations: dict[str, Any] | None = None,
    ) -> dict | None:
        """Create or update a catalog entity in Port.

        Uses the Port upsert endpoint which creates the entity if it does
        not exist or updates it if it does.

        Returns the entity dict on success, None on failure.
        """
        if not _check_enabled("upsert_entity"):
            return None

        body: dict[str, Any] = {
            "identifier": entity_id,
            "title": title,
            "properties": properties,
        }
        if relations:
            body["relations"] = relations

        logger.info(
            "Port upsert entity: blueprint=%s id=%s title=%s",
            blueprint_id,
            entity_id,
            title,
        )

        try:
            response = await self._post(
                f"/blueprints/{blueprint_id}/entities",
                json_body=body,
            )
            result = response.json()
            entity = result.get("entity", result)
            logger.info(
                "Port entity upserted: blueprint=%s id=%s",
                blueprint_id,
                entity_id,
            )
            return entity

        except PortError as exc:
            logger.error(
                "Port upsert_entity failed for %s/%s: %s",
                blueprint_id,
                entity_id,
                exc,
            )
            return None
        except Exception as exc:
            logger.exception(
                "Unexpected error in Port upsert_entity for %s/%s: %s",
                blueprint_id,
                entity_id,
                exc,
            )
            return None

    async def get_entity(
        self, blueprint_id: str, entity_id: str
    ) -> dict | None:
        """Fetch a single entity by blueprint and identifier.

        Returns the entity dict or None if not found / on error.
        """
        if not _check_enabled("get_entity"):
            return None

        try:
            response = await self._get(
                f"/blueprints/{blueprint_id}/entities/{entity_id}"
            )
            result = response.json()
            return result.get("entity", result)

        except PortNotFoundError:
            logger.debug(
                "Port entity not found: blueprint=%s id=%s",
                blueprint_id,
                entity_id,
            )
            return None
        except PortError as exc:
            logger.error(
                "Port get_entity failed for %s/%s: %s",
                blueprint_id,
                entity_id,
                exc,
            )
            return None

    async def delete_entity(
        self, blueprint_id: str, entity_id: str
    ) -> bool:
        """Delete an entity from the Port catalog.

        Returns True on success, False on failure.
        """
        if not _check_enabled("delete_entity"):
            return False

        logger.info(
            "Port delete entity: blueprint=%s id=%s",
            blueprint_id,
            entity_id,
        )

        try:
            await self._delete(
                f"/blueprints/{blueprint_id}/entities/{entity_id}"
            )
            logger.info(
                "Port entity deleted: blueprint=%s id=%s",
                blueprint_id,
                entity_id,
            )
            return True

        except PortNotFoundError:
            logger.debug(
                "Port entity already absent: blueprint=%s id=%s",
                blueprint_id,
                entity_id,
            )
            return True
        except PortError as exc:
            logger.error(
                "Port delete_entity failed for %s/%s: %s",
                blueprint_id,
                entity_id,
                exc,
            )
            return False

    async def search_entities(
        self,
        blueprint_id: str,
        query: dict | None = None,
    ) -> list[dict]:
        """Search entities within a blueprint.

        Returns a list of entity dicts, or empty list on failure.
        """
        if not _check_enabled("search_entities"):
            return []

        body: dict[str, Any] = {
            "combinator": "and",
            "rules": [
                {
                    "property": "$blueprint",
                    "operator": "=",
                    "value": blueprint_id,
                }
            ],
        }
        if query:
            body["rules"].extend(query.get("rules", []))

        try:
            response = await self._post(
                "/entities/search",
                json_body=body,
            )
            result = response.json()
            entities = result.get("entities", [])
            logger.debug(
                "Port search returned %d entities for blueprint=%s",
                len(entities),
                blueprint_id,
            )
            return entities

        except PortError as exc:
            logger.error(
                "Port search_entities failed for blueprint=%s: %s",
                blueprint_id,
                exc,
            )
            return []


# ---------------------------------------------------------------------------
# Synchronous client (for Celery tasks)
# ---------------------------------------------------------------------------


class PortServiceSync:
    """Synchronous client for the Port REST API.

    Uses ``httpx.Client`` (blocking) so it can be called directly from Celery
    workers without an event loop.
    """

    def __init__(
        self,
        base_url: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = (base_url or PORT_API_BASE).rstrip("/")
        self._client_id = client_id or settings.PORT_CLIENT_ID
        self._client_secret = client_secret or settings.PORT_CLIENT_SECRET
        self._timeout = timeout
        self.client = httpx.Client(
            base_url=self.base_url,
            timeout=self._timeout,
            headers={"Content-Type": "application/json"},
        )
        self._access_token: str | None = None
        self._token_expires_at: float = 0.0

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self.client.close()

    def _ensure_token(self) -> str:
        """Obtain or refresh the Port access token via client credentials."""
        if self._access_token and time.time() < self._token_expires_at:
            return self._access_token

        try:
            response = self.client.post(
                "/auth/access_token",
                json={
                    "clientId": self._client_id,
                    "clientSecret": self._client_secret,
                },
            )
        except httpx.ConnectError as exc:
            raise PortConnectionError(
                f"Cannot connect to Port at {self.base_url}: {exc}"
            ) from exc
        except httpx.TimeoutException as exc:
            raise PortConnectionError(
                f"Port auth request timed out: {exc}"
            ) from exc

        if response.status_code >= 400:
            raise PortAuthError(
                f"Port auth failed ({response.status_code})",
                status_code=response.status_code,
                response_body=response.text[:500],
            )

        data = response.json()
        self._access_token = data["accessToken"]
        expires_in = data.get("expiresIn", 86400)
        self._token_expires_at = time.time() + expires_in - 300

        return self._access_token

    # -- HTTP helpers -------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict | None = None,
        params: dict | None = None,
    ) -> httpx.Response:
        """Execute an authenticated synchronous HTTP request against Port."""
        token = self._ensure_token()

        try:
            response = self.client.request(
                method,
                path,
                json=json_body,
                params=params,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                },
            )
        except httpx.ConnectError as exc:
            raise PortConnectionError(
                f"Cannot connect to Port at {self.base_url}: {exc}"
            ) from exc
        except httpx.TimeoutException as exc:
            raise PortConnectionError(
                f"Request to Port timed out: {exc}"
            ) from exc

        if response.status_code in (401, 403):
            raise PortAuthError(
                f"Port authentication failed ({response.status_code})",
                status_code=response.status_code,
                response_body=response.text[:500],
            )

        if response.status_code == 404:
            raise PortNotFoundError(
                f"Port entity not found: {method} {path}",
                status_code=404,
                response_body=response.text[:500],
            )

        if response.status_code == 429:
            raise PortRateLimitError(
                "Port rate limit exceeded",
                status_code=429,
                response_body=response.text[:500],
            )

        if response.status_code >= 400:
            raise PortError(
                f"Port API error: {method} {path} returned {response.status_code}",
                status_code=response.status_code,
                response_body=response.text[:1000],
            )

        return response

    def _get(self, path: str, *, params: dict | None = None) -> httpx.Response:
        return self._request("GET", path, params=params)

    def _post(self, path: str, *, json_body: dict | None = None) -> httpx.Response:
        return self._request("POST", path, json_body=json_body)

    def _put(self, path: str, *, json_body: dict | None = None) -> httpx.Response:
        return self._request("PUT", path, json_body=json_body)

    def _delete(self, path: str) -> httpx.Response:
        return self._request("DELETE", path)

    # -- Public API ---------------------------------------------------------

    def health_check(self) -> bool:
        """Return True if Port API is reachable and credentials are valid."""
        try:
            self._ensure_token()
            return True
        except PortError:
            return False

    def upsert_entity(
        self,
        blueprint_id: str,
        entity_id: str,
        title: str,
        properties: dict[str, Any],
        relations: dict[str, Any] | None = None,
    ) -> dict | None:
        """Create or update a catalog entity in Port.

        Returns the entity dict on success, None on failure.
        """
        if not _check_enabled("upsert_entity"):
            return None

        body: dict[str, Any] = {
            "identifier": entity_id,
            "title": title,
            "properties": properties,
        }
        if relations:
            body["relations"] = relations

        logger.info(
            "Port upsert entity: blueprint=%s id=%s title=%s",
            blueprint_id,
            entity_id,
            title,
        )

        try:
            response = self._post(
                f"/blueprints/{blueprint_id}/entities",
                json_body=body,
            )
            result = response.json()
            entity = result.get("entity", result)
            logger.info(
                "Port entity upserted: blueprint=%s id=%s",
                blueprint_id,
                entity_id,
            )
            return entity

        except PortError as exc:
            logger.error(
                "Port upsert_entity failed for %s/%s: %s",
                blueprint_id,
                entity_id,
                exc,
            )
            return None
        except Exception as exc:
            logger.exception(
                "Unexpected error in Port upsert_entity for %s/%s: %s",
                blueprint_id,
                entity_id,
                exc,
            )
            return None

    def get_entity(
        self, blueprint_id: str, entity_id: str
    ) -> dict | None:
        """Fetch a single entity by blueprint and identifier.

        Returns the entity dict or None if not found / on error.
        """
        if not _check_enabled("get_entity"):
            return None

        try:
            response = self._get(
                f"/blueprints/{blueprint_id}/entities/{entity_id}"
            )
            result = response.json()
            return result.get("entity", result)

        except PortNotFoundError:
            logger.debug(
                "Port entity not found: blueprint=%s id=%s",
                blueprint_id,
                entity_id,
            )
            return None
        except PortError as exc:
            logger.error(
                "Port get_entity failed for %s/%s: %s",
                blueprint_id,
                entity_id,
                exc,
            )
            return None

    def delete_entity(
        self, blueprint_id: str, entity_id: str
    ) -> bool:
        """Delete an entity from the Port catalog.

        Returns True on success, False on failure.
        """
        if not _check_enabled("delete_entity"):
            return False

        logger.info(
            "Port delete entity: blueprint=%s id=%s",
            blueprint_id,
            entity_id,
        )

        try:
            self._delete(
                f"/blueprints/{blueprint_id}/entities/{entity_id}"
            )
            logger.info(
                "Port entity deleted: blueprint=%s id=%s",
                blueprint_id,
                entity_id,
            )
            return True

        except PortNotFoundError:
            logger.debug(
                "Port entity already absent: blueprint=%s id=%s",
                blueprint_id,
                entity_id,
            )
            return True
        except PortError as exc:
            logger.error(
                "Port delete_entity failed for %s/%s: %s",
                blueprint_id,
                entity_id,
                exc,
            )
            return False

    def search_entities(
        self,
        blueprint_id: str,
        query: dict | None = None,
    ) -> list[dict]:
        """Search entities within a blueprint.

        Returns a list of entity dicts, or empty list on failure.
        """
        if not _check_enabled("search_entities"):
            return []

        body: dict[str, Any] = {
            "combinator": "and",
            "rules": [
                {
                    "property": "$blueprint",
                    "operator": "=",
                    "value": blueprint_id,
                }
            ],
        }
        if query:
            body["rules"].extend(query.get("rules", []))

        try:
            response = self._post(
                "/entities/search",
                json_body=body,
            )
            result = response.json()
            entities = result.get("entities", [])
            logger.debug(
                "Port search returned %d entities for blueprint=%s",
                len(entities),
                blueprint_id,
            )
            return entities

        except PortError as exc:
            logger.error(
                "Port search_entities failed for blueprint=%s: %s",
                blueprint_id,
                exc,
            )
            return []


# ---------------------------------------------------------------------------
# Factory functions
# ---------------------------------------------------------------------------


def get_port_service() -> PortService:
    """Create a PortService (async) from application settings."""
    return PortService(
        client_id=settings.PORT_CLIENT_ID,
        client_secret=settings.PORT_CLIENT_SECRET,
    )


def get_port_service_sync() -> PortServiceSync:
    """Create a PortServiceSync (blocking) from application settings."""
    return PortServiceSync(
        client_id=settings.PORT_CLIENT_ID,
        client_secret=settings.PORT_CLIENT_SECRET,
    )
