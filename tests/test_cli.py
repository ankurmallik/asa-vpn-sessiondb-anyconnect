"""Unit tests for vpn_collector.cli."""

import logging
import sys
import textwrap
from pathlib import Path

import pytest
import yaml

from vpn_collector.cli import _apply_overrides, _build_parser, _setup_logging
from vpn_collector.config import AppConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse(args: list[str]):
    """Return a parsed Namespace from _build_parser()."""
    return _build_parser().parse_args(args)


# ---------------------------------------------------------------------------
# 1. _build_parser() — all 9 flags
# ---------------------------------------------------------------------------

class TestBuildParser:
    def test_excel_flag(self):
        args = _parse(["--excel"])
        assert args.excel is True

    def test_csv_flag(self):
        args = _parse(["--csv"])
        assert args.csv is True

    def test_json_flag(self):
        args = _parse(["--json"])
        assert args.json is True

    def test_email_flag(self):
        args = _parse(["--email"])
        assert args.email is True

    def test_devices_flag(self):
        args = _parse(["--devices", "10.0.0.1", "10.0.0.2"])
        assert args.devices == ["10.0.0.1", "10.0.0.2"]

    def test_output_dir_flag(self):
        args = _parse(["--output-dir", "/tmp"])
        assert args.output_dir == "/tmp"

    def test_workers_flag(self):
        args = _parse(["--workers", "5"])
        assert args.workers == 5

    def test_verbose_short_flag(self):
        args = _parse(["-v"])
        assert args.verbose is True

    def test_config_flag(self):
        args = _parse(["--config", "myconfig.yaml"])
        assert args.config == "myconfig.yaml"

    def test_workers_zero_raises_system_exit(self):
        with pytest.raises(SystemExit):
            _parse(["--workers", "0"])

    def test_workers_negative_raises_system_exit(self):
        with pytest.raises(SystemExit):
            _parse(["--workers", "-1"])

    def test_no_args_defaults(self):
        args = _parse([])
        assert args.excel is False
        assert args.csv is False
        assert args.json is False
        assert args.email is False
        assert args.devices is None
        assert args.output_dir is None
        assert args.workers is None
        assert args.verbose is False
        assert args.config is None


# ---------------------------------------------------------------------------
# 2. _apply_overrides()
# ---------------------------------------------------------------------------

class TestApplyOverrides:
    def _config(self) -> AppConfig:
        cfg = AppConfig()
        cfg.devices = ["192.168.1.1"]
        return cfg

    def test_devices_override(self):
        cfg = self._config()
        args = _parse(["--devices", "10.0.0.1", "10.0.0.2"])
        _apply_overrides(cfg, args)
        assert cfg.devices == ["10.0.0.1", "10.0.0.2"]

    def test_output_dir_override(self):
        cfg = self._config()
        args = _parse(["--output-dir", "/some/dir"])
        _apply_overrides(cfg, args)
        assert cfg.output.directory == "/some/dir"

    def test_workers_override(self):
        cfg = self._config()
        args = _parse(["--workers", "7"])
        _apply_overrides(cfg, args)
        assert cfg.collection.max_workers == 7

    def test_email_flag_does_not_mutate_config(self):
        cfg = self._config()
        assert cfg.email.enabled is False
        args = _parse(["--email"])
        _apply_overrides(cfg, args)
        # --email no longer mutates config.email.enabled; send_email is
        # computed in main() via: send_email = config.email.enabled or args.email
        assert cfg.email.enabled is False

    def test_no_flags_leaves_config_unchanged(self):
        cfg = self._config()
        original_devices = cfg.devices[:]
        original_dir = cfg.output.directory
        original_workers = cfg.collection.max_workers
        original_email = cfg.email.enabled
        args = _parse([])
        _apply_overrides(cfg, args)
        assert cfg.devices == original_devices
        assert cfg.output.directory == original_dir
        assert cfg.collection.max_workers == original_workers
        assert cfg.email.enabled == original_email


# ---------------------------------------------------------------------------
# 3. Default output format
# ---------------------------------------------------------------------------

class TestDefaultOutputFormat:
    def test_no_format_flags_excel_defaults_true(self):
        """When no format flag is given, main() sets args.excel = True."""
        args = _parse([])
        # Simulate what main() does
        if not (args.excel or args.csv or args.json):
            args.excel = True
        assert args.excel is True

    def test_csv_only_excel_stays_false(self):
        args = _parse(["--csv"])
        # main() should not override because args.csv is truthy
        if not (args.excel or args.csv or args.json):
            args.excel = True
        assert args.excel is False
        assert args.csv is True


# ---------------------------------------------------------------------------
# 4. _setup_logging()
# ---------------------------------------------------------------------------

class TestSetupLogging:
    def _get_logger(self) -> logging.Logger:
        return logging.getLogger("vpn_collector")

    def test_exactly_two_handlers(self, tmp_path):
        _setup_logging(str(tmp_path), verbose=False)
        logger = self._get_logger()
        assert len(logger.handlers) == 2

    def test_calling_twice_does_not_duplicate_handlers(self, tmp_path):
        _setup_logging(str(tmp_path), verbose=False)
        _setup_logging(str(tmp_path), verbose=False)
        logger = self._get_logger()
        assert len(logger.handlers) == 2

    def test_propagate_is_false(self, tmp_path):
        _setup_logging(str(tmp_path), verbose=False)
        logger = self._get_logger()
        assert logger.propagate is False

    def test_verbose_true_console_level_is_debug(self, tmp_path):
        _setup_logging(str(tmp_path), verbose=True)
        logger = self._get_logger()
        # Console handler is the StreamHandler (last added)
        console_handlers = [
            h for h in logger.handlers if isinstance(h, logging.StreamHandler)
            and not hasattr(h, "baseFilename")
        ]
        assert len(console_handlers) == 1
        assert console_handlers[0].level == logging.DEBUG

    def test_verbose_false_console_level_is_info(self, tmp_path):
        _setup_logging(str(tmp_path), verbose=False)
        logger = self._get_logger()
        console_handlers = [
            h for h in logger.handlers if isinstance(h, logging.StreamHandler)
            and not hasattr(h, "baseFilename")
        ]
        assert len(console_handlers) == 1
        assert console_handlers[0].level == logging.INFO


# ---------------------------------------------------------------------------
# 5. main() error handling
# ---------------------------------------------------------------------------

class TestMainErrorHandling:
    def test_missing_config_file_exits_1(self, tmp_path, monkeypatch, capsys):
        """A missing config file path causes sys.exit(1) without traceback."""
        from vpn_collector import cli

        missing = str(tmp_path / "does_not_exist.yaml")
        monkeypatch.setattr(sys, "argv", ["vpn_collector", "--config", missing])

        with pytest.raises(SystemExit) as exc_info:
            cli.main()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Error loading config" in captured.err

    def test_invalid_yaml_config_exits_1(self, tmp_path, monkeypatch, capsys):
        """Malformed YAML in config file causes sys.exit(1) without traceback."""
        from vpn_collector import cli

        bad_yaml = tmp_path / "bad.yaml"
        bad_yaml.write_text("key: [unclosed", encoding="utf-8")

        monkeypatch.setattr(sys, "argv", ["vpn_collector", "--config", str(bad_yaml)])

        with pytest.raises(SystemExit) as exc_info:
            cli.main()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Error loading config" in captured.err
