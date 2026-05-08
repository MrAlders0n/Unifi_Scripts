#!/usr/bin/env python3
"""
Bulk-enable syslog logging on UniFi Zone-Based Firewall policies.

Usage:
    # Dry run - see what would change
    python3 unifi_enable_logging.py

    # Dry run - only block/reject rules
    python3 unifi_enable_logging.py --only-blocks

    # Apply changes to block rules only
    python3 unifi_enable_logging.py --only-blocks --apply

    # Filter by source or destination zone name
    python3 unifi_enable_logging.py --src-zone IOT --apply

    # Include predefined matrix rules (use with caution)
    python3 unifi_enable_logging.py --include-predefined --apply

Environment variables:
    UNIFI_HOST      Gateway IP (e.g. 172.30.50.1)
    UNIFI_API_KEY   API key from Network > Settings > Control Plane > Integrations
    UNIFI_SITE      Site name (default: "default")
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def get_session(host: str, api_key: str) -> requests.Session:
    s = requests.Session()
    s.headers.update({"X-API-KEY": api_key})
    s.verify = False
    s.base_url = f"https://{host}"
    return s


def request_with_retry(method: str, session: requests.Session, url: str, **kwargs) -> requests.Response:
    for attempt in range(5):
        r = session.request(method, url, timeout=15, **kwargs)
        if r.status_code == 429:
            wait = int(r.headers.get("Retry-After", 5))
            print(f"  rate limited, waiting {wait}s...")
            time.sleep(wait)
            continue
        return r
    r.raise_for_status()
    return r


def list_policies(session: requests.Session, site: str) -> list[dict[str, Any]]:
    url = f"{session.base_url}/proxy/network/v2/api/site/{site}/firewall-policies"
    r = request_with_retry("GET", session, url)
    r.raise_for_status()
    data = r.json()
    return data if isinstance(data, list) else data.get("data", [])


def list_zones(session: requests.Session, site: str) -> dict[str, str]:
    """Build zone_id -> zone_name map. Returns empty dict if endpoint unavailable."""
    url = f"{session.base_url}/proxy/network/v2/api/site/{site}/firewall-zones"
    try:
        r = request_with_retry("GET", session, url)
        if r.status_code == 200:
            zones = r.json()
            return {z.get("_id", ""): z.get("name", "?") for z in zones}
    except Exception:
        pass
    return {}


def update_policy(session: requests.Session, site: str, policy: dict[str, Any]) -> requests.Response:
    """
    PUT a policy back. Predefined matrix rules use a different endpoint and
    a minimal payload (just id + logging), matching what the Network UI sends.
    User-defined rules take the full policy body at the regular endpoint.
    """
    if policy.get("predefined"):
        oid = policy.get("origin_id")
        if not oid:
            raise ValueError(f"predefined policy missing origin_id: {policy.get('name')}")
        url = f"{session.base_url}/proxy/network/v2/api/site/{site}/firewall-policies/predefined/{oid}"
        body = {"id": oid, "logging": policy.get("logging", True)}
    else:
        pid = policy["_id"]
        url = f"{session.base_url}/proxy/network/v2/api/site/{site}/firewall-policies/{pid}"
        body = policy
    return request_with_retry("PUT", session, url, json=body)


def zone_name(zmap: dict[str, str], obj: dict | None) -> str:
    if not obj:
        return "?"
    zid = obj.get("zone_id", "")
    return zmap.get(zid, zid[-6:] if zid else "?")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--apply", action="store_true", help="Apply changes (default is dry run)")
    p.add_argument("--only-blocks", action="store_true", help="Only enable on Block/Reject rules")
    p.add_argument("--src-zone", help="Filter by source zone name (substring match)")
    p.add_argument("--dst-zone", help="Filter by destination zone name (substring match)")
    p.add_argument("--include-predefined", action="store_true", help="Also process predefined matrix rules")
    args = p.parse_args()

    host = os.environ.get("UNIFI_HOST")
    api_key = os.environ.get("UNIFI_API_KEY")
    site = os.environ.get("UNIFI_SITE", "default")

    if not host or not api_key:
        print("ERROR: set UNIFI_HOST and UNIFI_API_KEY environment variables", file=sys.stderr)
        return 1

    session = get_session(host, api_key)

    # Build zone map for display
    print(f"Connecting to https://{host} (site={site})...")
    zmap = list_zones(session, site)
    if zmap:
        print(f"Loaded {len(zmap)} zones")

    print("Fetching policies...")
    try:
        policies = list_policies(session, site)
    except requests.HTTPError as e:
        print(f"ERROR: {e}\nResponse: {e.response.text[:500]}", file=sys.stderr)
        return 2

    print(f"Got {len(policies)} total policies\n")

    candidates = []
    for pol in policies:
        # Skip predefined unless explicitly included
        if pol.get("predefined") and not args.include_predefined:
            continue

        # Already logging?
        if pol.get("logging"):
            continue

        # Disabled rules - skip
        if not pol.get("enabled", True):
            continue

        # --only-blocks filter
        if args.only_blocks:
            action = (pol.get("action") or "").upper()
            if action not in ("BLOCK", "REJECT", "DROP"):
                continue

        # Zone name filters
        src_name = zone_name(zmap, pol.get("source"))
        dst_name = zone_name(zmap, pol.get("destination"))

        if args.src_zone and args.src_zone.upper() not in src_name.upper():
            continue
        if args.dst_zone and args.dst_zone.upper() not in dst_name.upper():
            continue

        candidates.append(pol)

    print(f"{len(candidates)} policies need logging enabled:")
    for pol in candidates:
        src = zone_name(zmap, pol.get("source"))
        dst = zone_name(zmap, pol.get("destination"))
        pre = " [predefined]" if pol.get("predefined") else ""
        print(f"  [{pol.get('action'):6}] {src:16} -> {dst:16} \"{pol.get('name')}\"{pre}")

    if not candidates:
        print("Nothing to do.")
        return 0

    if not args.apply:
        print(f"\nDry run. Re-run with --apply to enable logging on these {len(candidates)} policies.")
        return 0

    print(f"\nApplying logging=true to {len(candidates)} policies...")
    ok = 0
    fail = 0
    for pol in candidates:
        pol["logging"] = True
        src = zone_name(zmap, pol.get("source"))
        dst = zone_name(zmap, pol.get("destination"))
        label = f"{src} -> {dst} \"{pol.get('name')}\""
        try:
            r = update_policy(session, site, pol)
            if r.status_code in (200, 201, 204):
                print(f"  OK  {label}")
                ok += 1
            else:
                print(f"  FAIL {label}  HTTP {r.status_code}: {r.text[:200]}")
                fail += 1
        except Exception as e:
            print(f"  ERR  {label}  {e}")
            fail += 1
        time.sleep(0.3)  # gentle on the controller

    print(f"\nDone. {ok} updated, {fail} failed.")
    return 0 if fail == 0 else 3


if __name__ == "__main__":
    sys.exit(main())
