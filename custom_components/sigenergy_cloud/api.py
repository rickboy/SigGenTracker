"""Async API client for the Sigenergy Cloud API."""

from __future__ import annotations

import base64
import logging
from typing import Any

import aiohttp
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.padding import PKCS7

from .const import (
    AES_IV,
    AES_KEY,
    BASE_URLS,
    DEFAULT_REGION,
    ENDPOINT_AUTH,
    ENDPOINT_ENERGY_FLOW,
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


def _encrypt_password(password: str) -> str:
    """Encrypt password using AES-CBC with PKCS7 padding."""
    padder = PKCS7(128).padder()
    padded = padder.update(password.encode("utf-8")) + padder.finalize()
    cipher = Cipher(algorithms.AES(AES_KEY), modes.CBC(AES_IV))
    encryptor = cipher.encryptor()
    encrypted = encryptor.update(padded) + encryptor.finalize()
    return base64.b64encode(encrypted).decode("utf-8")


class SigenCloudApiClient:
    """Async client for the Sigenergy Cloud API."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        username: str,
        password: str,
        region: str = DEFAULT_REGION,
    ) -> None:
        self._session = session
        self._username = username
        self._password = password
        self._base_url = BASE_URLS[region]
        self._access_token: str | None = None
        self._refresh_token_value: str | None = None

    async def authenticate(self) -> None:
        """Authenticate and obtain access + refresh tokens."""
        encrypted_pw = _encrypt_password(self._password)

        data = {
            "grant_type": "password",
            "username": self._username,
            "password": encrypted_pw,
        }

        auth = aiohttp.BasicAuth(OAUTH_CLIENT_ID, OAUTH_CLIENT_SECRET)

        try:
            async with self._session.post(
                f"{self._base_url}/{ENDPOINT_AUTH}",
                data=data,
                auth=auth,
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise SigenCloudAuthError(
                        f"Authentication failed (HTTP {resp.status}): {text}"
                    )
                result = await resp.json()
        except aiohttp.ClientError as err:
            raise SigenCloudApiError(f"Connection error during auth: {err}") from err

        self._access_token = result.get("access_token")
        self._refresh_token_value = result.get("refresh_token")

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
                if resp.status != 200:
                    raise SigenCloudAuthError("Token refresh failed, re-auth needed")
                result = await resp.json()
        except aiohttp.ClientError as err:
            raise SigenCloudApiError(
                f"Connection error during token refresh: {err}"
            ) from err

        self._access_token = result.get("access_token")
        self._refresh_token_value = result.get("refresh_token")

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
                if resp.status == 401 and retry_auth:
                    _LOGGER.debug("Token expired, refreshing")
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
    # Convenience: fetch all data in one coordinator cycle
    # ------------------------------------------------------------------

    async def get_all_data(self, station_id: str) -> dict[str, Any]:
        """Fetch energy flow + current mode for the coordinator."""
        energy_flow = await self.get_energy_flow(station_id)
        current_mode = await self.get_current_mode(station_id)
        return {
            "energy_flow": energy_flow,
            "current_mode": current_mode,
        }
