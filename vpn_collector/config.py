"""Configuration loading and validation for the ASA VPN session collector."""

import os
from dataclasses import dataclass, field
from pathlib import Path

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
    recipients: list[str] = field(default_factory=list)


@dataclass
class AppConfig:
    """Top-level application configuration."""

    devices: list[str] = field(default_factory=list)
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

    errors: list[str] = []
    cfg = _build_config(raw, errors)
    _validate_config(cfg, errors)
    if errors:
        bullet_list = "\n  - ".join(errors)
        raise ValueError(f"Configuration errors found:\n  - {bullet_list}")
    return cfg


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_config(raw: dict, errors: list[str]) -> AppConfig:
    """Construct an :class:`AppConfig` from a raw YAML dictionary."""
    collection_raw = raw.get("collection") or {}
    output_raw = raw.get("output") or {}
    email_raw = raw.get("email") or {}

    collection = CollectionConfig(
        max_workers=collection_raw.get("max_workers", 20),
        retries=collection_raw.get("retries", 3),
        retry_backoff_base=collection_raw.get("retry_backoff_base", 2.0),
        timeout=collection_raw.get("timeout", 30),
    )

    output = OutputConfig(
        directory=output_raw.get("directory", "."),
        excel_filename=output_raw.get("excel_filename", "AnyConnect-Sessions.xlsx"),
    )

    # recipients: must be a list, not a scalar
    raw_recipients = email_raw.get("recipients") or []
    if not isinstance(raw_recipients, list):
        errors.append(
            f"'email.recipients' must be a list (got {type(raw_recipients).__name__})."
        )
        raw_recipients = []

    email = EmailConfig(
        enabled=email_raw.get("enabled", False),
        smtp_server=email_raw.get("smtp_server", "smtp.example.com"),
        smtp_port=email_raw.get("smtp_port", 587),
        tls=email_raw.get("tls", True),
        smtp_username=email_raw.get("smtp_username", ""),
        smtp_password=email_raw.get("smtp_password", ""),
        from_address=email_raw.get("from_address", "noreply@example.com"),
        recipients=list(raw_recipients),
    )

    # devices: must be a list, not a scalar
    raw_devices = raw.get("devices") or []
    if not isinstance(raw_devices, list):
        errors.append(
            f"'devices' must be a list (got {type(raw_devices).__name__})."
        )
        raw_devices = []

    return AppConfig(
        devices=list(raw_devices),
        collection=collection,
        output=output,
        email=email,
    )


def _validate_config(cfg: AppConfig, errors: list[str]) -> None:
    """Validate *cfg*, appending all problems into *errors*.

    The caller is responsible for raising if *errors* is non-empty after
    this function returns.
    """
    # devices
    if not cfg.devices:
        errors.append("'devices' must be a non-empty list of hostnames/IPs.")

    # collection — type guards before numeric comparisons
    if not isinstance(cfg.collection.max_workers, int):
        errors.append(
            f"'collection.max_workers' must be an integer "
            f"(got {type(cfg.collection.max_workers).__name__})."
        )
    elif cfg.collection.max_workers < 1:
        errors.append(
            f"'collection.max_workers' must be >= 1 (got {cfg.collection.max_workers})."
        )

    if not isinstance(cfg.collection.retries, int):
        errors.append(
            f"'collection.retries' must be an integer "
            f"(got {type(cfg.collection.retries).__name__})."
        )
    elif cfg.collection.retries < 0:
        errors.append(
            f"'collection.retries' must be >= 0 (got {cfg.collection.retries})."
        )

    if not isinstance(cfg.collection.retry_backoff_base, (int, float)):
        errors.append(
            f"'collection.retry_backoff_base' must be an int or float "
            f"(got {type(cfg.collection.retry_backoff_base).__name__})."
        )
    elif cfg.collection.retry_backoff_base <= 0:
        errors.append(
            f"'collection.retry_backoff_base' must be > 0 "
            f"(got {cfg.collection.retry_backoff_base})."
        )

    if not isinstance(cfg.collection.timeout, (int, float)):
        errors.append(
            f"'collection.timeout' must be an int or float "
            f"(got {type(cfg.collection.timeout).__name__})."
        )
    elif cfg.collection.timeout <= 0:
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
        if not isinstance(cfg.email.smtp_port, int):
            errors.append(
                f"'email.smtp_port' must be an integer "
                f"(got {type(cfg.email.smtp_port).__name__})."
            )
        elif not (1 <= cfg.email.smtp_port <= 65535):
            errors.append(
                f"'email.smtp_port' must be between 1 and 65535 "
                f"(got {cfg.email.smtp_port})."
            )
