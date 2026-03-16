"""Entry point for `python -m vpn_collector`."""

try:
    from vpn_collector.cli import main
except ImportError as exc:
    import sys
    sys.exit(f"vpn_collector is not fully installed — {exc}")

if __name__ == "__main__":
    main()
