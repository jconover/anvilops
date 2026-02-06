"""Custom exceptions for the Puppet Enterprise service layer."""


class PuppetError(Exception):
    """Base exception for Puppet Enterprise service errors.

    Attributes:
        message: Human-readable error description.
        status_code: HTTP status code returned by Puppet Enterprise, if applicable.
        response_body: Raw response body from the PE API, if available.
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
        parts = [f"PuppetError({self.message!r}"]
        if self.status_code is not None:
            parts.append(f", status_code={self.status_code}")
        parts.append(")")
        return "".join(parts)


class PuppetConnectionError(PuppetError):
    """Raised when a Puppet Enterprise API endpoint is unreachable."""


class PuppetAuthError(PuppetError):
    """Raised on 401/403 authentication or authorization failures."""


class PuppetNodeError(PuppetError):
    """Raised when a node-level operation fails (e.g. not found in PuppetDB)."""


class PuppetClassificationError(PuppetError):
    """Raised when a node classifier operation fails (group creation, pinning)."""


class PuppetTimeoutError(PuppetError):
    """Raised when polling for a node check-in exceeds the configured timeout."""
