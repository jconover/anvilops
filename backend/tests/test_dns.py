"""Unit tests for DNSCleanupService.

The service is a stub (no real Route 53 calls) so all tests verify the
return contract and logging behaviour only -- no mocking of external
dependencies is required.
"""

import logging

import pytest

from app.services.dns import DNSCleanupService


@pytest.fixture
def svc():
    return DNSCleanupService()


# ---------------------------------------------------------------------------
# Return value contract
# ---------------------------------------------------------------------------


class TestCleanupRecordsReturnContract:
    def test_returns_dict(self, svc):
        result = svc.cleanup_records("PROD-WEB-01")
        assert isinstance(result, dict)

    def test_exit_code_is_zero(self, svc):
        result = svc.cleanup_records("PROD-WEB-01")
        assert result["exit_code"] == 0

    def test_output_is_string(self, svc):
        result = svc.cleanup_records("PROD-WEB-01")
        assert isinstance(result["output"], str)

    def test_output_contains_server_name(self, svc):
        result = svc.cleanup_records("PROD-WEB-01")
        assert "PROD-WEB-01" in result["output"]

    def test_result_has_exit_code_key(self, svc):
        result = svc.cleanup_records("MY-SERVER")
        assert "exit_code" in result

    def test_result_has_output_key(self, svc):
        result = svc.cleanup_records("MY-SERVER")
        assert "output" in result


# ---------------------------------------------------------------------------
# dns_name handling
# ---------------------------------------------------------------------------


class TestCleanupRecordsDnsName:
    def test_dns_name_mentioned_in_output(self, svc):
        result = svc.cleanup_records("PROD-WEB-01", dns_name="prod-web-01.corp.example.com")
        assert "prod-web-01.corp.example.com" in result["output"]

    def test_no_dns_name_does_not_mention_fqdn(self, svc):
        result = svc.cleanup_records("PROD-WEB-01", dns_name=None)
        assert "Would delete DNS record" not in result["output"]

    def test_dns_name_action_in_output(self, svc):
        result = svc.cleanup_records("SRV", dns_name="srv.example.com")
        assert "Would delete DNS record for srv.example.com" in result["output"]


# ---------------------------------------------------------------------------
# private_ip handling
# ---------------------------------------------------------------------------


class TestCleanupRecordsPrivateIp:
    def test_private_ip_mentioned_in_output(self, svc):
        result = svc.cleanup_records("PROD-WEB-01", private_ip="10.0.1.50")
        assert "10.0.1.50" in result["output"]

    def test_private_ip_action_in_output(self, svc):
        result = svc.cleanup_records("SRV", private_ip="10.0.0.1")
        assert "Would delete A record for private IP 10.0.0.1" in result["output"]

    def test_no_private_ip_no_action_line(self, svc):
        result = svc.cleanup_records("SRV", private_ip=None)
        assert "private IP" not in result["output"]


# ---------------------------------------------------------------------------
# public_ip handling
# ---------------------------------------------------------------------------


class TestCleanupRecordsPublicIp:
    def test_public_ip_mentioned_in_output(self, svc):
        result = svc.cleanup_records("PROD-WEB-01", public_ip="52.10.20.30")
        assert "52.10.20.30" in result["output"]

    def test_public_ip_action_in_output(self, svc):
        result = svc.cleanup_records("SRV", public_ip="1.2.3.4")
        assert "Would delete A record for public IP 1.2.3.4" in result["output"]

    def test_no_public_ip_no_action_line(self, svc):
        result = svc.cleanup_records("SRV", public_ip=None)
        assert "public IP" not in result["output"]


# ---------------------------------------------------------------------------
# No records scenario
# ---------------------------------------------------------------------------


class TestCleanupRecordsNoRecords:
    def test_no_args_exit_code_still_zero(self, svc):
        result = svc.cleanup_records("ORPHAN-SRV")
        assert result["exit_code"] == 0

    def test_no_args_output_mentions_no_records(self, svc):
        result = svc.cleanup_records("ORPHAN-SRV")
        assert "No DNS records to clean up" in result["output"]


# ---------------------------------------------------------------------------
# Multiple fields at once
# ---------------------------------------------------------------------------


class TestCleanupRecordsMultipleFields:
    def test_all_three_fields_appear_in_output(self, svc):
        result = svc.cleanup_records(
            "FULL-SRV",
            dns_name="full-srv.corp.example.com",
            private_ip="10.5.5.5",
            public_ip="54.1.2.3",
        )
        assert "full-srv.corp.example.com" in result["output"]
        assert "10.5.5.5" in result["output"]
        assert "54.1.2.3" in result["output"]
        assert result["exit_code"] == 0

    def test_three_actions_in_output(self, svc):
        result = svc.cleanup_records(
            "FULL-SRV",
            dns_name="srv.example.com",
            private_ip="10.0.0.1",
            public_ip="8.8.8.8",
        )
        # Each action is a bullet line starting with "  - "
        bullet_lines = [line for line in result["output"].splitlines() if line.strip().startswith("-")]
        assert len(bullet_lines) == 3


# ---------------------------------------------------------------------------
# Logging behaviour
# ---------------------------------------------------------------------------


class TestCleanupRecordsLogging:
    def test_dns_name_triggers_info_log(self, svc, caplog):
        with caplog.at_level(logging.INFO, logger="app.services.dns"):
            svc.cleanup_records("SRV", dns_name="svc.corp.com")
        assert "svc.corp.com" in caplog.text

    def test_private_ip_triggers_info_log(self, svc, caplog):
        with caplog.at_level(logging.INFO, logger="app.services.dns"):
            svc.cleanup_records("SRV", private_ip="172.16.0.1")
        assert "172.16.0.1" in caplog.text

    def test_public_ip_triggers_info_log(self, svc, caplog):
        with caplog.at_level(logging.INFO, logger="app.services.dns"):
            svc.cleanup_records("SRV", public_ip="203.0.113.5")
        assert "203.0.113.5" in caplog.text

    def test_no_records_triggers_info_log(self, svc, caplog):
        with caplog.at_level(logging.INFO, logger="app.services.dns"):
            svc.cleanup_records("EMPTY-SRV")
        assert "no records" in caplog.text.lower()
