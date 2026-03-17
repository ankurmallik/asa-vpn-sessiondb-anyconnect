"""Command-line interface for the ASA VPN session collector."""

import argparse
import getpass
import logging
import sys
import yaml
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

from vpn_collector.collector import collect_all
from vpn_collector.config import AppConfig, load_config
from vpn_collector.mailer import send_report
from vpn_collector.reporter import write_csv, write_excel, write_json

_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_LOG_FILENAME = "vpn_collector.log"
_LOG_MAX_BYTES = 5 * 1024 * 1024  # 5 MB
_LOG_BACKUP_COUNT = 3


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def _positive_int(value: str) -> int:
    n = int(value)
    if n < 1:
        raise argparse.ArgumentTypeError(f"--workers must be >= 1, got {n}")
    return n


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vpn_collector",
        description="Collect AnyConnect VPN session statistics from Cisco ASA devices.",
    )

    parser.add_argument(
        "--devices",
        metavar="HOST",
        nargs="+",
        help="override device list from config",
    )

    # Output format flags
    output_fmt = parser.add_argument_group("output format")
    output_fmt.add_argument(
        "--excel",
        action="store_true",
        default=False,
        help="write Excel output",
    )
    output_fmt.add_argument(
        "--csv",
        action="store_true",
        default=False,
        help="write CSV output",
    )
    output_fmt.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="write JSON output",
    )

    parser.add_argument(
        "--email",
        action="store_true",
        default=False,
        help="send email (overrides config email.enabled)",
    )
    parser.add_argument(
        "--output-dir",
        metavar="DIR",
        dest="output_dir",
        help="override output directory",
    )
    parser.add_argument(
        "--workers",
        metavar="N",
        type=_positive_int,
        help="override max_workers",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        default=False,
        help="enable debug-level console logging",
    )
    parser.add_argument(
        "--config",
        metavar="FILE",
        default=None,
        help="path to config file (default: config.yaml in CWD)",
    )

    return parser


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

def _setup_logging(output_dir: str, verbose: bool) -> None:
    """Configure the root vpn_collector logger with rotating file + console handlers."""
    logger = logging.getLogger("vpn_collector")
    logger.setLevel(logging.DEBUG)  # capture everything; handlers filter independently

    # Avoid duplicate handlers if main() is called more than once (e.g. in tests)
    if logger.handlers:
        logger.handlers.clear()
    logger.propagate = False

    formatter = logging.Formatter(_LOG_FORMAT)

    # --- Rotating file handler (always DEBUG) ---
    log_path = Path(output_dir) / _LOG_FILENAME
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=_LOG_MAX_BYTES,
            backupCount=_LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
    except OSError as exc:
        # Fall back gracefully: warn on stderr, skip file handler
        print(f"Warning: could not open log file {log_path}: {exc}", file=sys.stderr)
        file_handler = None

    if file_handler is not None:
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    # --- Console handler ---
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.DEBUG if verbose else logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)


# ---------------------------------------------------------------------------
# Config overrides
# ---------------------------------------------------------------------------

def _apply_overrides(config: AppConfig, args: argparse.Namespace) -> None:
    """Apply CLI flag overrides onto the loaded AppConfig (mutates in-place)."""
    if args.devices:
        config.devices = args.devices
    if args.output_dir is not None:
        config.output.directory = args.output_dir
    if args.workers is not None:
        config.collection.max_workers = args.workers


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Main entry point for the vpn_collector CLI."""
    parser = _build_parser()
    args = parser.parse_args()

    # Determine output directory early so logging can use it
    # (we may not have loaded config yet, so use args.output_dir or "." as fallback)
    early_output_dir = args.output_dir if args.output_dir is not None else "."

    # Set up logging before anything else
    _setup_logging(early_output_dir, args.verbose)
    logger = logging.getLogger("vpn_collector")

    # Load configuration
    try:
        config = load_config(args.config)
    except (FileNotFoundError, ValueError, yaml.YAMLError) as exc:
        print(f"Error loading config: {exc}", file=sys.stderr)
        sys.exit(1)

    # Apply CLI overrides onto config
    _apply_overrides(config, args)

    # Re-configure file logging now that we have the final output directory
    # (only if --output-dir was not supplied on the CLI — otherwise early_output_dir
    # is already correct; if it came from config we need to re-init)
    if args.output_dir is None and config.output.directory != ".":
        _setup_logging(config.output.directory, args.verbose)

    # Default output format: if none specified, default to Excel
    if not (args.excel or args.csv or args.json):
        args.excel = True
        logger.info("No output format specified, defaulting to Excel.")

    # Determine whether to send email (CLI flag overrides config)
    send_email = config.email.enabled or args.email

    # Validate email settings now that we know whether email will be sent
    if send_email:
        email_errors = []
        if not config.email.smtp_server:
            email_errors.append("'email.smtp_server' is required when email is enabled.")
        if not config.email.from_address:
            email_errors.append("'email.from_address' is required when email is enabled.")
        if not config.email.recipients:
            email_errors.append("'email.recipients' must be non-empty when email is enabled.")
        if email_errors:
            print("Config error:\n" + "\n".join(f"  - {e}" for e in email_errors), file=sys.stderr)
            sys.exit(1)

    # Prompt for credentials
    username = input("Username: ")
    password = getpass.getpass("Password: ")

    # Collect VPN sessions from all devices
    results = collect_all(config, username, password)

    # Determine whether any sessions were collected this run
    has_data = sum(len(r.sessions) for r in results) > 0

    # Snapshot existing output files before writing (to detect new ones for email)
    out_dir = Path(config.output.directory)
    pre_existing = set(out_dir.glob("anyconnect-sessions-*")) if out_dir.exists() else set()

    # Write requested output formats
    if args.excel:
        write_excel(results, config)
    if args.csv:
        write_csv(results, config)
    if args.json:
        write_json(results, config)

    # Gather output files to attach: timestamped files added this run + excel if written
    new_timestamped = set(out_dir.glob("anyconnect-sessions-*")) - pre_existing if out_dir.exists() else set()
    output_files: list[Path] = list(new_timestamped)
    if args.excel and has_data:
        excel_path = out_dir / config.output.excel_filename
        if excel_path.exists() and excel_path not in output_files:
            output_files.append(excel_path)

    # Build summary dict for the mailer
    results_summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_devices": len(results),
        "successful_devices": sum(1 for r in results if r.success),
        "total_sessions": sum(len(r.sessions) for r in results),
        "devices": [
            {
                "host": r.host,
                "sessions": len(r.sessions),
                "status": "OK" if r.success else f"FAILED: {r.error}",
            }
            for r in results
        ],
    }

    # Send email if enabled
    if send_email:
        send_report(output_files, results_summary, config)

    # Final summary log
    logger.info(
        "Run complete — total_devices=%d, successful=%d, total_sessions=%d",
        results_summary["total_devices"],
        results_summary["successful_devices"],
        results_summary["total_sessions"],
    )
