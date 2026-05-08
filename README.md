# Unifi_Scripts

A collection of UniFi scripts to simplify auditing and management of Zone-Based Firewall and related Network Application features. Each script is self-contained and talks to a UniFi gateway over the local Network REST API using a key generated under **Network → Settings → Control Plane → Integrations**.

## Scripts

### Unifi_FW_Rule_Logging.py

Bulk-enable syslog logging on UniFi Zone-Based Firewall (ZBF) policies. Runs as a dry run by default so you can preview changes; pass `--apply` to write them back. Supports filters for source/destination zone and an `--only-blocks` flag to target just Block/Reject rules (typically the only ones worth logging).

Quick start:

```bash
export UNIFI_HOST="172.30.50.1"
export UNIFI_API_KEY="paste-key-here"
export UNIFI_SITE="default"          # optional

# Preview which Block/Reject rules would have logging turned on
python3 Unifi_FW_Rule_Logging.py --only-blocks

# Apply it
python3 Unifi_FW_Rule_Logging.py --only-blocks --apply
```

Full operator guide, including all flags, troubleshooting (Python 3.9 union-syntax fix, LibreSSL warning, 401/429 errors), and safety notes: see [Unifi_FW_Rule_Logging.md](Unifi_FW_Rule_Logging.md).

## Requirements

- Python 3.9 or newer
- `pip3 install requests`
- A UniFi gateway running a recent Network application with ZBF enabled
- A local API key from **Control Plane → Integrations**

## Conventions

- All scripts read `UNIFI_HOST`, `UNIFI_API_KEY`, and `UNIFI_SITE` from the environment.
- All scripts default to dry-run behavior. Mutating actions require an explicit `--apply` flag.
- TLS verification is disabled because UniFi gateways present self-signed certs by default.
- Treat the API key like a password. Do not commit it.

## License

See [LICENSE](LICENSE).
