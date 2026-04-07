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
from homeassistant.const import PERCENTAGE, UnitOfIrradiance, UnitOfSpeed, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from .const import DOMAIN

if TYPE_CHECKING:
    from . import SigenEnergyData


WEATHER_DEVICE_CLASS_TEMPERATURE = getattr(SensorDeviceClass, "TEMPERATURE", None)
WEATHER_DEVICE_CLASS_HUMIDITY = getattr(SensorDeviceClass, "HUMIDITY", None)
WEATHER_DEVICE_CLASS_WIND_SPEED = getattr(SensorDeviceClass, "WIND_SPEED", None)
WEATHER_DEVICE_CLASS_IRRADIANCE = getattr(SensorDeviceClass, "IRRADIANCE", None)


@dataclass(frozen=True, kw_only=True)
class SigenEnergySensorDescription(SensorEntityDescription):
    """Describe a Sigenergy Cloud sensor."""

    value_fn: Callable[[dict[str, Any]], float | str | None]


def _deep_find(node: Any, *keys: str) -> Any | None:
    """Return the first value found for any key within nested dict/list payloads."""
    lowered = {key.lower() for key in keys}

    if isinstance(node, dict):
        for key, value in node.items():
            if key.lower() in lowered:
                return value
        for value in node.values():
            found = _deep_find(value, *keys)
            if found is not None:
                return found
    elif isinstance(node, list):
        for item in node:
            found = _deep_find(item, *keys)
            if found is not None:
                return found

    return None


def _as_float(value: Any) -> float | None:
    """Convert a value to float, returning None on invalid data."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_text(value: Any) -> str | None:
    """Convert a value to a display-friendly string."""
    if value is None:
        return None
    if isinstance(value, bool):
        return "on" if value else "off"
    return str(value)


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


def _get_weather_metric(data: dict[str, Any], *keys: str) -> float | None:
    """Extract numeric values from the weather payload."""
    return _as_float(_deep_find(data.get("weather", {}), *keys))


def _get_weather_text(data: dict[str, Any], *keys: str) -> str | None:
    """Extract text-like values from the weather payload."""
    return _as_text(_deep_find(data.get("weather", {}), *keys))


def _get_energy_stats_metric(data: dict[str, Any], *keys: str) -> float | None:
    """Extract numeric values from energy stats payload."""
    return _as_float(_deep_find(data.get("energy_stats", {}), *keys))


def _get_custom_energy_stats_metric(data: dict[str, Any], *keys: str) -> float | None:
    """Extract numeric values from custom energy stats payload."""
    return _as_float(_deep_find(data.get("custom_energy_stats", {}), *keys))


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
    SigenEnergySensorDescription(
        key="on_off_grid_status",
        translation_key="on_off_grid_status",
        value_fn=lambda d: _as_text(_get_ef(d, "onOffGridStatus")),
    ),
    SigenEnergySensorDescription(
        key="weather_temperature",
        translation_key="weather_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=WEATHER_DEVICE_CLASS_TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: _get_weather_metric(d, "temperature", "temp"),
    ),
    SigenEnergySensorDescription(
        key="weather_humidity",
        translation_key="weather_humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=WEATHER_DEVICE_CLASS_HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: _get_weather_metric(d, "humidity"),
    ),
    SigenEnergySensorDescription(
        key="weather_condition",
        translation_key="weather_condition",
        value_fn=lambda d: _get_weather_text(d, "condition", "weather", "weatherDesc", "weatherCode"),
    ),
    SigenEnergySensorDescription(
        key="weather_wind_speed",
        translation_key="weather_wind_speed",
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        device_class=WEATHER_DEVICE_CLASS_WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: _get_weather_metric(d, "windSpeed", "wind_speed"),
    ),
    SigenEnergySensorDescription(
        key="weather_solar_irradiance",
        translation_key="weather_solar_irradiance",
        native_unit_of_measurement=UnitOfIrradiance.WATTS_PER_SQUARE_METER,
        device_class=WEATHER_DEVICE_CLASS_IRRADIANCE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: _get_weather_metric(d, "solarIrradiance", "irradiance"),
    ),
    SigenEnergySensorDescription(
        key="daily_pv_energy",
        translation_key="daily_pv_energy",
        native_unit_of_measurement="kWh",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: _get_energy_stats_metric(d, "dailyPvEnergy", "pvEnergy", "pvDayNrg"),
    ),
    SigenEnergySensorDescription(
        key="daily_import_energy",
        translation_key="daily_import_energy",
        native_unit_of_measurement="kWh",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: _get_energy_stats_metric(d, "dailyImportEnergy", "importEnergy", "gridImportEnergy"),
    ),
    SigenEnergySensorDescription(
        key="daily_export_energy",
        translation_key="daily_export_energy",
        native_unit_of_measurement="kWh",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: _get_energy_stats_metric(d, "dailyExportEnergy", "exportEnergy", "gridExportEnergy"),
    ),
    SigenEnergySensorDescription(
        key="daily_load_energy",
        translation_key="daily_load_energy",
        native_unit_of_measurement="kWh",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: _get_energy_stats_metric(d, "dailyLoadEnergy", "loadEnergy"),
    ),
    SigenEnergySensorDescription(
        key="daily_battery_charge_energy",
        translation_key="daily_battery_charge_energy",
        native_unit_of_measurement="kWh",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: _get_energy_stats_metric(
            d,
            "dailyBatteryChargeEnergy",
            "batteryChargeEnergy",
            "chargeEnergy",
        ),
    ),
    SigenEnergySensorDescription(
        key="daily_battery_discharge_energy",
        translation_key="daily_battery_discharge_energy",
        native_unit_of_measurement="kWh",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: _get_energy_stats_metric(
            d,
            "dailyBatteryDischargeEnergy",
            "batteryDischargeEnergy",
            "dischargeEnergy",
        ),
    ),
    SigenEnergySensorDescription(
        key="custom_daily_import_energy",
        translation_key="custom_daily_import_energy",
        native_unit_of_measurement="kWh",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: _get_custom_energy_stats_metric(
            d,
            "dailyImportEnergy",
            "importEnergy",
            "gridImportEnergy",
        ),
    ),
    SigenEnergySensorDescription(
        key="custom_daily_export_energy",
        translation_key="custom_daily_export_energy",
        native_unit_of_measurement="kWh",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: _get_custom_energy_stats_metric(
            d,
            "dailyExportEnergy",
            "exportEnergy",
            "gridExportEnergy",
        ),
    ),
    SigenEnergySensorDescription(
        key="custom_daily_load_energy",
        translation_key="custom_daily_load_energy",
        native_unit_of_measurement="kWh",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: _get_custom_energy_stats_metric(d, "dailyLoadEnergy", "loadEnergy"),
    ),
    SigenEnergySensorDescription(
        key="custom_daily_pv_energy",
        translation_key="custom_daily_pv_energy",
        native_unit_of_measurement="kWh",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: _get_custom_energy_stats_metric(d, "dailyPvEnergy", "pvEnergy", "pvDayNrg"),
    ),
    SigenEnergySensorDescription(
        key="custom_daily_battery_charge_energy",
        translation_key="custom_daily_battery_charge_energy",
        native_unit_of_measurement="kWh",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: _get_custom_energy_stats_metric(
            d,
            "dailyBatteryChargeEnergy",
            "batteryChargeEnergy",
            "chargeEnergy",
        ),
    ),
    SigenEnergySensorDescription(
        key="custom_daily_battery_discharge_energy",
        translation_key="custom_daily_battery_discharge_energy",
        native_unit_of_measurement="kWh",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: _get_custom_energy_stats_metric(
            d,
            "dailyBatteryDischargeEnergy",
            "batteryDischargeEnergy",
            "dischargeEnergy",
        ),
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
    entities.append(SigenEnergyRawDiagnosticSensor(coordinator, station_id, station_info))
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


class SigenEnergyRawDiagnosticSensor(
    CoordinatorEntity[DataUpdateCoordinator[dict[str, Any]]], SensorEntity
):
    """Diagnostic sensor exposing raw payloads and unmapped keys."""

    _attr_has_entity_name = True
    _attr_translation_key = "raw_payload_diagnostic"
    _attr_entity_category = "diagnostic"

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[dict[str, Any]],
        station_id: str,
        station_info: dict[str, Any],
    ) -> None:
        super().__init__(coordinator)
        self._station_id = station_id
        self._station_info = station_info
        self._attr_unique_id = f"{station_id}_raw_payload_diagnostic"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, station_id)},
            "name": f"Sigenergy {station_id}",
            "manufacturer": "Sigenergy",
        }

    @property
    def native_value(self) -> str | None:
        """Return diagnostic status."""
        if self.coordinator.data is None:
            return None
        return "available"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose raw payloads and unmapped keys."""
        data = self.coordinator.data or {}
        station_info = data.get("station_info", self._station_info)
        energy_flow = data.get("energy_flow", {})
        current_mode = data.get("current_mode", {})
        weather = data.get("weather", {})
        energy_stats = data.get("energy_stats", {})
        custom_energy_stats = data.get("custom_energy_stats", {})

        mapped_station_keys = {"pvCapacity", "batteryCapacity"}
        mapped_energy_flow_keys = {
            "pvPower",
            "batterySoc",
            "batterySoh",
            "batteryPower",
            "buySellPower",
            "gridPower",
            "loadPower",
            "online",
            "onOffGridStatus",
        }
        mapped_weather_keys = {
            "temperature",
            "temp",
            "humidity",
            "condition",
            "weather",
            "weatherDesc",
            "weatherCode",
            "windSpeed",
            "wind_speed",
            "solarIrradiance",
            "irradiance",
        }
        mapped_energy_stats_keys = {
            "dailyImportEnergy",
            "importEnergy",
            "gridImportEnergy",
            "dailyExportEnergy",
            "exportEnergy",
            "gridExportEnergy",
            "dailyLoadEnergy",
            "loadEnergy",
            "dailyPvEnergy",
            "pvEnergy",
            "pvDayNrg",
            "dailyBatteryChargeEnergy",
            "batteryChargeEnergy",
            "chargeEnergy",
            "dailyBatteryDischargeEnergy",
            "batteryDischargeEnergy",
            "dischargeEnergy",
        }

        def _unmapped(payload: Any, mapped_keys: set[str]) -> dict[str, Any]:
            if not isinstance(payload, dict):
                return {}
            return {k: v for k, v in payload.items() if k not in mapped_keys}

        return {
            "station_info_raw": station_info,
            "energy_flow_raw": energy_flow,
            "current_mode_raw": current_mode,
            "weather_raw": weather,
            "energy_stats_raw": energy_stats,
            "custom_energy_stats_raw": custom_energy_stats,
            "unmapped_station_info": _unmapped(station_info, mapped_station_keys),
            "unmapped_energy_flow": _unmapped(energy_flow, mapped_energy_flow_keys),
            "unmapped_weather": _unmapped(weather, mapped_weather_keys),
            "unmapped_energy_stats": _unmapped(energy_stats, mapped_energy_stats_keys),
            "unmapped_custom_energy_stats": _unmapped(custom_energy_stats, mapped_energy_stats_keys),
        }
