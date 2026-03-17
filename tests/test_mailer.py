"""Tests for vpn_collector.mailer (Tasks 8.1–8.6)."""

from __future__ import annotations

import logging
import smtplib
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

from vpn_collector.config import AppConfig, EmailConfig
from vpn_collector.mailer import send_report, _build_html_body, _build_text_body, _EMAIL_SUBJECT


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

_SUMMARY = {
    "timestamp": "2024-06-01T12:00:00+00:00",
    "total_devices": 3,
    "successful_devices": 2,
    "total_sessions": 15,
    "devices": [
        {"host": "fw1.example.com", "sessions": 10, "status": "ok"},
        {"host": "fw2.example.com", "sessions": 5, "status": "ok"},
        {"host": "fw3.example.com", "sessions": 0, "status": "error"},
    ],
}


def _make_config(
    *,
    tls: bool = True,
    smtp_username: str = "",
    smtp_password: str = "",
    recipients: list[str] | None = None,
) -> AppConfig:
    config = AppConfig()
    config.email = EmailConfig(
        enabled=True,
        smtp_server="smtp.example.com",
        smtp_port=587,
        tls=tls,
        smtp_username=smtp_username,
        smtp_password=smtp_password,
        from_address="noreply@example.com",
        recipients=recipients if recipients is not None else ["user@example.com"],
    )
    return config


def _make_files(tmp_path: Path, count: int = 2) -> list[Path]:
    files = []
    for i in range(count):
        p = tmp_path / f"report_{i}.xlsx"
        p.write_bytes(b"fake-content-%d" % i)
        files.append(p)
    return files


# ---------------------------------------------------------------------------
# 8.5 — Empty files guard
# ---------------------------------------------------------------------------

class TestEmptyFilesGuard:
    def test_no_smtp_connection_when_files_empty(self) -> None:
        config = _make_config()
        with patch("vpn_collector.mailer.smtplib.SMTP") as mock_smtp_cls:
            send_report([], _SUMMARY, config)
            mock_smtp_cls.assert_not_called()

    def test_warning_logged_when_files_empty(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        config = _make_config()
        pkg_logger = logging.getLogger("vpn_collector")
        original_propagate = pkg_logger.propagate
        try:
            pkg_logger.propagate = True
            with caplog.at_level(logging.WARNING, logger="vpn_collector.mailer"):
                send_report([], _SUMMARY, config)
        finally:
            pkg_logger.propagate = original_propagate
        assert "No output files to attach" in caplog.text


# ---------------------------------------------------------------------------
# 8.4 — SMTP logic: TLS
# ---------------------------------------------------------------------------

class TestSmtpTls:
    def test_starttls_called_when_tls_true(self, tmp_path: Path) -> None:
        config = _make_config(tls=True)
        files = _make_files(tmp_path)
        with patch("vpn_collector.mailer.smtplib.SMTP") as mock_smtp_cls:
            mock_server = MagicMock()
            mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
            mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
            send_report(files, _SUMMARY, config)
            mock_server.starttls.assert_called_once()

    def test_starttls_not_called_when_tls_false(self, tmp_path: Path) -> None:
        config = _make_config(tls=False)
        files = _make_files(tmp_path)
        with patch("vpn_collector.mailer.smtplib.SMTP") as mock_smtp_cls:
            mock_server = MagicMock()
            mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
            mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
            send_report(files, _SUMMARY, config)
            mock_server.starttls.assert_not_called()

    def test_warning_logged_when_tls_false(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        config = _make_config(tls=False)
        files = _make_files(tmp_path)
        pkg_logger = logging.getLogger("vpn_collector")
        original_propagate = pkg_logger.propagate
        try:
            pkg_logger.propagate = True
            with patch("vpn_collector.mailer.smtplib.SMTP") as mock_smtp_cls:
                mock_server = MagicMock()
                mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
                mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
                with caplog.at_level(logging.WARNING, logger="vpn_collector.mailer"):
                    send_report(files, _SUMMARY, config)
        finally:
            pkg_logger.propagate = original_propagate
        assert "without TLS" in caplog.text
        assert "plaintext" in caplog.text


# ---------------------------------------------------------------------------
# 8.4 — SMTP logic: login
# ---------------------------------------------------------------------------

class TestSmtpLogin:
    def test_login_called_when_username_non_empty(self, tmp_path: Path) -> None:
        config = _make_config(smtp_username="user@example.com", smtp_password="secret")
        files = _make_files(tmp_path)
        with patch("vpn_collector.mailer.smtplib.SMTP") as mock_smtp_cls:
            mock_server = MagicMock()
            mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
            mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
            send_report(files, _SUMMARY, config)
            mock_server.login.assert_called_once_with("user@example.com", "secret")

    def test_login_not_called_when_username_empty(self, tmp_path: Path) -> None:
        config = _make_config(smtp_username="")
        files = _make_files(tmp_path)
        with patch("vpn_collector.mailer.smtplib.SMTP") as mock_smtp_cls:
            mock_server = MagicMock()
            mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
            mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
            send_report(files, _SUMMARY, config)
            mock_server.login.assert_not_called()


# ---------------------------------------------------------------------------
# 8.4 — SMTP logic: success logging
# ---------------------------------------------------------------------------

class TestSmtpSuccessLogging:
    def test_info_logged_on_success(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        config = _make_config(recipients=["a@example.com", "b@example.com"])
        files = _make_files(tmp_path)
        pkg_logger = logging.getLogger("vpn_collector")
        original_propagate = pkg_logger.propagate
        try:
            pkg_logger.propagate = True
            with patch("vpn_collector.mailer.smtplib.SMTP") as mock_smtp_cls:
                mock_server = MagicMock()
                mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
                mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
                with caplog.at_level(logging.INFO, logger="vpn_collector.mailer"):
                    send_report(files, _SUMMARY, config)
        finally:
            pkg_logger.propagate = original_propagate
        assert "Email sent to 2 recipients" in caplog.text

    def test_smtp_called_with_correct_server_and_port(self, tmp_path: Path) -> None:
        config = _make_config()
        files = _make_files(tmp_path)
        with patch("vpn_collector.mailer.smtplib.SMTP") as mock_smtp_cls:
            mock_server = MagicMock()
            mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
            mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
            send_report(files, _SUMMARY, config)
            mock_smtp_cls.assert_called_once_with("smtp.example.com", 587)


# ---------------------------------------------------------------------------
# 8.6 — Exception handling
# ---------------------------------------------------------------------------

class TestExceptionHandling:
    def test_smtp_exception_logged_as_error(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        config = _make_config()
        files = _make_files(tmp_path)
        pkg_logger = logging.getLogger("vpn_collector")
        original_propagate = pkg_logger.propagate
        try:
            pkg_logger.propagate = True
            with patch("vpn_collector.mailer.smtplib.SMTP") as mock_smtp_cls:
                mock_smtp_cls.return_value.__enter__ = MagicMock(
                    side_effect=smtplib.SMTPException("connection failed")
                )
                mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
                with caplog.at_level(logging.ERROR, logger="vpn_collector.mailer"):
                    send_report(files, _SUMMARY, config)
        finally:
            pkg_logger.propagate = original_propagate
        assert any(
            record.levelno == logging.ERROR for record in caplog.records
        )

    def test_smtp_exception_not_raised(self, tmp_path: Path) -> None:
        config = _make_config()
        files = _make_files(tmp_path)
        with patch("vpn_collector.mailer.smtplib.SMTP") as mock_smtp_cls:
            mock_smtp_cls.return_value.__enter__ = MagicMock(
                side_effect=smtplib.SMTPException("boom")
            )
            mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
            # Must not raise
            send_report(files, _SUMMARY, config)

    def test_oserror_logged_as_error(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        config = _make_config()
        files = _make_files(tmp_path)
        pkg_logger = logging.getLogger("vpn_collector")
        original_propagate = pkg_logger.propagate
        try:
            pkg_logger.propagate = True
            with patch("vpn_collector.mailer.smtplib.SMTP") as mock_smtp_cls:
                mock_smtp_cls.return_value.__enter__ = MagicMock(
                    side_effect=OSError("Connection refused")
                )
                mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
                with caplog.at_level(logging.ERROR, logger="vpn_collector.mailer"):
                    send_report(files, _SUMMARY, config)
        finally:
            pkg_logger.propagate = original_propagate
        assert any(
            record.levelno == logging.ERROR for record in caplog.records
        )

    def test_oserror_not_raised(self, tmp_path: Path) -> None:
        config = _make_config()
        files = _make_files(tmp_path)
        with patch("vpn_collector.mailer.smtplib.SMTP") as mock_smtp_cls:
            mock_smtp_cls.return_value.__enter__ = MagicMock(
                side_effect=OSError("DNS failure")
            )
            mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
            # Must not raise
            send_report(files, _SUMMARY, config)


# ---------------------------------------------------------------------------
# 8.2 — HTML body content
# ---------------------------------------------------------------------------

class TestHtmlBody:
    def test_html_contains_timestamp(self) -> None:
        html = _build_html_body(_SUMMARY)
        assert "2024-06-01T12:00:00+00:00" in html

    def test_html_contains_total_devices(self) -> None:
        html = _build_html_body(_SUMMARY)
        assert "3" in html

    def test_html_contains_successful_devices(self) -> None:
        html = _build_html_body(_SUMMARY)
        assert "2" in html

    def test_html_contains_total_sessions(self) -> None:
        html = _build_html_body(_SUMMARY)
        assert "15" in html

    def test_html_contains_table_tag(self) -> None:
        html = _build_html_body(_SUMMARY)
        assert "<table" in html

    def test_html_contains_device_host(self) -> None:
        html = _build_html_body(_SUMMARY)
        assert "fw1.example.com" in html

    def test_html_contains_device_sessions(self) -> None:
        html = _build_html_body(_SUMMARY)
        assert "10" in html

    def test_html_contains_device_status(self) -> None:
        html = _build_html_body(_SUMMARY)
        assert "ok" in html

    def test_html_contains_all_devices(self) -> None:
        html = _build_html_body(_SUMMARY)
        for device in _SUMMARY["devices"]:
            assert device["host"] in html

    def test_html_has_column_headers(self) -> None:
        html = _build_html_body(_SUMMARY)
        assert "Host" in html
        assert "Sessions" in html
        assert "Status" in html

    def test_html_escapes_device_hostname(self) -> None:
        """HTML escaping: device hostnames with malicious HTML are escaped."""
        summary = {
            "timestamp": "2024-06-01T12:00:00+00:00",
            "total_devices": 1,
            "successful_devices": 1,
            "total_sessions": 0,
            "devices": [
                {"host": "<evil>&", "sessions": 0, "status": "ok"},
            ],
        }
        html = _build_html_body(summary)
        # Verify that HTML entities are used instead of raw HTML
        assert "&lt;evil&gt;&amp;" in html
        assert "<evil>&" not in html or "&lt;evil&gt;&amp;" in html


# ---------------------------------------------------------------------------
# 8.3 — Plain-text body content
# ---------------------------------------------------------------------------

class TestTextBody:
    def test_text_contains_timestamp(self) -> None:
        text = _build_text_body(_SUMMARY)
        assert "2024-06-01T12:00:00+00:00" in text

    def test_text_contains_total_devices(self) -> None:
        text = _build_text_body(_SUMMARY)
        assert "3" in text

    def test_text_contains_successful_devices(self) -> None:
        text = _build_text_body(_SUMMARY)
        assert "2" in text

    def test_text_contains_total_sessions(self) -> None:
        text = _build_text_body(_SUMMARY)
        assert "15" in text

    def test_text_no_html_tags(self) -> None:
        text = _build_text_body(_SUMMARY)
        assert "<" not in text
        assert ">" not in text

    def test_text_contains_device_host(self) -> None:
        text = _build_text_body(_SUMMARY)
        assert "fw1.example.com" in text

    def test_text_contains_all_devices(self) -> None:
        text = _build_text_body(_SUMMARY)
        for device in _SUMMARY["devices"]:
            assert device["host"] in text


# ---------------------------------------------------------------------------
# 8.1 — Attachment count
# ---------------------------------------------------------------------------

class TestAttachments:
    def test_attachment_count_matches_files(self, tmp_path: Path) -> None:
        """The number of binary attachments must equal len(files)."""
        config = _make_config()
        files = _make_files(tmp_path, count=3)
        captured_messages: list[str] = []

        with patch("vpn_collector.mailer.smtplib.SMTP") as mock_smtp_cls:
            mock_server = MagicMock()
            mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
            mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

            def capture_sendmail(from_addr, to_addrs, msg_string):
                captured_messages.append(msg_string)

            mock_server.sendmail.side_effect = capture_sendmail
            send_report(files, _SUMMARY, config)

        assert len(captured_messages) == 1
        # Parse the MIME message and count attachments
        import email
        msg = email.message_from_string(captured_messages[0])
        attachments = [
            part for part in msg.walk()
            if part.get_content_disposition() == "attachment"
        ]
        assert len(attachments) == 3

    def test_single_file_attached(self, tmp_path: Path) -> None:
        config = _make_config()
        files = _make_files(tmp_path, count=1)
        captured_messages: list[str] = []

        with patch("vpn_collector.mailer.smtplib.SMTP") as mock_smtp_cls:
            mock_server = MagicMock()
            mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
            mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

            def capture_sendmail(from_addr, to_addrs, msg_string):
                captured_messages.append(msg_string)

            mock_server.sendmail.side_effect = capture_sendmail
            send_report(files, _SUMMARY, config)

        import email
        msg = email.message_from_string(captured_messages[0])
        attachments = [
            part for part in msg.walk()
            if part.get_content_disposition() == "attachment"
        ]
        assert len(attachments) == 1

    def test_attachment_filename_matches(self, tmp_path: Path) -> None:
        config = _make_config()
        files = _make_files(tmp_path, count=1)
        captured_messages: list[str] = []

        with patch("vpn_collector.mailer.smtplib.SMTP") as mock_smtp_cls:
            mock_server = MagicMock()
            mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
            mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

            def capture_sendmail(from_addr, to_addrs, msg_string):
                captured_messages.append(msg_string)

            mock_server.sendmail.side_effect = capture_sendmail
            send_report(files, _SUMMARY, config)

        import email
        msg = email.message_from_string(captured_messages[0])
        attachment = next(
            part for part in msg.walk()
            if part.get_content_disposition() == "attachment"
        )
        assert attachment.get_filename() == files[0].name


# ---------------------------------------------------------------------------
# 8.1 — Message headers
# ---------------------------------------------------------------------------

class TestMessageHeaders:
    def test_from_header_set(self, tmp_path: Path) -> None:
        config = _make_config()
        files = _make_files(tmp_path)
        captured_messages: list[str] = []

        with patch("vpn_collector.mailer.smtplib.SMTP") as mock_smtp_cls:
            mock_server = MagicMock()
            mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
            mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

            def capture_sendmail(from_addr, to_addrs, msg_string):
                captured_messages.append(msg_string)

            mock_server.sendmail.side_effect = capture_sendmail
            send_report(files, _SUMMARY, config)

        import email
        msg = email.message_from_string(captured_messages[0])
        assert msg["From"] == "noreply@example.com"

    def test_to_header_contains_all_recipients(self, tmp_path: Path) -> None:
        config = _make_config(recipients=["alice@example.com", "bob@example.com"])
        files = _make_files(tmp_path)
        captured_messages: list[str] = []

        with patch("vpn_collector.mailer.smtplib.SMTP") as mock_smtp_cls:
            mock_server = MagicMock()
            mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
            mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

            def capture_sendmail(from_addr, to_addrs, msg_string):
                captured_messages.append(msg_string)

            mock_server.sendmail.side_effect = capture_sendmail
            send_report(files, _SUMMARY, config)

        import email
        msg = email.message_from_string(captured_messages[0])
        to_header = msg["To"]
        assert "alice@example.com" in to_header
        assert "bob@example.com" in to_header

    def test_subject_header_set(self, tmp_path: Path) -> None:
        config = _make_config()
        files = _make_files(tmp_path)
        captured_messages: list[str] = []

        with patch("vpn_collector.mailer.smtplib.SMTP") as mock_smtp_cls:
            mock_server = MagicMock()
            mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
            mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

            def capture_sendmail(from_addr, to_addrs, msg_string):
                captured_messages.append(msg_string)

            mock_server.sendmail.side_effect = capture_sendmail
            send_report(files, _SUMMARY, config)

        import email
        msg = email.message_from_string(captured_messages[0])
        assert msg["Subject"] == _EMAIL_SUBJECT
