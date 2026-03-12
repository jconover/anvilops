"""Custom exceptions for the Port IDP service layer."""


class PortError(Exception):
    """Base exception for Port service errors.

    Attributes:
        message: Human-readable error description.
        status_code: HTTP status code returned by Port, if applicable.
        response_body: Raw response body from Port, if available.
    """

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response_body: str | None = None,
    ) -> None:
        self.message = message
        self.status_code = status_code
        self.response_body = response_body
        super().__init__(message)

    def __repr__(self) -> str:
        parts = [f"PortError({self.message!r}"]
        if self.status_code is not None:
            parts.append(f", status_code={self.status_code}")
        parts.append(")")
        return "".join(parts)


class PortConnectionError(PortError):
    """Raised when the Port API is unreachable."""


class PortAuthError(PortError):
    """Raised on 401/403 authentication or authorization failures."""


class PortNotFoundError(PortError):
    """Raised when an entity is not found (404)."""


class PortRateLimitError(PortError):
    """Raised when Port returns 429 Too Many Requests."""
