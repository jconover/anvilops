"""Unit tests for custom exception classes in AWX and Puppet service layers.

Pure in-memory logic — no external connections required.
"""

import pytest

from app.services.awx_exceptions import (
    AWXAuthError,
    AWXConnectionError,
    AWXError,
    AWXJobError,
    AWXTimeoutError,
)
from app.services.puppet_exceptions import (
    PuppetAuthError,
    PuppetClassificationError,
    PuppetConnectionError,
    PuppetError,
    PuppetNodeError,
    PuppetTimeoutError,
)


# ---------------------------------------------------------------------------
# AWXError base class
# ---------------------------------------------------------------------------


class TestAWXError:
    def test_is_exception(self):
        assert issubclass(AWXError, Exception)

    def test_message_stored(self):
        err = AWXError("something failed")
        assert err.message == "something failed"

    def test_str_is_message(self):
        err = AWXError("something failed")
        assert str(err) == "something failed"

    def test_status_code_default_none(self):
        err = AWXError("msg")
        assert err.status_code is None

    def test_response_body_default_none(self):
        err = AWXError("msg")
        assert err.response_body is None

    def test_status_code_stored(self):
        err = AWXError("msg", status_code=404)
        assert err.status_code == 404

    def test_response_body_stored(self):
        err = AWXError("msg", response_body='{"error": "not found"}')
        assert err.response_body == '{"error": "not found"}'

    def test_repr_without_status_code(self):
        err = AWXError("msg")
        assert "AWXError" in repr(err)
        assert "msg" in repr(err)

    def test_repr_with_status_code(self):
        err = AWXError("msg", status_code=500)
        assert "status_code=500" in repr(err)

    def test_can_be_raised_and_caught(self):
        with pytest.raises(AWXError) as exc_info:
            raise AWXError("test error", status_code=422)
        assert exc_info.value.status_code == 422

    def test_can_be_caught_as_exception(self):
        with pytest.raises(Exception):
            raise AWXError("err")


# ---------------------------------------------------------------------------
# AWX subclass hierarchy
# ---------------------------------------------------------------------------


class TestAWXSubclasses:
    def test_awx_connection_error_is_awx_error(self):
        assert issubclass(AWXConnectionError, AWXError)

    def test_awx_auth_error_is_awx_error(self):
        assert issubclass(AWXAuthError, AWXError)

    def test_awx_job_error_is_awx_error(self):
        assert issubclass(AWXJobError, AWXError)

    def test_awx_timeout_error_is_awx_error(self):
        assert issubclass(AWXTimeoutError, AWXError)

    def test_connection_error_stores_message(self):
        err = AWXConnectionError("unreachable", status_code=503)
        assert err.message == "unreachable"
        assert err.status_code == 503

    def test_auth_error_stores_message(self):
        err = AWXAuthError("forbidden", status_code=403)
        assert err.message == "forbidden"
        assert err.status_code == 403

    def test_job_error_stores_message(self):
        err = AWXJobError("job canceled")
        assert err.message == "job canceled"

    def test_timeout_error_stores_message(self):
        err = AWXTimeoutError("timed out after 600s")
        assert err.message == "timed out after 600s"

    def test_connection_error_caught_as_awx_error(self):
        with pytest.raises(AWXError):
            raise AWXConnectionError("unreachable")

    def test_auth_error_caught_as_awx_error(self):
        with pytest.raises(AWXError):
            raise AWXAuthError("401 unauthorized")

    def test_job_error_caught_as_awx_error(self):
        with pytest.raises(AWXError):
            raise AWXJobError("job failed")

    def test_timeout_error_caught_as_awx_error(self):
        with pytest.raises(AWXError):
            raise AWXTimeoutError("timeout")

    def test_subclasses_are_distinct_types(self):
        assert AWXConnectionError is not AWXAuthError
        assert AWXJobError is not AWXTimeoutError


# ---------------------------------------------------------------------------
# PuppetError base class
# ---------------------------------------------------------------------------


class TestPuppetError:
    def test_is_exception(self):
        assert issubclass(PuppetError, Exception)

    def test_message_stored(self):
        err = PuppetError("puppet failed")
        assert err.message == "puppet failed"

    def test_str_is_message(self):
        err = PuppetError("puppet failed")
        assert str(err) == "puppet failed"

    def test_status_code_default_none(self):
        err = PuppetError("msg")
        assert err.status_code is None

    def test_response_body_default_none(self):
        err = PuppetError("msg")
        assert err.response_body is None

    def test_status_code_stored(self):
        err = PuppetError("msg", status_code=500)
        assert err.status_code == 500

    def test_response_body_stored(self):
        err = PuppetError("msg", response_body='{"error": "internal"}')
        assert err.response_body == '{"error": "internal"}'

    def test_repr_without_status_code(self):
        err = PuppetError("msg")
        assert "PuppetError" in repr(err)
        assert "msg" in repr(err)

    def test_repr_with_status_code(self):
        err = PuppetError("msg", status_code=503)
        assert "status_code=503" in repr(err)

    def test_can_be_raised_and_caught(self):
        with pytest.raises(PuppetError) as exc_info:
            raise PuppetError("node not found", status_code=404)
        assert exc_info.value.status_code == 404

    def test_can_be_caught_as_exception(self):
        with pytest.raises(Exception):
            raise PuppetError("err")


# ---------------------------------------------------------------------------
# Puppet subclass hierarchy
# ---------------------------------------------------------------------------


class TestPuppetSubclasses:
    def test_puppet_connection_error_is_puppet_error(self):
        assert issubclass(PuppetConnectionError, PuppetError)

    def test_puppet_auth_error_is_puppet_error(self):
        assert issubclass(PuppetAuthError, PuppetError)

    def test_puppet_node_error_is_puppet_error(self):
        assert issubclass(PuppetNodeError, PuppetError)

    def test_puppet_classification_error_is_puppet_error(self):
        assert issubclass(PuppetClassificationError, PuppetError)

    def test_puppet_timeout_error_is_puppet_error(self):
        assert issubclass(PuppetTimeoutError, PuppetError)

    def test_connection_error_stores_message(self):
        err = PuppetConnectionError("PE unreachable", status_code=503)
        assert err.message == "PE unreachable"
        assert err.status_code == 503

    def test_auth_error_stores_message(self):
        err = PuppetAuthError("invalid token", status_code=401)
        assert err.message == "invalid token"
        assert err.status_code == 401

    def test_node_error_stores_message(self):
        err = PuppetNodeError("node not found in PuppetDB")
        assert err.message == "node not found in PuppetDB"

    def test_classification_error_stores_message(self):
        err = PuppetClassificationError("group creation failed")
        assert err.message == "group creation failed"

    def test_timeout_error_stores_message(self):
        err = PuppetTimeoutError("agent check-in timed out after 900s")
        assert err.message == "agent check-in timed out after 900s"

    def test_connection_error_caught_as_puppet_error(self):
        with pytest.raises(PuppetError):
            raise PuppetConnectionError("unreachable")

    def test_auth_error_caught_as_puppet_error(self):
        with pytest.raises(PuppetError):
            raise PuppetAuthError("403 forbidden")

    def test_node_error_caught_as_puppet_error(self):
        with pytest.raises(PuppetError):
            raise PuppetNodeError("node missing")

    def test_classification_error_caught_as_puppet_error(self):
        with pytest.raises(PuppetError):
            raise PuppetClassificationError("classification failed")

    def test_timeout_error_caught_as_puppet_error(self):
        with pytest.raises(PuppetError):
            raise PuppetTimeoutError("timeout")

    def test_subclasses_are_distinct_types(self):
        assert PuppetConnectionError is not PuppetAuthError
        assert PuppetNodeError is not PuppetClassificationError
        assert PuppetTimeoutError is not PuppetNodeError
