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
from homeassistant.const import PERCENTAGE
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


def _get_ef_any(data: dict[str, Any], *keys: str) -> float | None:
    """Extract the first available numeric value from energy_flow using fallback keys."""
    for key in keys:
        value = _get_ef(data, key)
        if value is not None:
            return value
    return None


def _get_ef_kw(data: dict[str, Any], key: str) -> float | None:
    """Extract a power value already reported in kW by the API."""
    return _get_ef(data, key)


def _get_station_metric(data: dict[str, Any], key: str) -> float | None:
    """Extract a numeric value from station_info."""
    station = data.get("station_info", {})
    if not isinstance(station, dict):
        return None
    value = station.get(key)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


SENSOR_DESCRIPTIONS: tuple[SigenEnergySensorDescription, ...] = (
    SigenEnergySensorDescription(
        key="pv_power",
        translation_key="pv_power",
        native_unit_of_measurement="kW",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: _get_ef_kw(d, "pvPower"),
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
        native_unit_of_measurement="kW",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: _get_ef_kw(d, "batteryPower"),
    ),
    SigenEnergySensorDescription(
        key="grid_power",
        translation_key="grid_power",
        native_unit_of_measurement="kW",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: _get_ef_any(d, "buySellPower", "gridPower"),
    ),
    SigenEnergySensorDescription(
        key="load_power",
        translation_key="load_power",
        native_unit_of_measurement="kW",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: _get_ef_kw(d, "loadPower"),
    ),
    SigenEnergySensorDescription(
        key="system_online",
        translation_key="system_online",
        value_fn=lambda d: d.get("energy_flow", {}).get("online"),
    ),
    SigenEnergySensorDescription(
        key="pv_capacity",
        translation_key="pv_capacity",
        native_unit_of_measurement="kW",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: _get_station_metric(d, "pvCapacity"),
    ),
    SigenEnergySensorDescription(
        key="battery_capacity",
        translation_key="battery_capacity",
        native_unit_of_measurement="kWh",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: _get_station_metric(d, "batteryCapacity"),
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
    station_info = data.station_info

    entities = [
        SigenEnergySensor(coordinator, description, station_id, station_info)
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
        station_info: dict[str, Any],
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._station_id = station_id
        self._station_info = station_info
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
        merged_data = dict(self.coordinator.data)
        merged_data.setdefault("station_info", self._station_info)
        return self.entity_description.value_fn(merged_data)
