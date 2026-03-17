"""Email reporting for the ASA VPN session collector."""

from __future__ import annotations

import html
import logging
import smtplib
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from vpn_collector.config import AppConfig

_logger = logging.getLogger("vpn_collector.mailer")
_EMAIL_SUBJECT = "AnyConnect VPN Session Report"


# ---------------------------------------------------------------------------
# Body builders
# ---------------------------------------------------------------------------

def _build_html_body(results_summary: dict) -> str:
    """Return a well-formatted HTML email body from *results_summary*."""
    timestamp = html.escape(str(results_summary.get("timestamp", "N/A")))
    total_devices = html.escape(str(results_summary.get("total_devices", 0)))
    successful_devices = html.escape(str(results_summary.get("successful_devices", 0)))
    total_sessions = html.escape(str(results_summary.get("total_sessions", 0)))
    devices = results_summary.get("devices", [])

    rows_html = ""
    for device in devices:
        host = html.escape(str(device.get("host", "")))
        sessions = html.escape(str(device.get("sessions", 0)))
        status = html.escape(str(device.get("status", "")))
        rows_html += (
            f"    <tr>\n"
            f"      <td style='padding:4px 8px;border:1px solid #ccc;'>{host}</td>\n"
            f"      <td style='padding:4px 8px;border:1px solid #ccc;text-align:right;'>{sessions}</td>\n"
            f"      <td style='padding:4px 8px;border:1px solid #ccc;'>{status}</td>\n"
            f"    </tr>\n"
        )

    return f"""\
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: Arial, sans-serif; font-size: 14px; color: #333; }}
    table {{ border-collapse: collapse; width: 100%; max-width: 640px; }}
    th {{ background-color: #0057a8; color: #fff; padding: 6px 8px; border: 1px solid #ccc; text-align: left; }}
    td {{ vertical-align: top; }}
    .summary {{ margin-bottom: 16px; }}
    .summary dt {{ font-weight: bold; }}
    .summary dd {{ margin: 0 0 4px 0; }}
  </style>
</head>
<body>
  <h2>AnyConnect VPN Session Report</h2>
  <dl class="summary">
    <dt>Run Timestamp</dt><dd>{timestamp}</dd>
    <dt>Total Devices Queried</dt><dd>{total_devices}</dd>
    <dt>Successful Devices</dt><dd>{successful_devices}</dd>
    <dt>Total Sessions Collected</dt><dd>{total_sessions}</dd>
  </dl>
  <table>
    <thead>
      <tr>
        <th>Host</th>
        <th>Sessions</th>
        <th>Status</th>
      </tr>
    </thead>
    <tbody>
{rows_html}\
    </tbody>
  </table>
</body>
</html>
"""


def _build_text_body(results_summary: dict) -> str:
    """Return a plain-text email body from *results_summary*."""
    timestamp = results_summary.get("timestamp", "N/A")
    total_devices = results_summary.get("total_devices", 0)
    successful_devices = results_summary.get("successful_devices", 0)
    total_sessions = results_summary.get("total_sessions", 0)
    devices = results_summary.get("devices", [])

    lines = [
        "AnyConnect VPN Session Report",
        "=" * 40,
        f"Run Timestamp:           {timestamp}",
        f"Total Devices Queried:   {total_devices}",
        f"Successful Devices:      {successful_devices}",
        f"Total Sessions Collected: {total_sessions}",
        "",
        f"{'Host':<30} {'Sessions':>9}  Status",
        "-" * 55,
    ]
    for device in devices:
        host = device.get("host", "")
        sessions = device.get("sessions", 0)
        status = device.get("status", "")
        lines.append(f"{host:<30} {sessions:>9}  {status}")

    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def send_report(
    files: list[Path],
    results_summary: dict,
    config: AppConfig,
) -> None:
    """Send a VPN session report email with *files* attached.

    Parameters
    ----------
    files:
        Output files to attach (Excel, CSV, JSON, …).  If the list is empty
        the function logs a WARNING and returns without connecting to SMTP.
    results_summary:
        Summary dict with keys ``timestamp``, ``total_devices``,
        ``successful_devices``, ``total_sessions``, and ``devices``.
    config:
        Application configuration containing ``email.*`` settings.
    """
    # 8.5 — guard against empty file list
    if not files:
        _logger.warning("No output files to attach — skipping email.")
        return

    # --- Build message ---
    outer = MIMEMultipart("mixed")
    outer["From"] = config.email.from_address
    outer["To"] = ", ".join(config.email.recipients)
    outer["Subject"] = _EMAIL_SUBJECT

    # Alternative inner part (text + HTML)
    inner = MIMEMultipart("alternative")
    text_body = _build_text_body(results_summary)
    html_body = _build_html_body(results_summary)
    inner.attach(MIMEText(text_body, "plain", "utf-8"))
    inner.attach(MIMEText(html_body, "html", "utf-8"))
    outer.attach(inner)

    # Attach files as binary attachments
    for file_path in files:
        with file_path.open("rb") as fh:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(fh.read())
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition",
            "attachment",
            filename=file_path.name,
        )
        outer.attach(part)

    # --- SMTP delivery ---
    smtp_server = config.email.smtp_server
    smtp_port = config.email.smtp_port
    username = config.email.smtp_username
    password = config.email.smtp_password
    use_tls = config.email.tls
    recipients = config.email.recipients

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            if use_tls:
                server.starttls()
            else:
                _logger.warning(
                    "Sending email without TLS — credentials and content are "
                    "transmitted in plaintext"
                )
            if username:
                server.login(username, password)
            server.sendmail(config.email.from_address, recipients, outer.as_string())
        _logger.info("Email sent to %d recipients", len(recipients))
    except smtplib.SMTPException as exc:
        _logger.error("SMTP error while sending email: %s", exc)
    except OSError as exc:
        _logger.error("Network error while sending email: %s", exc)
