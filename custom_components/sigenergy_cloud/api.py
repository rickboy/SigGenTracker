"""Async API client for the Sigenergy Cloud API."""

from __future__ import annotations

import base64
import json
import logging
from datetime import datetime
from typing import Any

import aiohttp
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.padding import PKCS7

try:
    from homeassistant.util import dt as dt_util
except ImportError:
    dt_util = None

from .const import (
    AES_IV,
    AES_KEY,
    BASE_URLS,
    DEFAULT_REGION,
    ENDPOINT_AUTH,
    ENDPOINT_CURRENT_LOCAL_WEATHER,
    ENDPOINT_ENERGY_FLOW,
    ENDPOINT_ENERGY_STATS,
    ENDPOINT_ENERGY_STATS_CUSTOM,
    ENDPOINT_MODE_CURRENT,
    ENDPOINT_MODE_SET,
    ENDPOINT_MODES_ALL,
    ENDPOINT_SMART_LOAD_TOGGLE,
    ENDPOINT_SMART_LOADS,
    ENDPOINT_STATION_HOME,
    ENDPOINT_SYSTEM_DEVICES,
    OAUTH_CLIENT_ID,
    OAUTH_CLIENT_SECRET,
)

_LOGGER = logging.getLogger(__name__)


class SigenCloudApiError(Exception):
    """Base exception for Sigenergy Cloud API errors."""


class SigenCloudAuthError(SigenCloudApiError):
    """Authentication failed."""


def _redact_auth_payload(payload: str) -> str:
    """Redact sensitive auth fields in a JSON payload string for debug logs."""
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return payload

    if isinstance(data, dict):
        for key in ("access_token", "refresh_token"):
            if key in data and isinstance(data[key], str):
                token = data[key]
                data[key] = f"{token[:8]}..." if len(token) > 8 else "***"
    return json.dumps(data, ensure_ascii=True)


def _encrypt_password(password: str) -> str:
    """Encrypt password using AES-CBC with PKCS7 padding."""
    padder = PKCS7(128).padder()
    padded = padder.update(password.encode("utf-8")) + padder.finalize()
    cipher = Cipher(algorithms.AES(AES_KEY), modes.CBC(AES_IV))
    encryptor = cipher.encryptor()
    encrypted = encryptor.update(padded) + encryptor.finalize()
    return base64.b64encode(encrypted).decode("utf-8")


def _extract_tokens(payload: dict[str, Any]) -> tuple[str | None, str | None]:
    """Extract access/refresh tokens from either top-level or nested data payloads."""
    access_token = payload.get("access_token")
    refresh_token = payload.get("refresh_token")

    data = payload.get("data")
    if isinstance(data, dict):
        access_token = access_token or data.get("access_token")
        refresh_token = refresh_token or data.get("refresh_token")

    return access_token, refresh_token


class SigenCloudApiClient:
    """Async client for the Sigenergy Cloud API."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        username: str,
        password: str,
        region: str = DEFAULT_REGION,
        user_device_id: str = "",
    ) -> None:
        self._session = session
        self._username = username
        self._password = password
        self._base_url = BASE_URLS[region]
        self._user_device_id = user_device_id
        self._access_token: str | None = None
        self._refresh_token_value: str | None = None
        self._station_sn_code: str | None = None

    def set_station_context(self, station_info: dict[str, Any]) -> None:
        """Synchronously persist station context for later non-auth API calls."""
        for key in ("stationSnCode", "stationSNCode", "stationSn", "snCode"):
            value = station_info.get(key)
            if value:
                self._station_sn_code = str(value)
                break

    async def authenticate(self) -> None:
        """Authenticate and obtain access + refresh tokens."""
        encrypted_pw = _encrypt_password(self._password)

        data = {
            "grant_type": "password",
            "username": self._username,
            "password": encrypted_pw,
            "scope": "server",
            "userDeviceId": self._user_device_id
        }

        auth = aiohttp.BasicAuth(OAUTH_CLIENT_ID, OAUTH_CLIENT_SECRET)

        try:
            async with self._session.post(
                f"{self._base_url}/{ENDPOINT_AUTH}",
                data=data,
                auth=auth,
            ) as resp:
                resp_text = await resp.text()
                result: dict[str, Any]
                if resp_text:
                    try:
                        result = json.loads(resp_text)
                    except json.JSONDecodeError:
                        result = await resp.json()
                else:
                    result = await resp.json()
                _LOGGER.debug(
                    "Auth POST response status=%s body=%s",
                    resp.status,
                    _redact_auth_payload(resp_text) if resp_text else json.dumps(result, ensure_ascii=True),
                )
                if resp.status != 200:
                    raise SigenCloudAuthError(
                        f"Authentication failed (HTTP {resp.status}): {resp_text}"
                    )
        except aiohttp.ClientError as err:
            raise SigenCloudApiError(f"Connection error during auth: {err}") from err

        self._access_token, self._refresh_token_value = _extract_tokens(result)

        if not self._access_token:
            raise SigenCloudAuthError("No access_token in auth response")

    async def _do_refresh_token(self) -> None:
        """Refresh the access token using the stored refresh token."""
        if not self._refresh_token_value:
            raise SigenCloudAuthError("No refresh token available")

        data = {
            "grant_type": "refresh_token",
            "refresh_token": self._refresh_token_value,
        }

        auth = aiohttp.BasicAuth(OAUTH_CLIENT_ID, OAUTH_CLIENT_SECRET)

        try:
            async with self._session.post(
                f"{self._base_url}/{ENDPOINT_AUTH}",
                data=data,
                auth=auth,
            ) as resp:
                resp_text = await resp.text()
                result: dict[str, Any]
                if resp_text:
                    try:
                        result = json.loads(resp_text)
                    except json.JSONDecodeError:
                        result = await resp.json()
                else:
                    result = await resp.json()
                _LOGGER.debug(
                    "Refresh POST response status=%s body=%s",
                    resp.status,
                    _redact_auth_payload(resp_text) if resp_text else json.dumps(result, ensure_ascii=True),
                )
                if resp.status != 200:
                    raise SigenCloudAuthError("Token refresh failed, re-auth needed")
        except aiohttp.ClientError as err:
            raise SigenCloudApiError(
                f"Connection error during token refresh: {err}"
            ) from err

        self._access_token, self._refresh_token_value = _extract_tokens(result)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
        retry_auth: bool = True,
    ) -> dict[str, Any]:
        """Make an authenticated API request with automatic token refresh."""
        if not self._access_token:
            await self.authenticate()

        headers = {"Authorization": f"Bearer {self._access_token}"}
        url = f"{self._base_url}/{path}"

        try:
            async with self._session.request(
                method,
                url,
                headers=headers,
                params=params,
                json=json_data,
            ) as resp:
                if resp.status in (401, 424) and retry_auth:
                    _LOGGER.debug("Auth expired (HTTP %s), refreshing", resp.status)
                    try:
                        await self._do_refresh_token()
                    except SigenCloudAuthError:
                        await self.authenticate()
                    return await self._request(
                        method, path, params=params, json_data=json_data, retry_auth=False
                    )

                if resp.status != 200:
                    text = await resp.text()
                    raise SigenCloudApiError(
                        f"API error {method} {path} (HTTP {resp.status}): {text}"
                    )

                result = await resp.json()
        except aiohttp.ClientError as err:
            raise SigenCloudApiError(f"Connection error: {err}") from err

        code = result.get("code")
        if code is not None and code != 0:
            raise SigenCloudApiError(
                f"API returned error code {code}: {result.get('message', 'unknown')}"
            )

        return result.get("data", result)

    # ------------------------------------------------------------------
    # Station
    # ------------------------------------------------------------------

    async def get_station(self) -> dict[str, Any]:
        """Get the user's home station info (stationId, capacities, etc.)."""
        return await self._request("GET", ENDPOINT_STATION_HOME)

    # ------------------------------------------------------------------
    # Energy flow (real-time power data)
    # ------------------------------------------------------------------

    async def get_energy_flow(self, station_id: str) -> dict[str, Any]:
        """Get real-time energy flow data for a station."""
        return await self._request(
            "GET", ENDPOINT_ENERGY_FLOW, params={"id": station_id}
        )

    # ------------------------------------------------------------------
    # Operational modes
    # ------------------------------------------------------------------

    async def get_available_modes(self, station_id: str) -> dict[str, Any]:
        """Get all available operational modes for a station."""
        return await self._request("GET", f"{ENDPOINT_MODES_ALL}/{station_id}")

    async def get_current_mode(self, station_id: str) -> dict[str, Any]:
        """Get the current operational mode for a station."""
        return await self._request("GET", f"{ENDPOINT_MODE_CURRENT}/{station_id}")

    async def set_operational_mode(
        self, station_id: str, mode: int, profile_id: str | None = None
    ) -> dict[str, Any]:
        """Set the operational mode for a station."""
        payload: dict[str, Any] = {
            "stationId": station_id,
            "workingMode": mode,
        }
        if profile_id is not None:
            payload["profileId"] = profile_id
        return await self._request("PUT", ENDPOINT_MODE_SET, json_data=payload)

    # ------------------------------------------------------------------
    # Smart loads
    # ------------------------------------------------------------------

    async def get_system_devices(self, station_id: str) -> dict[str, Any]:
        """Get system device cards (includes smart load paths)."""
        return await self._request(
            "GET", ENDPOINT_SYSTEM_DEVICES, params={"stationId": station_id}
        )

    async def get_smart_load_details(
        self, station_id: str, load_path: str
    ) -> dict[str, Any]:
        """Get details for a specific smart load."""
        return await self._request(
            "GET",
            ENDPOINT_SMART_LOADS,
            params={"stationId": station_id, "loadPath": load_path},
        )

    async def toggle_smart_load(
        self, station_id: str, load_path: str, turn_on: bool
    ) -> dict[str, Any]:
        """Toggle a smart load on or off."""
        return await self._request(
            "PATCH",
            ENDPOINT_SMART_LOAD_TOGGLE,
            params={"stationId": station_id, "loadPath": load_path},
            json_data={"manualSwitch": 1 if turn_on else 0},
        )

    # ------------------------------------------------------------------
    # Weather
    # ------------------------------------------------------------------

    async def get_current_local_weather(self, station_sn_code: str) -> dict[str, Any]:
        """Get current local weather for a station serial number code."""
        return await self._request(
            "GET",
            ENDPOINT_CURRENT_LOCAL_WEATHER,
            params={"stationSnCode": station_sn_code},
        )

    async def get_energy_stats(
        self,
        station_id: str,
        start_date: str,
        end_date: str,
        *,
        date_flag: int = 1,
    ) -> dict[str, Any]:
        """Get daily energy statistics for a station and date range."""
        return await self._request(
            "GET",
            ENDPOINT_ENERGY_STATS,
            params={
                "stationId": station_id,
                "startDate": start_date,
                "endDate": end_date,
                "dateFlag": date_flag,
            },
        )

    async def get_custom_energy_stats(
        self,
        station_id: str,
        start_date: str,
        end_date: str,
        *,
        date_flag: int = 1,
        resource_ids: str = "energy_card",
    ) -> dict[str, Any]:
        """Get custom energy statistics for a station and date range.

        Some regions/accounts reject one station identifier key but accept another.
        Try a small compatibility set before surfacing the final API error.
        """
        start_variants = [start_date]
        end_variants = [end_date]
        if len(start_date) == 8 and start_date.isdigit():
            start_variants.append(f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:8]}")
        if len(end_date) == 8 and end_date.isdigit():
            end_variants.append(f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:8]}")

        params_candidates: list[dict[str, Any]] = []
        for sdate in start_variants:
            for edate in end_variants:
                params_candidates.extend(
                    [
                        {
                            "stationId": station_id,
                            "startDate": sdate,
                            "endDate": edate,
                            "dateFlag": date_flag,
                            "resourceIds": resource_ids,
                        },
                        {
                            "id": station_id,
                            "startDate": sdate,
                            "endDate": edate,
                            "dateFlag": date_flag,
                            "resourceIds": resource_ids,
                        },
                        {
                            "stationId": station_id,
                            "startDate": sdate,
                            "endDate": edate,
                            "resourceIds": resource_ids,
                        },
                    ]
                )

                if self._station_sn_code:
                    params_candidates.append(
                        {
                            "stationSnCode": self._station_sn_code,
                            "startDate": sdate,
                            "endDate": edate,
                            "dateFlag": date_flag,
                            "resourceIds": resource_ids,
                        }
                    )

        seen: set[tuple[tuple[str, Any], ...]] = set()
        deduped_candidates: list[dict[str, Any]] = []
        for params in params_candidates:
            key = tuple(sorted(params.items(), key=lambda item: item[0]))
            if key not in seen:
                seen.add(key)
                deduped_candidates.append(params)

        last_error: SigenCloudApiError | None = None
        for params in deduped_candidates:
            # For transient backend failures, retry once with the same request
            # before moving to compatibility variants.
            for attempt in (1, 2):
                try:
                    return await self._request(
                        "GET",
                        ENDPOINT_ENERGY_STATS_CUSTOM,
                        params=params,
                    )
                except SigenCloudApiError as err:
                    last_error = err
                    _LOGGER.debug(
                        "Custom energy stats failed method=GET attempt=%s params=%s: %s",
                        attempt,
                        params,
                        err,
                    )
                    if attempt == 1 and "HTTP 500" in str(err):
                        continue
                    break

        if last_error is not None:
            last_message = str(last_error)
            if "HTTP 500" in last_message and (
                "system error" in last_message.lower() or '"code":1' in last_message
            ):
                raise SigenCloudApiError(
                    "Custom energy stats endpoint appears unsupported for this account/region"
                ) from last_error
            raise SigenCloudApiError(
                f"Custom energy stats request failed after compatibility retries: {last_message}"
            ) from last_error

        raise SigenCloudApiError("Custom energy stats request failed")

    async def get_all_data(self, station_id: str) -> dict[str, Any]:
        """Fetch core and optional datasets for the coordinator."""
        energy_flow = await self.get_energy_flow(station_id)
        current_mode = await self.get_current_mode(station_id)

        result: dict[str, Any] = {
            "energy_flow": energy_flow,
            "current_mode": current_mode,
        }

        if self._station_sn_code:
            try:
                result["weather"] = await self.get_current_local_weather(self._station_sn_code)
            except SigenCloudApiError as err:
                _LOGGER.debug("Skipping weather data update: %s", err)

        now = dt_util.now() if dt_util is not None else datetime.now()
        today = now.strftime("%Y%m%d")

        try:
            result["energy_stats"] = await self.get_energy_stats(
                station_id,
                today,
                today,
                date_flag=1,
            )
        except SigenCloudApiError as err:
            _LOGGER.debug("Skipping energy stats update: %s", err)

        return result
