# ASA VPN Session Collector

## Overview

A Python package that collects AnyConnect VPN session statistics from one or more Cisco ASA devices over SSH and writes the results to Excel, CSV, or JSON. Runs against large fleets concurrently, retries failed devices automatically, and can email the output when collection is done.

---

## Features

- **Concurrent SSH collection** — polls multiple ASA devices in parallel using a configurable thread-pool (default 20 workers, tested at 50+)
- **Multi-format output** — Excel (`.xlsx` with Summary + Raw sheets), CSV, and JSON; combine any or all in one run
- **TLS email delivery** — optional STARTTLS-secured SMTP with HTML summary body and file attachments
- **CLI interface** — full command-line control over devices, output format, directory, worker count, and verbosity
- **YAML configuration** — single `config.yaml` covers all settings; no source-code editing required
- **Retry with backoff** — per-device exponential back-off on SSH failure
- **Rotating log file** — `vpn_collector.log` written with automatic rotation

---

## Requirements

- Python 3.10 or later
- Install dependencies:

```bash
pip install -r requirements.txt
```

---

## Quick Start

```bash
# 1. Copy the example config
cp config.example.yaml config.yaml

# 2. Add your ASA device IPs/hostnames
vi config.yaml

# 3. Run — defaults to Excel output
python -m vpn_collector
```

You will be prompted for SSH credentials at runtime. No passwords are stored on disk.

---

## CLI Usage

```
usage: vpn_collector [-h] [--devices HOST [HOST ...]] [--excel] [--csv]
                     [--json] [--email] [--output-dir DIR] [--workers N]
                     [--verbose] [--config FILE]
```

| Flag | Description |
|------|-------------|
| `--devices HOST [HOST ...]` | Override device list from `config.yaml` |
| `--excel` | Write Excel output (Summary + Raw sheets) |
| `--csv` | Write CSV output |
| `--json` | Write JSON output |
| `--email` | Send email after collection (overrides `config.yaml` `email.enabled`) |
| `--output-dir DIR` | Override output directory |
| `--workers N` | Override `collection.max_workers` |
| `--verbose`, `-v` | Enable debug-level console logging |
| `--config FILE` | Path to config file (default: `config.yaml` in CWD) |

If no output-format flag is given, `--excel` is used by default.

### Examples

**Collect from all configured devices, write Excel (default):**
```bash
python -m vpn_collector
```

**Collect from all configured devices, write all three formats:**
```bash
python -m vpn_collector --excel --csv --json
```

**Target two specific firewalls, write JSON only:**
```bash
python -m vpn_collector --devices 10.0.0.1 10.0.0.2 --json
```

**Write output to a specific directory:**
```bash
python -m vpn_collector --excel --output-dir /var/reports/vpn
```

**Run with higher concurrency against a large fleet:**
```bash
python -m vpn_collector --workers 40
```

**Collect, write CSV, and email the result:**
```bash
python -m vpn_collector --csv --email
```

**Debug a failing device — verbose console output:**
```bash
python -m vpn_collector --devices 10.0.0.5 --verbose
```

**Use a non-default config file:**
```bash
python -m vpn_collector --config /etc/vpn-collector/prod.yaml
```

---

## Configuration Reference

Copy `config.example.yaml` to `config.yaml` and edit. The full annotated example is in `config.example.yaml`.

### `devices`

```yaml
devices:
  - 10.0.0.1
  - 10.0.0.2
  - asa-dmz.corp.example.com
```

### `collection`

| Key | Default | Description |
|-----|---------|-------------|
| `max_workers` | `20` | Maximum concurrent SSH connections (recommended ceiling: 50) |
| `retries` | `3` | Retry attempts per device on failure |
| `retry_backoff_base` | `2.0` | Exponential back-off base in seconds |
| `timeout` | `30` | SSH connection timeout in seconds |

### `output`

| Key | Default | Description |
|-----|---------|-------------|
| `directory` | `"."` | Directory for all output files |
| `excel_filename` | `"AnyConnect-Sessions.xlsx"` | Excel workbook filename |

### `email`

| Key | Default | Description |
|-----|---------|-------------|
| `enabled` | `false` | Send email after each run |
| `smtp_server` | — | SMTP server hostname or IP |
| `smtp_port` | `587` | SMTP port |
| `tls` | `true` | Use STARTTLS |
| `smtp_username` | `""` | Auth username (leave blank to skip auth) |
| `smtp_password` | `""` | Auth password — **never commit real values** |
| `from_address` | — | Sender address |
| `recipients` | — | List of recipient addresses |

---

## Output Files

### Excel (default)

A single `.xlsx` workbook with two sheets per run:

**Summary sheet** — one row per device:

| Run Timestamp | Total Devices | Successful | Total Sessions |
|---------------|--------------|------------|----------------|
| 2026-03-17T06:00:00+00:00 | 12 | 11 | 347 |

| Host | Sessions | Status |
|------|----------|--------|
| 10.0.0.1 | 42 | OK |
| 10.0.0.2 | 31 | OK |
| 10.0.0.3 | 0 | FAILED: Authentication failed |

**Raw sheet** (`Raw_20260317_060000`) — one row per AnyConnect session:

| username | assigned_ip | public_ip | protocol | bytes_tx | bytes_rx | duration | group_policy | tunnel_group |
|----------|-------------|-----------|----------|----------|----------|----------|--------------|--------------|
| jsmith | 10.10.1.100 | 203.0.113.50 | AnyConnect-Parent SSL-Tunnel DTLS-Tunnel | 12345678 | 87654321 | 2h:15m:30s | GroupPolicy_RA | RA-VPN |
| bjones | 10.10.1.101 | 198.51.100.22 | AnyConnect-Parent SSL-Tunnel DTLS-Tunnel | 5000000 | 3000000 | 1h:30m:00s | GroupPolicy_RA | RA-VPN |

Subsequent runs append a new `Raw_YYYYMMDD_HHMMSS` sheet — the workbook accumulates history across runs.

---

### CSV

Flat file, one row per session. Filename: `anyconnect-sessions-YYYYMMDD_HHMMSS.csv`

```
username,assigned_ip,public_ip,protocol,bytes_tx,bytes_rx,duration,group_policy,tunnel_group,login_time,...
jsmith,10.10.1.100,203.0.113.50,AnyConnect-Parent SSL-Tunnel DTLS-Tunnel,12345678,87654321,2h:15m:30s,GroupPolicy_RA,RA-VPN,09:30:15 UTC Mon Mar 17 2026,...
bjones,10.10.1.101,198.51.100.22,AnyConnect-Parent SSL-Tunnel DTLS-Tunnel,5000000,3000000,1h:30m:00s,GroupPolicy_RA,RA-VPN,10:15:00 UTC Mon Mar 17 2026,...
```

---

### JSON

Array of device result objects. Filename: `anyconnect-sessions-YYYYMMDD_HHMMSS.json`

```json
[
  {
    "host": "10.0.0.1",
    "success": true,
    "collected_at": "2026-03-17T06:00:01.234567+00:00",
    "session_count": 2,
    "sessions": [
      {
        "username": "jsmith",
        "assigned_ip": "10.10.1.100",
        "public_ip": "203.0.113.50",
        "protocol": "AnyConnect-Parent SSL-Tunnel DTLS-Tunnel",
        "bytes_tx": "12345678",
        "bytes_rx": "87654321",
        "duration": "2h:15m:30s",
        "group_policy": "GroupPolicy_RA",
        "tunnel_group": "RA-VPN"
      },
      {
        "username": "bjones",
        "assigned_ip": "10.10.1.101",
        "public_ip": "198.51.100.22",
        "protocol": "AnyConnect-Parent SSL-Tunnel DTLS-Tunnel",
        "bytes_tx": "5000000",
        "bytes_rx": "3000000",
        "duration": "1h:30m:00s",
        "group_policy": "GroupPolicy_RA",
        "tunnel_group": "RA-VPN"
      }
    ]
  },
  {
    "host": "10.0.0.3",
    "success": false,
    "collected_at": "2026-03-17T06:00:04.891234+00:00",
    "session_count": 0,
    "sessions": [],
    "error": "Authentication failed."
  }
]
```

---

### Log output

Console output during a run (normal verbosity):

```
2026-03-17 06:00:00,000 [INFO] vpn_collector: No output format specified, defaulting to Excel.
Username: admin
Password:
2026-03-17 06:00:04,123 [INFO] vpn_collector: Run complete — total_devices=12, successful=11, total_sessions=347
```

With `--verbose`:

```
2026-03-17 06:00:00,001 [DEBUG] vpn_collector: Connecting to 10.0.0.1 (attempt 1/4)
2026-03-17 06:00:00,002 [DEBUG] vpn_collector: Connecting to 10.0.0.2 (attempt 1/4)
...
2026-03-17 06:00:02,441 [WARNING] vpn_collector: [10.0.0.3] All retries exhausted: Authentication failed.
2026-03-17 06:00:04,123 [INFO] vpn_collector: Run complete — total_devices=12, successful=11, total_sessions=347
```

---

## Migration from v1

| v1 | v2 |
|----|----|
| `asa_devices.txt` | `devices:` list in `config.yaml` |
| `ciphertext.bin` (encrypted credentials) | Removed — **delete it** |
| `fetch_creds.py` | Removed |
| `command.py` | `vpn_collector/collector.py` |
| `data_handler.py` | `vpn_collector/reporter.py` |
| `send_mail.py` | `vpn_collector/mailer.py` |
| `main.py` | `python -m vpn_collector` |

Migration steps:

```bash
# Remove old credential file
rm -f ciphertext.bin

# Set up config
cp config.example.yaml config.yaml
# edit config.yaml — add devices, configure email if needed

# Update dependencies
pip install -r requirements.txt

# Run
python -m vpn_collector
```

---

## Disclaimer

This tool is intended for **authorized use only**. Ensure you have explicit permission from the device owners and your organization before running automated SSH commands against any Cisco ASA device. Unauthorized access to network infrastructure may violate applicable laws and organizational policies.
