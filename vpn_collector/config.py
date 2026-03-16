"""Configuration loading and validation for the ASA VPN session collector."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise ImportError("PyYAML is required: pip install PyYAML") from exc

_DEFAULT_CONFIG_FILENAME = "config.yaml"


# ---------------------------------------------------------------------------
# Nested config dataclasses
# ---------------------------------------------------------------------------

@dataclass
class CollectionConfig:
    """Settings that control how devices are polled."""

    max_workers: int = 20
    retries: int = 3
    retry_backoff_base: float = 2.0
    timeout: int = 30


@dataclass
class OutputConfig:
    """Settings for where output files are written."""

    directory: str = "."
    excel_filename: str = "AnyConnect-Sessions.xlsx"


@dataclass
class EmailConfig:
    """Settings for email notifications."""

    enabled: bool = False
    smtp_server: str = "smtp.example.com"
    smtp_port: int = 587
    tls: bool = True
    smtp_username: str = ""
    smtp_password: str = ""
    from_address: str = "noreply@example.com"
    recipients: List[str] = field(default_factory=list)


@dataclass
class AppConfig:
    """Top-level application configuration."""

    devices: List[str] = field(default_factory=list)
    collection: CollectionConfig = field(default_factory=CollectionConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    email: EmailConfig = field(default_factory=EmailConfig)


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def load_config(path: str | os.PathLike | None = None) -> AppConfig:
    """Load, parse, and validate configuration from a YAML file.

    Parameters
    ----------
    path:
        Path to the config file.  When *None* (the default) the file
        ``config.yaml`` in the current working directory is used.

    Returns
    -------
    AppConfig
        A fully validated :class:`AppConfig` instance.

    Raises
    ------
    FileNotFoundError
        When the config file does not exist.
    ValueError
        When one or more validation errors are found.  All errors are
        collected first and reported together in a single exception.
    """
    if path is None:
        config_path = Path.cwd() / _DEFAULT_CONFIG_FILENAME
    else:
        config_path = Path(path)

    if not config_path.exists():
        raise FileNotFoundError(
            f"Config file not found: {config_path}\n"
            f"Copy config.example.yaml to {config_path.name} and fill in your values."
        )

    with config_path.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}

    cfg = _build_config(raw)
    _validate_config(cfg)
    return cfg


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_config(raw: dict) -> AppConfig:
    """Construct an :class:`AppConfig` from a raw YAML dictionary."""
    collection_raw = raw.get("collection") or {}
    output_raw = raw.get("output") or {}
    email_raw = raw.get("email") or {}

    collection = CollectionConfig(
        max_workers=collection_raw.get("max_workers", CollectionConfig.max_workers),
        retries=collection_raw.get("retries", CollectionConfig.retries),
        retry_backoff_base=collection_raw.get(
            "retry_backoff_base", CollectionConfig.retry_backoff_base
        ),
        timeout=collection_raw.get("timeout", CollectionConfig.timeout),
    )

    output = OutputConfig(
        directory=output_raw.get("directory", OutputConfig.directory),
        excel_filename=output_raw.get("excel_filename", OutputConfig.excel_filename),
    )

    email = EmailConfig(
        enabled=email_raw.get("enabled", EmailConfig.enabled),
        smtp_server=email_raw.get("smtp_server", EmailConfig.smtp_server),
        smtp_port=email_raw.get("smtp_port", EmailConfig.smtp_port),
        tls=email_raw.get("tls", EmailConfig.tls),
        smtp_username=email_raw.get("smtp_username", EmailConfig.smtp_username),
        smtp_password=email_raw.get("smtp_password", EmailConfig.smtp_password),
        from_address=email_raw.get("from_address", EmailConfig.from_address),
        recipients=list(email_raw.get("recipients") or []),
    )

    return AppConfig(
        devices=list(raw.get("devices") or []),
        collection=collection,
        output=output,
        email=email,
    )


def _validate_config(cfg: AppConfig) -> None:
    """Validate *cfg*, collecting ALL errors before raising.

    Raises
    ------
    ValueError
        A single exception whose message lists every validation problem found.
    """
    errors: list[str] = []

    # devices
    if not cfg.devices:
        errors.append("'devices' must be a non-empty list of hostnames/IPs.")

    # collection
    if cfg.collection.max_workers < 1:
        errors.append(
            f"'collection.max_workers' must be >= 1 (got {cfg.collection.max_workers})."
        )
    if cfg.collection.retries < 0:
        errors.append(
            f"'collection.retries' must be >= 0 (got {cfg.collection.retries})."
        )
    if cfg.collection.retry_backoff_base <= 0:
        errors.append(
            f"'collection.retry_backoff_base' must be > 0 "
            f"(got {cfg.collection.retry_backoff_base})."
        )
    if cfg.collection.timeout <= 0:
        errors.append(
            f"'collection.timeout' must be > 0 (got {cfg.collection.timeout})."
        )

    # email (only when enabled)
    if cfg.email.enabled:
        if not cfg.email.smtp_server:
            errors.append(
                "'email.smtp_server' must be non-empty when email is enabled."
            )
        if not cfg.email.from_address:
            errors.append(
                "'email.from_address' must be non-empty when email is enabled."
            )
        if not cfg.email.recipients:
            errors.append(
                "'email.recipients' must be a non-empty list when email is enabled."
            )

    if errors:
        bullet_list = "\n  - ".join(errors)
        raise ValueError(f"Configuration errors found:\n  - {bullet_list}")
