#!/usr/bin/env python3
"""Live test harness for Sigenergy Cloud authentication.

Usage:
    python test_auth_live.py

Credentials are read from environment variables or prompted interactively:
    SIGEN_USERNAME   – Sigenergy account email/username
    SIGEN_PASSWORD   – Sigenergy account password
    SIGEN_REGION     – API region (apac, aus, eu, us, cn)  [default: apac]
    SIGEN_STATION_SN_CODE – Optional station serial code for weather call
    SIGEN_STATS_DATE – Optional YYYYMMDD date for daily stats endpoints
"""

from __future__ import annotations

import asyncio
from datetime import datetime
import importlib.util
import json
import logging
import os
import re
import sys

import aiohttp

# Direct file-level imports to avoid __init__.py (which requires homeassistant)
_HERE = os.path.dirname(os.path.abspath(__file__))
_PKG = os.path.join(_HERE, "custom_components", "sigenergy_cloud")


def _import_module(name: str, filepath: str):
    spec = importlib.util.spec_from_file_location(name, filepath)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# Load const first (api imports from it via relative import, so we register the package)
sys.modules.setdefault("custom_components", type(sys)("custom_components"))
sys.modules.setdefault("custom_components.sigenergy_cloud", type(sys)("custom_components.sigenergy_cloud"))
const = _import_module("custom_components.sigenergy_cloud.const", os.path.join(_PKG, "const.py"))
api = _import_module("custom_components.sigenergy_cloud.api", os.path.join(_PKG, "api.py"))

SigenCloudApiClient = api.SigenCloudApiClient
SigenCloudApiError = api.SigenCloudApiError
SigenCloudAuthError = api.SigenCloudAuthError
BASE_URLS = const.BASE_URLS
DEFAULT_REGION = const.DEFAULT_REGION
REGIONS = const.REGIONS


def _prompt(label: str, *, secret: bool = False, default: str = "") -> str:
    """Prompt for a value, falling back to *default*."""
    suffix = f" [{default}]" if default else ""
    if secret:
        import getpass
        value = getpass.getpass(f"{label}{suffix}: ")
    else:
        value = input(f"{label}{suffix}: ")
    return value.strip() or default


def _get_credentials() -> tuple[str, str, str]:
    """Return (username, password, region) from env vars or interactive prompts."""
    username = os.environ.get("SIGEN_USERNAME", "")
    password = os.environ.get("SIGEN_PASSWORD", "")
    region = os.environ.get("SIGEN_REGION", "")

    if not username:
        username = _prompt("Username (email)")
    if not password:
        password = _prompt("Password", secret=True)
    if not region:
        region = _prompt(f"Region ({', '.join(REGIONS)})", default=DEFAULT_REGION)

    if region not in REGIONS:
        print(f"ERROR: unknown region '{region}'. Must be one of {REGIONS}")
        sys.exit(1)

    return username, password, region


def _get_station_sn_code(station_payload: object) -> str | None:
    """Extract stationSnCode from station payload, if present."""
    if isinstance(station_payload, dict):
        value = station_payload.get("stationSnCode")
        if value is not None:
            return str(value)

    if isinstance(station_payload, list) and station_payload:
        first = station_payload[0]
        if isinstance(first, dict):
            value = first.get("stationSnCode")
            if value is not None:
                return str(value)

    return None


def _dump_payload(title: str, payload: object) -> None:
    """Pretty-print a full payload for debugging."""
    print(f"\n--- {title} ---")
    try:
        print(json.dumps(payload, indent=2, ensure_ascii=True, default=str))
    except TypeError:
        print(payload)


def _collect_load_paths(payload: object) -> list[str]:
    """Collect smart load paths from a nested payload."""
    paths: set[str] = set()

    def _walk(node: object) -> None:
        if isinstance(node, dict):
            value = node.get("loadPath")
            if isinstance(value, str) and value:
                paths.add(value)
            for item in node.values():
                _walk(item)
        elif isinstance(node, list):
            for item in node:
                _walk(item)

    _walk(payload)
    return sorted(paths)


async def run() -> None:
    if os.environ.get("SIGEN_DEBUG", "").strip() in {"1", "true", "TRUE", "yes", "YES"}:
        logging.basicConfig(level=logging.DEBUG)

    username, password, region = _get_credentials()
    stats_date = os.environ.get("SIGEN_STATS_DATE", "").strip() or datetime.now().strftime("%Y%m%d")
    base_url = BASE_URLS[region]

    print(f"\n--- Sigenergy Cloud Auth Test ---")
    print(f"Region : {region}")
    print(f"API URL: {base_url}")
    print(f"User   : {username}")
    print(f"Date   : {stats_date}")
    print()

    async with aiohttp.ClientSession() as session:
        client = SigenCloudApiClient(
            session=session,
            username=username,
            password=password,
            region=region,
        )

        # --- Step 1: Authenticate ---
        print("[1] Authenticating ...", end=" ", flush=True)
        try:
            await client.authenticate()
        except SigenCloudAuthError as exc:
            print(f"FAILED\n    Auth error: {exc}")
            return
        except SigenCloudApiError as exc:
            print(f"FAILED\n    API error: {exc}")
            return

        print("OK")
        print(f"    access_token : {client._access_token[:20]}..." if client._access_token else "    (none)")
        print(f"    refresh_token: {client._refresh_token_value[:20]}..." if client._refresh_token_value else "    (none)")

        # --- Step 2: Fetch station ---
        print("\n[2] Fetching station info ...", end=" ", flush=True)
        try:
            station = await client.get_station()
        except SigenCloudApiError as exc:
            print(f"FAILED\n    {exc}")
            return

        print("OK")
        station_id = None
        if isinstance(station, dict):
            station_id = station.get("stationId") or station.get("id")
            print(f"    station data keys: {list(station.keys())}")
            if station_id:
                print(f"    stationId: {station_id}")
        elif isinstance(station, list) and station:
            first = station[0] if isinstance(station[0], dict) else {}
            station_id = first.get("stationId") or first.get("id")
            print(f"    stations returned: {len(station)}")
            if station_id:
                print(f"    first stationId: {station_id}")
        else:
            print(f"    raw: {station}")

        _dump_payload("Station response", station)

        station_sn_code = os.environ.get("SIGEN_STATION_SN_CODE", "").strip() or _get_station_sn_code(station)

        # --- Step 3: Energy flow (if station found) ---
        if station_id:
            print(f"\n[3] Fetching energy flow for station {station_id} ...", end=" ", flush=True)
            try:
                flow = await client.get_energy_flow(station_id)
                print("OK")
                if isinstance(flow, dict):
                    print(f"    energy flow keys: {list(flow.keys())}")
                else:
                    print(f"    raw: {flow}")
                _dump_payload("Energy flow response", flow)
            except SigenCloudApiError as exc:
                print(f"FAILED\n    {exc}")

            # --- Step 4: Current mode ---
            print(f"\n[4] Fetching current mode for station {station_id} ...", end=" ", flush=True)
            try:
                mode = await client.get_current_mode(station_id)
                print("OK")
                if isinstance(mode, dict):
                    print(f"    mode data: {mode}")
                else:
                    print(f"    raw: {mode}")
                _dump_payload("Current mode response", mode)
            except SigenCloudApiError as exc:
                print(f"FAILED\n    {exc}")

            # --- Step 5: Available modes ---
            print(f"\n[5] Fetching available modes for station {station_id} ...", end=" ", flush=True)
            try:
                all_modes = await client.get_available_modes(station_id)
                print("OK")
                _dump_payload("Available modes response", all_modes)
            except SigenCloudApiError as exc:
                print(f"FAILED\n    {exc}")

            # --- Step 6: System devices ---
            print(f"\n[6] Fetching system devices for station {station_id} ...", end=" ", flush=True)
            try:
                devices = await client.get_system_devices(station_id)
                print("OK")
                _dump_payload("System devices response", devices)

                load_paths = _collect_load_paths(devices)
                if load_paths:
                    print(f"\n    Found {len(load_paths)} loadPath value(s): {load_paths}")
                else:
                    print("\n    No loadPath values found in system devices payload")

                # --- Step 7: Smart load details ---
                for index, load_path in enumerate(load_paths, start=1):
                    print(
                        f"\n[7.{index}] Fetching smart load details for loadPath={load_path} ...",
                        end=" ",
                        flush=True,
                    )
                    try:
                        smart_load = await client.get_smart_load_details(station_id, load_path)
                        print("OK")
                        _dump_payload(f"Smart load response ({load_path})", smart_load)
                    except SigenCloudApiError as exc:
                        print(f"FAILED\n    {exc}")
            except SigenCloudApiError as exc:
                print(f"FAILED\n    {exc}")

            # --- Step 8: Current weather ---
            if station_sn_code:
                print(
                    f"\n[8] Fetching current local weather for stationSnCode={station_sn_code} ...",
                    end=" ",
                    flush=True,
                )
                try:
                    weather = await client.get_current_local_weather(station_sn_code)
                    print("OK")
                    _dump_payload("Current local weather response", weather)
                except SigenCloudApiError as exc:
                    print(f"FAILED\n    {exc}")
            else:
                print("\n[8] Skipped current local weather (no stationSnCode found)")

            # --- Step 9: Daily energy stats ---
            print(
                f"\n[9] Fetching energy stats for stationId={station_id} date={stats_date} ...",
                end=" ",
                flush=True,
            )
            try:
                energy_stats = await client.get_energy_stats(
                    station_id,
                    stats_date,
                    stats_date,
                    date_flag=1,
                )
                print("OK")
                _dump_payload("Energy stats response", energy_stats)
            except SigenCloudApiError as exc:
                print(f"FAILED\n    {exc}")

            # --- Step 10: Custom energy stats ---
            print(
                f"\n[10] Fetching custom energy stats for stationId={station_id} date={stats_date} ...",
                end=" ",
                flush=True,
            )
            try:
                custom_energy_stats = await client.get_custom_energy_stats(
                    station_id,
                    stats_date,
                    stats_date,
                    date_flag=1,
                    resource_ids="energy_card"
                )
                print("OK")
                _dump_payload("Custom energy stats response", custom_energy_stats)
            except SigenCloudApiError as exc:
                message = str(exc)
                lowered = message.lower()
                if (
                    "unsupported for this account/region" in lowered
                    or (
                        "http 500" in lowered
                        and (
                            "system error" in lowered
                            or re.search(r'"code"\s*:\s*1\b', lowered) is not None
                        )
                    )
                ):
                    print("UNAVAILABLE")
                    print("    Endpoint appears unsupported for this account/region")
                else:
                    print(f"FAILED\n    {exc}")

        else:
            print("\n[3] Skipped energy flow (no stationId found)")
            print("[4] Skipped current mode (no stationId found)")
            print("[5] Skipped available modes (no stationId found)")
            print("[6] Skipped system devices (no stationId found)")
            print("[7] Skipped smart load details (no stationId found)")
            print("[8] Skipped current local weather (no stationId found)")
            print("[9] Skipped energy stats (no stationId found)")
            print("[10] Skipped custom energy stats (no stationId found)")

        # --- Step 11: Token refresh ---
        print("\n[11] Testing token refresh ...", end=" ", flush=True)
        try:
            await client._do_refresh_token()
            print("OK")
            print(f"    new access_token : {client._access_token[:20]}..." if client._access_token else "    (none)")
        except SigenCloudAuthError as exc:
            print(f"FAILED\n    {exc}")
        except SigenCloudApiError as exc:
            print(f"FAILED\n    {exc}")

    print("\n--- Done ---")


if __name__ == "__main__":
    asyncio.run(run())
