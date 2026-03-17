# ASA VPN Session Collector

## Overview

A Python package that collects AnyConnect VPN session statistics from one or more Cisco ASA devices over SSH and writes the results to Excel, CSV, or JSON. It can also send the output file by email when collection is complete.

---

## Features

- **Concurrent SSH collection** — polls multiple ASA devices in parallel using a configurable thread-pool worker count
- **Multi-format output** — write results as Excel (`.xlsx` with Summary + Raw sheets), CSV, or JSON; multiple formats can be selected in a single run
- **TLS email delivery** — optional STARTTLS-secured SMTP notifications with attachment support
- **CLI interface** — full command-line control over devices, output format, directory, worker count, and verbosity
- **YAML configuration** — single `config.yaml` file covers all settings; no source-code editing required
- **Rotating log file** — `vpn_collector.log` is written with automatic rotation to prevent unbounded growth

---

## Requirements

- Python 3.10 or later
- Install dependencies:

```
pip install -r requirements.txt
```

---

## Quick Start

1. Copy the example configuration file:

   ```
   cp config.example.yaml config.yaml
   ```

2. Edit `config.yaml` — add your device IPs/hostnames and (optionally) configure email:

   ```yaml
   devices:
     - 10.0.0.1
     - asa2.corp.example.com
   ```

3. Run the collector (defaults to Excel output):

   ```
   python -m vpn_collector
   ```

---

## CLI Usage

```
usage: vpn_collector [-h] [--devices HOST [HOST ...]] [--excel] [--csv]
                     [--json] [--email] [--output-dir DIR] [--workers N]
                     [--verbose] [--config FILE]
```

| Flag | Description |
|------|-------------|
| `--devices HOST [HOST ...]` | Override the device list from `config.yaml` |
| `--excel` | Write Excel output (`.xlsx` with Summary and Raw sheets) |
| `--csv` | Write CSV output |
| `--json` | Write JSON output |
| `--email` | Send email notification after collection (overrides `config.yaml` `email.enabled`) |
| `--output-dir DIR` | Override the output directory from `config.yaml` |
| `--workers N` | Override `collection.max_workers` from `config.yaml` |
| `--verbose`, `-v` | Enable debug-level console logging |
| `--config FILE` | Path to config file (default: `config.yaml` in the current working directory) |

Multiple output-format flags may be combined; if none are given, `--excel` is the default.

---

## Configuration Reference

All settings live in `config.yaml`. The full set of options with their defaults is documented in `config.example.yaml`.

### `devices`

A list of ASA device hostnames or IP addresses to poll.

```yaml
devices:
  - 10.0.0.1
  - asa.corp.example.com
```

### `collection`

Controls SSH polling behaviour.

| Key | Default | Description |
|-----|---------|-------------|
| `max_workers` | `20` | Maximum concurrent SSH connections |
| `retries` | `3` | Retry attempts per device on failure |
| `retry_backoff_base` | `2.0` | Exponential back-off base in seconds (`base ^ attempt`) |
| `timeout` | `30` | SSH connection timeout in seconds |

### `output`

Controls where output files are written.

| Key | Default | Description |
|-----|---------|-------------|
| `directory` | `"."` | Directory for output files |
| `excel_filename` | `"AnyConnect-Sessions.xlsx"` | Excel output filename |

### `email`

Controls optional email notifications.

| Key | Default | Description |
|-----|---------|-------------|
| `enabled` | `false` | Enable email sending |
| `smtp_server` | — | SMTP server hostname or IP |
| `smtp_port` | `587` | SMTP port |
| `tls` | `true` | Use STARTTLS |
| `smtp_username` | `""` | SMTP authentication username (leave blank to skip auth) |
| `smtp_password` | `""` | SMTP authentication password (leave blank to skip auth) |
| `from_address` | — | Sender address |
| `recipients` | — | List of recipient addresses |

**Never commit real SMTP credentials to source control.** Use environment-variable substitution or a secrets manager and reference them in `config.yaml`.

---

## Output Files

### Excel (default)

A single `.xlsx` workbook with two sheets:

- **Summary** — one row per device showing total session count and collection status
- **Raw** — one row per AnyConnect session with all parsed fields (username, assigned IP, public IP, protocol, bytes in/out, duration, etc.)

### CSV

A flat `.csv` file containing the same per-session rows as the Raw sheet.

### JSON

A `.json` file containing an array of session objects, one element per session.

---

## Migration from v1

The original single-script layout has been replaced by the `vpn_collector` package:

| v1 | v2 |
|----|----|
| `asa_devices.txt` (device list) | `devices:` list in `config.yaml` |
| `ciphertext.bin` (encrypted credentials) | No longer used — **delete it** |
| `fetch_creds.py` | Removed |
| `command.py` | `vpn_collector/collector.py` |
| `data_handler.py` | `vpn_collector/reporter.py` |
| `send_mail.py` | `vpn_collector/mailer.py` |
| `main.py` | `python -m vpn_collector` |

Steps to migrate:

1. Delete `ciphertext.bin` if it exists.
2. Copy `config.example.yaml` to `config.yaml` and fill in your device list and email settings.
3. Install updated dependencies: `pip install -r requirements.txt`
4. Run `python -m vpn_collector`.

---

## Disclaimer

This tool is intended for **authorized use only**. Ensure you have explicit permission from the device owners and your organization before running automated SSH commands against any Cisco ASA device. Unauthorized access to network infrastructure may violate applicable laws and organizational policies.
