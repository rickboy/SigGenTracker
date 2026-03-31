"""Select platform for Sigenergy Cloud integration — operational mode."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from .const import DOMAIN, OPERATIONAL_MODES

if TYPE_CHECKING:
    from . import SigenEnergyData

_LOGGER = logging.getLogger(__name__)

# Reverse map: name -> mode id
_MODE_NAME_TO_ID: dict[str, int] = {v: k for k, v in OPERATIONAL_MODES.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the operational mode select entity."""
    data: SigenEnergyData = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [SigenEnergyModeSelect(data.coordinator, data.station_id, data.client)]
    )


class SigenEnergyModeSelect(
    CoordinatorEntity[DataUpdateCoordinator[dict[str, Any]]], SelectEntity
):
    """Select entity for the station operational mode."""

    _attr_has_entity_name = True
    _attr_translation_key = "operational_mode"
    _attr_options = list(OPERATIONAL_MODES.values())

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[dict[str, Any]],
        station_id: str,
        client: Any,
    ) -> None:
        super().__init__(coordinator)
        self._station_id = station_id
        self._client = client
        self._attr_unique_id = f"{station_id}_operational_mode"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, station_id)},
            "name": f"Sigenergy {station_id}",
            "manufacturer": "Sigenergy",
        }

    @property
    def current_option(self) -> str | None:
        """Return the current operational mode name."""
        if self.coordinator.data is None:
            return None
        mode_data = self.coordinator.data.get("current_mode", {})
        mode_id = mode_data.get("currentMode")
        if mode_id is None:
            return None
        return OPERATIONAL_MODES.get(int(mode_id))

    async def async_select_option(self, option: str) -> None:
        """Set the operational mode."""
        mode_id = _MODE_NAME_TO_ID.get(option)
        if mode_id is None:
            _LOGGER.error("Unknown operational mode: %s", option)
            return
        await self._client.set_operational_mode(self._station_id, mode_id)
        await self.coordinator.async_request_refresh()
