"""Unit tests for vpn_collector.config (Tasks 2.1–2.4)."""

import textwrap
from pathlib import Path

import pytest

from vpn_collector.config import (
    AppConfig,
    CollectionConfig,
    EmailConfig,
    OutputConfig,
    load_config,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_config(tmp_path: Path, content: str) -> Path:
    """Write *content* to ``config.yaml`` inside *tmp_path* and return the path."""
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(textwrap.dedent(content), encoding="utf-8")
    return cfg_file


# Minimal valid config string — only the required 'devices' key.
_MINIMAL_VALID = """\
    devices:
      - 192.168.1.1
"""

# ---------------------------------------------------------------------------
# 2.1  Dataclass structure
# ---------------------------------------------------------------------------

class TestDataclasses:
    """AppConfig and its nested dataclasses have sensible defaults."""

    def test_collection_defaults(self):
        c = CollectionConfig()
        assert c.max_workers == 20
        assert c.retries == 3
        assert c.retry_backoff_base == 2.0
        assert c.timeout == 30

    def test_output_defaults(self):
        o = OutputConfig()
        assert o.directory == "."
        assert o.excel_filename == "AnyConnect-Sessions.xlsx"

    def test_email_defaults(self):
        e = EmailConfig()
        assert e.enabled is False
        assert e.smtp_port == 587
        assert e.tls is True
        assert e.recipients == []

    def test_app_config_defaults(self):
        a = AppConfig()
        assert a.devices == []
        assert isinstance(a.collection, CollectionConfig)
        assert isinstance(a.output, OutputConfig)
        assert isinstance(a.email, EmailConfig)


# ---------------------------------------------------------------------------
# 2.2  YAML loader
# ---------------------------------------------------------------------------

class TestLoader:
    """load_config() reads YAML files correctly."""

    def test_missing_file_raises_file_not_found(self, tmp_path):
        """A clear FileNotFoundError is raised when config.yaml is absent."""
        missing = tmp_path / "config.yaml"
        with pytest.raises(FileNotFoundError) as exc_info:
            load_config(missing)
        assert "config.yaml" in str(exc_info.value).lower() or str(missing) in str(
            exc_info.value
        )

    def test_missing_file_error_mentions_filename(self, tmp_path):
        """The error message helps the user know what file is missing."""
        missing = tmp_path / "config.yaml"
        with pytest.raises(FileNotFoundError) as exc_info:
            load_config(missing)
        # Should mention the path or a hint like 'config.example.yaml'
        message = str(exc_info.value)
        assert str(missing) in message or "config" in message.lower()

    def test_valid_minimal_config_loads(self, tmp_path):
        """A minimal config (devices only) loads with correct defaults."""
        cfg_file = _write_config(tmp_path, _MINIMAL_VALID)
        cfg = load_config(cfg_file)

        assert cfg.devices == ["192.168.1.1"]
        assert cfg.collection.max_workers == 20
        assert cfg.collection.retries == 3
        assert cfg.collection.retry_backoff_base == 2.0
        assert cfg.collection.timeout == 30
        assert cfg.output.directory == "."
        assert cfg.output.excel_filename == "AnyConnect-Sessions.xlsx"
        assert cfg.email.enabled is False

    def test_returns_app_config_instance(self, tmp_path):
        cfg_file = _write_config(tmp_path, _MINIMAL_VALID)
        cfg = load_config(cfg_file)
        assert isinstance(cfg, AppConfig)

    def test_full_config_overrides_defaults(self, tmp_path):
        """All fields from a full config file are loaded correctly."""
        content = """\
            devices:
              - 10.0.0.1
              - 10.0.0.2
            collection:
              max_workers: 5
              retries: 1
              retry_backoff_base: 1.5
              timeout: 10
            output:
              directory: /tmp/reports
              excel_filename: custom.xlsx
            email:
              enabled: false
              smtp_server: mail.corp.com
              smtp_port: 25
              tls: false
              smtp_username: user
              smtp_password: secret
              from_address: vpn@corp.com
              recipients:
                - ops@corp.com
        """
        cfg_file = _write_config(tmp_path, content)
        cfg = load_config(cfg_file)

        assert cfg.devices == ["10.0.0.1", "10.0.0.2"]
        assert cfg.collection.max_workers == 5
        assert cfg.collection.retries == 1
        assert cfg.collection.retry_backoff_base == 1.5
        assert cfg.collection.timeout == 10
        assert cfg.output.directory == "/tmp/reports"
        assert cfg.output.excel_filename == "custom.xlsx"
        assert cfg.email.smtp_server == "mail.corp.com"
        assert cfg.email.smtp_port == 25
        assert cfg.email.tls is False
        assert cfg.email.from_address == "vpn@corp.com"
        assert cfg.email.recipients == ["ops@corp.com"]


# ---------------------------------------------------------------------------
# 2.3  Validation
# ---------------------------------------------------------------------------

class TestValidation:
    """load_config() raises ValueError listing ALL problems at once."""

    # --- Individual field checks -------------------------------------------

    def test_empty_devices_raises(self, tmp_path):
        """An empty devices list produces a validation error."""
        content = "devices: []\n"
        cfg_file = _write_config(tmp_path, content)
        with pytest.raises(ValueError) as exc_info:
            load_config(cfg_file)
        assert "devices" in str(exc_info.value).lower()

    def test_missing_devices_key_raises(self, tmp_path):
        """A completely absent 'devices' key also produces a validation error."""
        content = "collection:\n  max_workers: 5\n"
        cfg_file = _write_config(tmp_path, content)
        with pytest.raises(ValueError) as exc_info:
            load_config(cfg_file)
        assert "devices" in str(exc_info.value).lower()

    def test_max_workers_zero_raises(self, tmp_path):
        """max_workers: 0 must produce a validation error."""
        content = """\
            devices:
              - 192.168.1.1
            collection:
              max_workers: 0
        """
        cfg_file = _write_config(tmp_path, content)
        with pytest.raises(ValueError) as exc_info:
            load_config(cfg_file)
        assert "max_workers" in str(exc_info.value)

    def test_max_workers_negative_raises(self, tmp_path):
        content = """\
            devices:
              - 192.168.1.1
            collection:
              max_workers: -1
        """
        cfg_file = _write_config(tmp_path, content)
        with pytest.raises(ValueError) as exc_info:
            load_config(cfg_file)
        assert "max_workers" in str(exc_info.value)

    def test_retries_negative_raises(self, tmp_path):
        content = """\
            devices:
              - 192.168.1.1
            collection:
              retries: -1
        """
        cfg_file = _write_config(tmp_path, content)
        with pytest.raises(ValueError) as exc_info:
            load_config(cfg_file)
        assert "retries" in str(exc_info.value)

    def test_retries_zero_is_valid(self, tmp_path):
        """retries: 0 means no retries, which is a valid setting."""
        content = """\
            devices:
              - 192.168.1.1
            collection:
              retries: 0
        """
        cfg_file = _write_config(tmp_path, content)
        cfg = load_config(cfg_file)
        assert cfg.collection.retries == 0

    def test_retry_backoff_base_zero_raises(self, tmp_path):
        content = """\
            devices:
              - 192.168.1.1
            collection:
              retry_backoff_base: 0
        """
        cfg_file = _write_config(tmp_path, content)
        with pytest.raises(ValueError) as exc_info:
            load_config(cfg_file)
        assert "retry_backoff_base" in str(exc_info.value)

    def test_retry_backoff_base_negative_raises(self, tmp_path):
        content = """\
            devices:
              - 192.168.1.1
            collection:
              retry_backoff_base: -1.0
        """
        cfg_file = _write_config(tmp_path, content)
        with pytest.raises(ValueError) as exc_info:
            load_config(cfg_file)
        assert "retry_backoff_base" in str(exc_info.value)

    def test_timeout_zero_raises(self, tmp_path):
        content = """\
            devices:
              - 192.168.1.1
            collection:
              timeout: 0
        """
        cfg_file = _write_config(tmp_path, content)
        with pytest.raises(ValueError) as exc_info:
            load_config(cfg_file)
        assert "timeout" in str(exc_info.value)

    # --- Email-specific checks when enabled --------------------------------

    def test_email_enabled_missing_smtp_server_raises(self, tmp_path):
        """email.enabled=true with blank smtp_server must raise."""
        content = """\
            devices:
              - 192.168.1.1
            email:
              enabled: true
              smtp_server: ""
              from_address: "vpn@corp.com"
              recipients:
                - ops@corp.com
        """
        cfg_file = _write_config(tmp_path, content)
        with pytest.raises(ValueError) as exc_info:
            load_config(cfg_file)
        assert "smtp_server" in str(exc_info.value)

    def test_email_enabled_missing_from_address_raises(self, tmp_path):
        content = """\
            devices:
              - 192.168.1.1
            email:
              enabled: true
              smtp_server: "mail.corp.com"
              from_address: ""
              recipients:
                - ops@corp.com
        """
        cfg_file = _write_config(tmp_path, content)
        with pytest.raises(ValueError) as exc_info:
            load_config(cfg_file)
        assert "from_address" in str(exc_info.value)

    def test_email_enabled_empty_recipients_raises(self, tmp_path):
        content = """\
            devices:
              - 192.168.1.1
            email:
              enabled: true
              smtp_server: "mail.corp.com"
              from_address: "vpn@corp.com"
              recipients: []
        """
        cfg_file = _write_config(tmp_path, content)
        with pytest.raises(ValueError) as exc_info:
            load_config(cfg_file)
        assert "recipients" in str(exc_info.value)

    def test_email_disabled_smtp_fields_not_checked(self, tmp_path):
        """When email.enabled is false, smtp fields are not validated."""
        content = """\
            devices:
              - 192.168.1.1
            email:
              enabled: false
              smtp_server: ""
              from_address: ""
              recipients: []
        """
        cfg_file = _write_config(tmp_path, content)
        # Should NOT raise
        cfg = load_config(cfg_file)
        assert cfg.email.enabled is False

    # --- Multiple errors collected together --------------------------------

    def test_multiple_errors_reported_together(self, tmp_path):
        """When several fields are invalid, all errors appear in one ValueError."""
        content = """\
            devices: []
            collection:
              max_workers: 0
              retries: -1
              retry_backoff_base: 0
              timeout: 0
        """
        cfg_file = _write_config(tmp_path, content)
        with pytest.raises(ValueError) as exc_info:
            load_config(cfg_file)
        message = str(exc_info.value)
        assert "devices" in message.lower()
        assert "max_workers" in message
        assert "retries" in message
        assert "retry_backoff_base" in message
        assert "timeout" in message

    def test_multiple_email_errors_collected(self, tmp_path):
        """All three email fields can fail simultaneously."""
        content = """\
            devices:
              - 192.168.1.1
            email:
              enabled: true
              smtp_server: ""
              from_address: ""
              recipients: []
        """
        cfg_file = _write_config(tmp_path, content)
        with pytest.raises(ValueError) as exc_info:
            load_config(cfg_file)
        message = str(exc_info.value)
        assert "smtp_server" in message
        assert "from_address" in message
        assert "recipients" in message

    # --- Type guard tests (CRITICAL 1) ------------------------------------

    def test_max_workers_wrong_type_raises(self, tmp_path):
        """max_workers with a non-integer value raises a clean type error."""
        content = """\
            devices:
              - 192.168.1.1
            collection:
              max_workers: "banana"
        """
        cfg_file = _write_config(tmp_path, content)
        with pytest.raises(ValueError) as exc_info:
            load_config(cfg_file)
        message = str(exc_info.value)
        assert "max_workers" in message
        assert "int" in message.lower() or "str" in message.lower()

    def test_retries_wrong_type_raises(self, tmp_path):
        """retries with a non-integer value raises a clean type error."""
        content = """\
            devices:
              - 192.168.1.1
            collection:
              retries: "three"
        """
        cfg_file = _write_config(tmp_path, content)
        with pytest.raises(ValueError) as exc_info:
            load_config(cfg_file)
        message = str(exc_info.value)
        assert "retries" in message
        assert "int" in message.lower() or "str" in message.lower()

    def test_retry_backoff_base_wrong_type_raises(self, tmp_path):
        """retry_backoff_base with a non-numeric value raises a clean type error."""
        content = """\
            devices:
              - 192.168.1.1
            collection:
              retry_backoff_base: "fast"
        """
        cfg_file = _write_config(tmp_path, content)
        with pytest.raises(ValueError) as exc_info:
            load_config(cfg_file)
        message = str(exc_info.value)
        assert "retry_backoff_base" in message
        assert "int" in message.lower() or "float" in message.lower() or "str" in message.lower()

    def test_timeout_wrong_type_raises(self, tmp_path):
        """timeout with a non-numeric value raises a clean type error."""
        content = """\
            devices:
              - 192.168.1.1
            collection:
              timeout: "quick"
        """
        cfg_file = _write_config(tmp_path, content)
        with pytest.raises(ValueError) as exc_info:
            load_config(cfg_file)
        message = str(exc_info.value)
        assert "timeout" in message
        assert "int" in message.lower() or "float" in message.lower() or "str" in message.lower()

    # --- Non-list devices/recipients (CRITICAL 2) -------------------------

    def test_devices_as_scalar_string_raises(self, tmp_path):
        """A scalar string for 'devices' raises a helpful type error."""
        content = "devices: 192.168.1.1\n"
        cfg_file = _write_config(tmp_path, content)
        with pytest.raises(ValueError) as exc_info:
            load_config(cfg_file)
        message = str(exc_info.value)
        assert "devices" in message.lower()

    def test_recipients_as_scalar_string_raises(self, tmp_path):
        """A scalar string for 'recipients' raises a helpful type error, not a char list."""
        content = """\
            devices:
              - 192.168.1.1
            email:
              enabled: true
              smtp_server: "mail.corp.com"
              from_address: "vpn@corp.com"
              recipients: ops@corp.com
        """
        cfg_file = _write_config(tmp_path, content)
        with pytest.raises(ValueError) as exc_info:
            load_config(cfg_file)
        message = str(exc_info.value)
        assert "recipients" in message.lower()

    # --- smtp_port range validation (IMPORTANT 4) -------------------------

    def test_smtp_port_zero_raises(self, tmp_path):
        """smtp_port of 0 is out of valid range and must raise."""
        content = """\
            devices:
              - 192.168.1.1
            email:
              enabled: true
              smtp_server: "mail.corp.com"
              from_address: "vpn@corp.com"
              smtp_port: 0
              recipients:
                - ops@corp.com
        """
        cfg_file = _write_config(tmp_path, content)
        with pytest.raises(ValueError) as exc_info:
            load_config(cfg_file)
        assert "smtp_port" in str(exc_info.value)

    def test_smtp_port_too_large_raises(self, tmp_path):
        """smtp_port above 65535 is out of valid range and must raise."""
        content = """\
            devices:
              - 192.168.1.1
            email:
              enabled: true
              smtp_server: "mail.corp.com"
              from_address: "vpn@corp.com"
              smtp_port: 99999
              recipients:
                - ops@corp.com
        """
        cfg_file = _write_config(tmp_path, content)
        with pytest.raises(ValueError) as exc_info:
            load_config(cfg_file)
        assert "smtp_port" in str(exc_info.value)

    def test_smtp_port_valid_boundary_values(self, tmp_path):
        """smtp_port values of 1 and 65535 are valid."""
        for port in (1, 65535):
            content = f"""\
                devices:
                  - 192.168.1.1
                email:
                  enabled: true
                  smtp_server: "mail.corp.com"
                  from_address: "vpn@corp.com"
                  smtp_port: {port}
                  recipients:
                    - ops@corp.com
            """
            cfg_file = _write_config(tmp_path, content)
            cfg = load_config(cfg_file)
            assert cfg.email.smtp_port == port

    def test_smtp_port_always_validated_when_disabled(self, tmp_path):
        """An invalid smtp_port raises even when email is disabled."""
        content = """\
            devices:
              - 192.168.1.1
            email:
              enabled: false
              smtp_port: 0
        """
        cfg_file = _write_config(tmp_path, content)
        with pytest.raises(ValueError) as exc_info:
            load_config(cfg_file)
        assert "smtp_port" in str(exc_info.value)

    def test_smtp_port_valid_when_email_disabled_passes(self, tmp_path):
        """A valid smtp_port does not raise even when email is disabled."""
        content = """\
            devices:
              - 192.168.1.1
            email:
              enabled: false
              smtp_port: 587
        """
        cfg_file = _write_config(tmp_path, content)
        cfg = load_config(cfg_file)
        assert cfg.email.enabled is False
        assert cfg.email.smtp_port == 587

    # --- Truthy non-dict section values (CRITICAL 1) ----------------------

    def test_collection_scalar_raises_not_attribute_error(self, tmp_path):
        """A truthy scalar for 'collection' (e.g. 42) raises ValueError, not AttributeError."""
        content = """\
            devices:
              - 192.168.1.1
            collection: 42
        """
        cfg_file = _write_config(tmp_path, content)
        with pytest.raises(ValueError) as exc_info:
            load_config(cfg_file)
        assert "collection" in str(exc_info.value)

    # --- Bool values silently pass int checks (CRITICAL 2) ----------------

    def test_max_workers_bool_raises(self, tmp_path):
        """max_workers: true (a bool) must be rejected as a type error."""
        content = """\
            devices:
              - 192.168.1.1
            collection:
              max_workers: true
        """
        cfg_file = _write_config(tmp_path, content)
        with pytest.raises(ValueError) as exc_info:
            load_config(cfg_file)
        assert "max_workers" in str(exc_info.value)

    def test_smtp_port_string_enabled_raises(self, tmp_path):
        """smtp_port: \"587\" (string) with email enabled raises a type error."""
        content = """\
            devices:
              - 192.168.1.1
            email:
              enabled: true
              smtp_server: "mail.corp.com"
              from_address: "vpn@corp.com"
              smtp_port: "587"
              recipients:
                - ops@corp.com
        """
        cfg_file = _write_config(tmp_path, content)
        with pytest.raises(ValueError) as exc_info:
            load_config(cfg_file)
        assert "smtp_port" in str(exc_info.value)

    def test_smtp_port_string_disabled_raises(self, tmp_path):
        """smtp_port: \"587\" (string) with email disabled still raises a type error."""
        content = """\
            devices:
              - 192.168.1.1
            email:
              enabled: false
              smtp_port: "587"
        """
        cfg_file = _write_config(tmp_path, content)
        with pytest.raises(ValueError) as exc_info:
            load_config(cfg_file)
        assert "smtp_port" in str(exc_info.value)
