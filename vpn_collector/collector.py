"""Device collection logic for the ASA VPN session collector."""

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone

import netmiko
import netmiko.exceptions

from vpn_collector.config import AppConfig
from vpn_collector.parser import parse_sessions

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class DeviceResult:
    """Holds the outcome of a single device collection attempt."""

    host: str
    success: bool
    sessions: list[dict]
    error: str | None
    collected_at: datetime


# ---------------------------------------------------------------------------
# Single-device collection
# ---------------------------------------------------------------------------

def collect_device(
    device_info: dict,
    retries: int,
    backoff_base: float,
) -> DeviceResult:
    """Connect to one device, run the VPN session command, and return a result.

    Parameters
    ----------
    device_info:
        Keyword arguments passed directly to ``netmiko.ConnectHandler``.
        Must contain at least ``host``, ``device_type``, ``username``,
        ``password``.
    retries:
        Number of retry attempts after the initial failure (so total
        attempts = retries + 1).
    backoff_base:
        Base for the exponential back-off.  Wait ``backoff_base ** attempt``
        seconds *before* each retry (attempt 0 = first retry).

    Returns
    -------
    DeviceResult
        Always returns a ``DeviceResult``; never raises.
    """
    host: str = device_info.get("host", "<unknown>")
    last_exc: Exception | None = None

    for attempt in range(retries + 1):
        if attempt > 0:
            wait = backoff_base ** (attempt - 1)
            logger.debug("[%s] Retry %d/%d — waiting %.1fs", host, attempt, retries, wait)
            time.sleep(wait)

        connection = None
        try:
            logger.debug("[%s] Connecting (attempt %d)", host, attempt)
            connection = netmiko.ConnectHandler(**device_info)
            output = connection.send_command("show vpn-sessiondb anyconnect")
            sessions = parse_sessions(output, host)
            logger.info("[%s] Collected %d session(s)", host, len(sessions))
            return DeviceResult(
                host=host,
                success=True,
                sessions=sessions,
                error=None,
                collected_at=datetime.now(timezone.utc),
            )
        except (
            netmiko.exceptions.NetmikoBaseException,
            OSError,
            TimeoutError,
        ) as exc:
            last_exc = exc
            logger.warning("[%s] Connection error (attempt %d): %s", host, attempt, exc)
        except Exception as exc:  # noqa: BLE001 — must not let anything escape
            last_exc = exc
            logger.error("[%s] Unexpected error (attempt %d): %s", host, attempt, exc)
            # Unexpected errors are not retried
            break
        finally:
            if connection is not None:
                try:
                    connection.disconnect()
                except Exception:  # noqa: BLE001
                    pass

    return DeviceResult(
        host=host,
        success=False,
        sessions=[],
        error=str(last_exc),
        collected_at=datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# Parallel collection across all devices
# ---------------------------------------------------------------------------

def collect_all(
    config: AppConfig,
    username: str,
    password: str,
) -> list[DeviceResult]:
    """Collect VPN sessions from all configured devices in parallel.

    Parameters
    ----------
    config:
        Loaded application configuration.
    username:
        SSH username to authenticate with.
    password:
        SSH password to authenticate with.

    Returns
    -------
    list[DeviceResult]
        One ``DeviceResult`` per device, in completion order.  Never raises.
    """
    results: list[DeviceResult] = []

    try:
        futures = {}
        with ThreadPoolExecutor(max_workers=config.collection.max_workers) as executor:
            for device in config.devices:
                device_info = {
                    "device_type": "cisco_asa",
                    "host": device,
                    "username": username,
                    "password": password,
                    "timeout": config.collection.timeout,
                }
                future = executor.submit(
                    collect_device,
                    device_info,
                    config.collection.retries,
                    config.collection.retry_backoff_base,
                )
                futures[future] = device

            for future in as_completed(futures):
                device = futures[future]
                try:
                    result = future.result()
                except Exception as exc:  # noqa: BLE001 — final safety net
                    logger.error("[%s] Unhandled future error: %s", device, exc)
                    result = DeviceResult(
                        host=device,
                        success=False,
                        sessions=[],
                        error=str(exc),
                        collected_at=datetime.now(timezone.utc),
                    )
                results.append(result)

    except Exception as exc:  # noqa: BLE001 — executor/setup failures
        logger.error("collect_all: unexpected error: %s", exc)

    return results
