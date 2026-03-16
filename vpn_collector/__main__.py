"""Entry point for `python -m vpn_collector`."""

import sys

try:
    from vpn_collector.cli import main
except ImportError as exc:
    sys.exit(f"vpn_collector is not fully installed — {exc}")

if __name__ == "__main__":
    main()
