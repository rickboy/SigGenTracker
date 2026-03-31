"""Switch platform for Sigenergy Cloud integration — smart loads."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from .api import SigenCloudApiClient, SigenCloudApiError
from .const import DOMAIN

if TYPE_CHECKING:
    from . import SigenEnergyData

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Discover and set up smart load switch entities."""
    data: SigenEnergyData = hass.data[DOMAIN][entry.entry_id]
    client = data.client
    station_id = data.station_id

    entities: list[SigenSmartLoadSwitch] = []

    try:
        devices = await client.get_system_devices(station_id)
    except SigenCloudApiError:
        _LOGGER.debug("No system devices / smart loads found for station %s", station_id)
        return

    # devices may contain a list of smart load cards
    loads = devices if isinstance(devices, list) else devices.get("data", [])
    if not isinstance(loads, list):
        loads = []

    for load in loads:
        load_name = load.get("name", "Smart Load")
        load_path = load.get("path") or load.get("loadPath")
        if not load_path:
            continue
        entities.append(
            SigenSmartLoadSwitch(
                coordinator=data.coordinator,
                client=client,
                station_id=station_id,
                load_path=load_path,
                load_name=load_name,
            )
        )

    if entities:
        async_add_entities(entities)


class SigenSmartLoadSwitch(
    CoordinatorEntity[DataUpdateCoordinator[dict[str, Any]]], SwitchEntity
):
    """Switch entity for a Sigenergy smart load."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[dict[str, Any]],
        client: SigenCloudApiClient,
        station_id: str,
        load_path: str,
        load_name: str,
    ) -> None:
        super().__init__(coordinator)
        self._client = client
        self._station_id = station_id
        self._load_path = load_path
        self._attr_name = load_name
        self._attr_unique_id = f"{station_id}_smartload_{load_path}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, station_id)},
            "name": f"Sigenergy {station_id}",
            "manufacturer": "Sigenergy",
        }
        self._is_on: bool = False

    @property
    def is_on(self) -> bool:
        """Return true if the smart load is on."""
        return self._is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the smart load on."""
        try:
            await self._client.toggle_smart_load(self._station_id, self._load_path, True)
            self._is_on = True
            self.async_write_ha_state()
        except SigenCloudApiError:
            _LOGGER.exception("Failed to turn on smart load %s", self._load_path)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the smart load off."""
        try:
            await self._client.toggle_smart_load(self._station_id, self._load_path, False)
            self._is_on = False
            self.async_write_ha_state()
        except SigenCloudApiError:
            _LOGGER.exception("Failed to turn off smart load %s", self._load_path)
