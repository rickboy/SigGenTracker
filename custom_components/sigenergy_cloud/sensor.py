"""Sensor platform for Sigenergy Cloud integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from .const import DOMAIN

if TYPE_CHECKING:
    from . import SigenEnergyData


@dataclass(frozen=True, kw_only=True)
class SigenEnergySensorDescription(SensorEntityDescription):
    """Describe a Sigenergy Cloud sensor."""

    value_fn: Callable[[dict[str, Any]], float | str | None]


def _get_ef(data: dict[str, Any], key: str) -> float | None:
    """Extract a value from the energy_flow sub-dict."""
    val = data.get("energy_flow", {}).get(key)
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


SENSOR_DESCRIPTIONS: tuple[SigenEnergySensorDescription, ...] = (
    SigenEnergySensorDescription(
        key="pv_power",
        translation_key="pv_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: _get_ef(d, "pvPower"),
    ),
    SigenEnergySensorDescription(
        key="battery_soc",
        translation_key="battery_soc",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: _get_ef(d, "batterySoc"),
    ),
    SigenEnergySensorDescription(
        key="battery_soh",
        translation_key="battery_soh",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: _get_ef(d, "batterySoh"),
    ),
    SigenEnergySensorDescription(
        key="battery_power",
        translation_key="battery_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: _get_ef(d, "batteryPower"),
    ),
    SigenEnergySensorDescription(
        key="grid_power",
        translation_key="grid_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: _get_ef(d, "gridPower"),
    ),
    SigenEnergySensorDescription(
        key="load_power",
        translation_key="load_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: _get_ef(d, "loadPower"),
    ),
    SigenEnergySensorDescription(
        key="system_online",
        translation_key="system_online",
        value_fn=lambda d: d.get("energy_flow", {}).get("online"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Sigenergy Cloud sensor entities."""
    data: SigenEnergyData = hass.data[DOMAIN][entry.entry_id]
    coordinator = data.coordinator
    station_id = data.station_id

    entities = [
        SigenEnergySensor(coordinator, description, station_id)
        for description in SENSOR_DESCRIPTIONS
    ]
    async_add_entities(entities)


class SigenEnergySensor(
    CoordinatorEntity[DataUpdateCoordinator[dict[str, Any]]], SensorEntity
):
    """Representation of a Sigenergy Cloud sensor."""

    entity_description: SigenEnergySensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[dict[str, Any]],
        description: SigenEnergySensorDescription,
        station_id: str,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._station_id = station_id
        self._attr_unique_id = f"{station_id}_{description.key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, station_id)},
            "name": f"Sigenergy {station_id}",
            "manufacturer": "Sigenergy",
        }

    @property
    def native_value(self) -> float | str | None:
        """Return the sensor value."""
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)
