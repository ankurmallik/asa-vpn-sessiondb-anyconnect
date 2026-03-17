"""Unit tests for vpn_collector.parser (Tasks 6.1–6.4)."""

import logging

import pytest

from vpn_collector.parser import parse_sessions


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_vpn_collector_logger():
    """Ensure the vpn_collector logger always propagates to the root logger.

    Some cli tests call _setup_logging() which sets propagate=False on the
    'vpn_collector' logger.  That prevents pytest's caplog handler (attached
    to the root logger) from capturing records emitted by child loggers such
    as 'vpn_collector.parser'.  This fixture restores propagation after every
    test so the suite is order-independent.
    """
    parent = logging.getLogger("vpn_collector")
    original_propagate = parent.propagate
    parent.propagate = True
    yield
    parent.propagate = original_propagate


# ---------------------------------------------------------------------------
# Fixture strings
# ---------------------------------------------------------------------------

_TWO_SESSIONS = """\
Session Type: AnyConnect-Parent

Username     : jsmith           Index        : 12345
Assigned IP  : 10.10.1.100      Public IP    : 203.0.113.50
Protocol     : AnyConnect-Parent SSL-Tunnel DTLS-Tunnel
License      : AnyConnect Premium
Encryption   : AnyConnect-Parent: (1)none  SSL-Tunnel: (1)RC4      DTLS-Tunnel: (1)AES128
Hashing      : AnyConnect-Parent: (1)none  SSL-Tunnel: (1)SHA1     DTLS-Tunnel: (1)SHA1
Bytes Tx     : 12345678         Bytes Rx     : 87654321
Group Policy : GroupPolicy_RemoteAccess      Tunnel Group : RA-VPN-Group
Login Time   : 09:30:15 UTC Mon Mar 17 2025
Duration     : 2h:15m:30s
Inactivity   : 0h:02:10s
VLAN Mapping : N/A              VLAN         : none
Audt Sess ID : 0a000001000000010000000000000000
Security Grp : none

Username     : bjones           Index        : 12346
Assigned IP  : 10.10.1.101      Public IP    : 198.51.100.22
Protocol     : AnyConnect-Parent SSL-Tunnel DTLS-Tunnel
License      : AnyConnect Premium
Encryption   : AnyConnect-Parent: (1)none  SSL-Tunnel: (1)RC4      DTLS-Tunnel: (1)AES128
Hashing      : AnyConnect-Parent: (1)none  SSL-Tunnel: (1)SHA1     DTLS-Tunnel: (1)SHA1
Bytes Tx     : 5000000          Bytes Rx     : 3000000
Group Policy : GroupPolicy_RemoteAccess      Tunnel Group : RA-VPN-Group
Login Time   : 10:15:00 UTC Mon Mar 17 2025
Duration     : 1h:30m:00s
Inactivity   : 0h:00:30s
VLAN Mapping : N/A              VLAN         : none
Audt Sess ID : 0a000001000000020000000000000000
Security Grp : none
"""

_NO_ACTIVE_SESSIONS = (
    "There are no active AnyConnect-Parent sessions."
)

_MALFORMED = "this is total garbage that will not match any template fields"


# ---------------------------------------------------------------------------
# Tests: normal two-session output
# ---------------------------------------------------------------------------

class TestTwoSessions:
    def test_returns_two_records(self):
        result = parse_sessions(_TWO_SESSIONS, "fw1")
        assert len(result) == 2

    def test_records_are_dicts(self):
        result = parse_sessions(_TWO_SESSIONS, "fw1")
        for rec in result:
            assert isinstance(rec, dict)

    def test_first_session_username(self):
        result = parse_sessions(_TWO_SESSIONS, "fw1")
        assert result[0]["username"] == "jsmith"

    def test_second_session_username(self):
        result = parse_sessions(_TWO_SESSIONS, "fw1")
        assert result[1]["username"] == "bjones"

    def test_first_session_assigned_ip(self):
        result = parse_sessions(_TWO_SESSIONS, "fw1")
        assert result[0]["assigned_ip"] == "10.10.1.100"

    def test_second_session_assigned_ip(self):
        result = parse_sessions(_TWO_SESSIONS, "fw1")
        assert result[1]["assigned_ip"] == "10.10.1.101"

    def test_first_session_public_ip(self):
        result = parse_sessions(_TWO_SESSIONS, "fw1")
        assert result[0]["public_ip"] == "203.0.113.50"

    def test_second_session_public_ip(self):
        result = parse_sessions(_TWO_SESSIONS, "fw1")
        assert result[1]["public_ip"] == "198.51.100.22"

    def test_first_session_bytes_tx(self):
        result = parse_sessions(_TWO_SESSIONS, "fw1")
        assert result[0]["bytes_tx"] == "12345678"

    def test_first_session_bytes_rx(self):
        result = parse_sessions(_TWO_SESSIONS, "fw1")
        assert result[0]["bytes_rx"] == "87654321"

    def test_second_session_bytes_tx(self):
        result = parse_sessions(_TWO_SESSIONS, "fw1")
        assert result[1]["bytes_tx"] == "5000000"

    def test_first_session_index(self):
        result = parse_sessions(_TWO_SESSIONS, "fw1")
        assert result[0]["index"] == "12345"

    def test_second_session_index(self):
        result = parse_sessions(_TWO_SESSIONS, "fw1")
        assert result[1]["index"] == "12346"

    def test_first_session_group_policy(self):
        result = parse_sessions(_TWO_SESSIONS, "fw1")
        assert result[0]["group_policy"] == "GroupPolicy_RemoteAccess"

    def test_first_session_tunnel_group(self):
        result = parse_sessions(_TWO_SESSIONS, "fw1")
        assert result[0]["tunnel_group"] == "RA-VPN-Group"

    def test_first_session_duration(self):
        result = parse_sessions(_TWO_SESSIONS, "fw1")
        assert result[0]["duration"] == "2h:15m:30s"

    def test_first_session_login_time(self):
        result = parse_sessions(_TWO_SESSIONS, "fw1")
        assert result[0]["login_time"] == "09:30:15"

    def test_first_session_login_year(self):
        result = parse_sessions(_TWO_SESSIONS, "fw1")
        assert result[0]["login_year"] == "2025"

    def test_first_session_audt_sess_id(self):
        result = parse_sessions(_TWO_SESSIONS, "fw1")
        assert result[0]["audt_sess_id"] == "0a000001000000010000000000000000"

    def test_expected_keys_present(self):
        result = parse_sessions(_TWO_SESSIONS, "fw1")
        expected_keys = {
            "session_type", "username", "index", "assigned_ip", "public_ip",
            "protocol", "license", "encryption", "hashing", "bytes_tx",
            "bytes_rx", "group_policy", "tunnel_group", "login_time",
            "duration", "inactivity", "vlan_mapping", "vlan_id",
            "audt_sess_id", "security_grp",
        }
        for rec in result:
            assert expected_keys.issubset(rec.keys())


# ---------------------------------------------------------------------------
# Tests: zero-session output
# ---------------------------------------------------------------------------

class TestNoActiveSessions:
    def test_no_active_returns_empty_list(self):
        result = parse_sessions(_NO_ACTIVE_SESSIONS, "fw1")
        assert result == []

    def test_no_active_returns_list_type(self):
        result = parse_sessions(_NO_ACTIVE_SESSIONS, "fw1")
        assert isinstance(result, list)

    def test_no_active_variant_message(self):
        output = "There are no active SSL-Tunnel sessions."
        result = parse_sessions(output, "fw2")
        assert result == []


# ---------------------------------------------------------------------------
# Tests: empty string input
# ---------------------------------------------------------------------------

class TestEmptyString:
    def test_empty_string_returns_empty_list(self):
        result = parse_sessions("", "fw1")
        assert result == []

    def test_empty_string_returns_list_type(self):
        result = parse_sessions("", "fw1")
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# Tests: malformed output (TextFSM no-match path)
# ---------------------------------------------------------------------------

class TestMalformedOutput:
    def test_malformed_returns_empty_list(self):
        result = parse_sessions(_MALFORMED, "fw1")
        assert result == []

    def test_malformed_returns_list_type(self):
        result = parse_sessions(_MALFORMED, "fw1")
        assert isinstance(result, list)

    def test_malformed_logs_warning_on_exception(self, monkeypatch, caplog):
        """Force an exception inside parse_output and verify the WARNING is logged."""
        import vpn_collector.parser as parser_module

        def _raise(*args, **kwargs):
            raise RuntimeError("simulated TextFSM failure")

        monkeypatch.setattr(parser_module, "parse_output", _raise)

        with caplog.at_level(logging.WARNING, logger="vpn_collector.parser"):
            result = parse_sessions("some output", "fw-bad")

        assert result == []
        assert any(
            "TextFSM parse failed" in msg
            for msg in caplog.messages
        )

    def test_malformed_warning_contains_host(self, monkeypatch, caplog):
        """The WARNING message must contain the device host name."""
        import vpn_collector.parser as parser_module

        def _raise(*args, **kwargs):
            raise ValueError("bad template")

        monkeypatch.setattr(parser_module, "parse_output", _raise)

        with caplog.at_level(logging.WARNING, logger="vpn_collector.parser"):
            parse_sessions("some output", "192.0.2.1")

        assert any(
            "192.0.2.1" in msg
            for msg in caplog.messages
        )
