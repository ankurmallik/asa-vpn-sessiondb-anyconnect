"""Command-line interface for the ASA VPN session collector."""

import argparse
import getpass
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from vpn_collector.config import AppConfig, load_config

_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_LOG_FILENAME = "vpn_collector.log"
_LOG_MAX_BYTES = 5 * 1024 * 1024  # 5 MB
_LOG_BACKUP_COUNT = 3


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

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
        type=int,
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
    if args.email:
        config.email.enabled = True


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
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

    # Apply CLI overrides onto config
    _apply_overrides(config, args)

    # Re-configure file logging now that we have the final output directory
    # (only if --output-dir was not supplied on the CLI — otherwise early_output_dir
    # is already correct; if it came from config we need to re-init)
    if args.output_dir is None and config.output.directory != ".":
        _setup_logging(config.output.directory, args.verbose)
        logger = logging.getLogger("vpn_collector")

    # Default output format: if none specified, default to Excel
    if not (args.excel or args.csv or args.json):
        args.excel = True
        logger.info("No output format specified, defaulting to Excel.")

    # Prompt for credentials
    username = input("Username: ")
    password = getpass.getpass("Password: ")

    # TODO: collect, report, mail
    logger.debug(
        "CLI ready — devices=%s, output_dir=%s, workers=%d, "
        "excel=%s, csv=%s, json=%s, email=%s",
        config.devices,
        config.output.directory,
        config.collection.max_workers,
        args.excel,
        args.csv,
        args.json,
        config.email.enabled,
    )
    _ = username, password  # suppress unused-variable warnings until used downstream
