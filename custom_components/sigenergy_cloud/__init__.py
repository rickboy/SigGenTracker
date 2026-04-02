"""The Sigenergy Cloud integration."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any, TypeAlias

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import SigenCloudApiClient, SigenCloudApiError, SigenCloudAuthError
from .const import CONF_REGION, CONF_USER_DEVICE_ID, DEFAULT_REGION, DEFAULT_SCAN_INTERVAL, DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)

# ConfigEntry generic was added in HA 2024.x; use a simple alias for compatibility
SigenEnergyConfigEntry: TypeAlias = ConfigEntry


class SigenEnergyData:
    """Runtime data stored in the config entry."""

    def __init__(
        self,
        client: SigenCloudApiClient,
        coordinator: SigenEnergyDataUpdateCoordinator,
        station_id: str,
        station_info: dict[str, Any],
    ) -> None:
        self.client = client
        self.coordinator = coordinator
        self.station_id = station_id
        self.station_info = station_info


class SigenEnergyDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator to poll the Sigenergy Cloud API."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: SigenCloudApiClient,
        station_id: str,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.client = client
        self.station_id = station_id

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the API."""
        try:
            return await self.client.get_all_data(self.station_id)
        except SigenCloudAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except SigenCloudApiError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err


async def async_setup_entry(hass: HomeAssistant, entry: SigenEnergyConfigEntry) -> bool:
    """Set up Sigenergy Cloud from a config entry."""
    session = async_get_clientsession(hass)
    client = SigenCloudApiClient(
        session=session,
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        region=entry.data.get(CONF_REGION, DEFAULT_REGION),
        user_device_id=entry.data.get(CONF_USER_DEVICE_ID, ""),
    )

    try:
        await client.authenticate()
        station_info = await client.get_station()
        if isinstance(station_info, dict):
            client.set_station_context(station_info)
    except SigenCloudAuthError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except SigenCloudApiError as err:
        raise ConfigEntryAuthFailed(f"Setup failed: {err}") from err

    station_id = str(station_info.get("stationId", ""))
    if not station_id:
        raise ConfigEntryAuthFailed("No station found for this account")

    coordinator = SigenEnergyDataUpdateCoordinator(hass, client, station_id)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = SigenEnergyData(
        client=client,
        coordinator=coordinator,
        station_id=station_id,
        station_info=station_info,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SigenEnergyConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
