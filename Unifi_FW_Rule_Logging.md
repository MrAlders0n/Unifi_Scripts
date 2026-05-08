# UniFi Firewall Rule Logging

Operator guide for `Unifi_FW_Rule_Logging.py`, a script that bulk-enables syslog logging on UniFi Zone-Based Firewall (ZBF) policies. By default it runs as a dry run and prints what it would change. Nothing is modified until you pass `--apply`.

## What it does

The UniFi Network UI lets you toggle "Log Activity" on each firewall rule individually. With dozens of zone-to-zone policies, this is tedious and error-prone. This script automates that toggle by talking directly to the gateway's REST API, with filters so you can target only the rules you care about (for example, only Block/Reject rules between specific zones).

It handles two kinds of policies:

1. **User-defined rules.** PUT the full policy body to `/proxy/network/v2/api/site/<site>/firewall-policies/<id>`.
2. **Predefined matrix rules** (the auto-generated zone-to-zone defaults). PUT a minimal `{id, logging}` body to `/proxy/network/v2/api/site/<site>/firewall-policies/predefined/<origin_id>`, matching what the Network UI itself sends. Predefined rules are skipped unless you pass `--include-predefined`.

A built-in retry handles HTTP 429 rate limiting using the `Retry-After` header.

## Prerequisites

- Python 3.9 or newer.
- A UniFi gateway reachable on its management IP (UDM/UDM-Pro/UDM-SE/UCG/Dream Router etc., running a recent Network application with ZBF enabled).
- A local API key, generated from **Network → Settings → Control Plane → Integrations**.
- The `requests` library: `pip3 install requests`.

## Configuration

Set three environment variables before running:

```bash
export UNIFI_HOST="172.30.50.1"          # gateway IP or hostname
export UNIFI_API_KEY="paste-key-here"    # from Control Plane > Integrations
export UNIFI_SITE="default"              # optional, defaults to "default"
```

To make these persistent, add the lines to `~/.zshrc` (macOS default) or `~/.bashrc`. Treat the API key like a password; do not commit it to git.

## Usage

All invocations from the directory containing the script.

### Dry run (recommended first step)

```bash
python3 Unifi_FW_Rule_Logging.py
```

Lists every policy and shows which ones would have logging enabled. No changes made.

### Dry run, only Block/Reject rules

```bash
python3 Unifi_FW_Rule_Logging.py --only-blocks
```

Most useful filter for security visibility. Allow rules typically generate too much noise to log.

### Apply changes to Block/Reject rules

```bash
python3 Unifi_FW_Rule_Logging.py --only-blocks --apply
```

Adds `--apply` to actually PUT the updates back to the gateway.

### Filter by zone

```bash
python3 Unifi_FW_Rule_Logging.py --src-zone IOT --apply
python3 Unifi_FW_Rule_Logging.py --dst-zone DMZ --apply
python3 Unifi_FW_Rule_Logging.py --src-zone IOT --dst-zone Internal --apply
```

Substring match against zone names. Combine `--src-zone` and `--dst-zone` to narrow further.

### Include predefined matrix rules

```bash
python3 Unifi_FW_Rule_Logging.py --include-predefined --apply
```

Use with caution. The matrix contains a row/column entry for every zone pair, so this can produce a lot of syslog volume.

### Common flag combinations

| Goal | Command |
| --- | --- |
| See everything that would change | `python3 Unifi_FW_Rule_Logging.py` |
| Log all Block/Reject rules | `python3 Unifi_FW_Rule_Logging.py --only-blocks --apply` |
| Log Blocks from IOT only | `python3 Unifi_FW_Rule_Logging.py --only-blocks --src-zone IOT --apply` |
| Log everything including matrix defaults | `python3 Unifi_FW_Rule_Logging.py --include-predefined --apply` |

## Verifying results

After `--apply`, confirm in the UniFi UI under **Settings → Security → Firewall → Zone-Based Firewall** that the affected rules show "Log Activity" enabled. Syslog output then flows to whatever destination you have configured under **Settings → System → Application Logging** (typically a syslog server or local SIEM collector).

## Troubleshooting

### `TypeError: unsupported operand type(s) for |: 'type' and 'NoneType'`

You are on Python 3.9 or older. The script uses PEP 604 union syntax (`dict | None`) which requires 3.10+. The fix already applied is `from __future__ import annotations` at the top of the file, which makes all annotations lazy-evaluated strings and works on 3.9. If you ever see this again after pulling a new version, re-add that import.

### `NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+...`

Cosmetic. macOS's stock `/usr/bin/python3` links against LibreSSL, which urllib3 v2 grumbles about. Three ways to silence it:

1. Install Python from [python.org](https://www.python.org) or via Homebrew (`brew install python@3.12`); these link against OpenSSL.
2. Pin an older urllib3: `pip3 install 'urllib3<2'`.
3. Ignore it. It does not affect the API calls.

### HTTP 401 / 403 from the gateway

The API key is wrong, expired, or scoped to the wrong site. Regenerate it under **Control Plane → Integrations** and make sure `UNIFI_SITE` matches the site the key was created in.

### HTTP 429 (rate limited)

The script handles this automatically by sleeping for the duration the server requests, up to 5 retries. If you see repeated 429s, run with smaller filters (one zone at a time) instead of touching everything in one pass.

### Connection errors to the gateway IP

Confirm `UNIFI_HOST` is reachable from your workstation (`ping`, `curl -k https://<host>`). The script disables TLS verification because UniFi gateways typically present self-signed certs.

## Safety notes

- Always run a dry run before adding `--apply`.
- `--include-predefined` can flip on logging for hundreds of matrix entries at once; consider whether your syslog ingestion is sized for that.
- The script does not disable logging anywhere. If you want to revert, you currently have to toggle rules off in the UI (or extend the script to take a `--disable` flag).

## File locations

- Script: `Unifi_Scripts/Unifi_FW_Rule_Logging.py`
- This doc: `Unifi_Scripts/Unifi_FW_Rule_Logging.md`
