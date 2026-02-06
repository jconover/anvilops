"""Custom exceptions for the AWX service layer."""


class AWXError(Exception):
    """Base exception for AWX service errors.

    Attributes:
        message: Human-readable error description.
        status_code: HTTP status code returned by AWX, if applicable.
        response_body: Raw response body from AWX, if available.
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
        parts = [f"AWXError({self.message!r}"]
        if self.status_code is not None:
            parts.append(f", status_code={self.status_code}")
        parts.append(")")
        return "".join(parts)


class AWXConnectionError(AWXError):
    """Raised when the AWX API is unreachable."""


class AWXAuthError(AWXError):
    """Raised on 401/403 authentication or authorization failures."""


class AWXJobError(AWXError):
    """Raised when an AWX job fails, errors, or is canceled."""


class AWXTimeoutError(AWXError):
    """Raised when polling for a job exceeds the configured timeout."""
