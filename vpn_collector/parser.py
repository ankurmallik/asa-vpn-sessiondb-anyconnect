"""TextFSM-based parser for Cisco ASA VPN session output."""

import logging

from ntc_templates.parse import parse_output

logger = logging.getLogger(__name__)

_NO_SESSIONS_SENTINEL = "There are no active"


def parse_sessions(raw_output: str, host: str) -> list[dict]:
    """Parse the output of ``show vpn-sessiondb anyconnect`` into a list of dicts.

    Uses the NTC Templates library (ntc-templates) which ships with a TextFSM
    template for ``cisco_asa / show vpn-sessiondb anyconnect``.

    Parameters
    ----------
    raw_output:
        Raw CLI output returned by the device.
    host:
        Hostname or IP of the source device (used only for log messages).

    Returns
    -------
    list[dict]
        One dictionary per VPN session, keyed by the TextFSM header names.
        Returns an empty list when there are no sessions or parsing fails.
    """
    # --- Fast-path: empty or explicitly zero-session output -----------------
    if not raw_output or _NO_SESSIONS_SENTINEL in raw_output:
        return []

    # --- TextFSM parse via ntc-templates ------------------------------------
    try:
        sessions: list[dict] = parse_output(
            platform="cisco_asa",
            command="show vpn-sessiondb anyconnect",
            data=raw_output,
        )
        return sessions
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] TextFSM parse failed: %s", host, exc)
        return []
