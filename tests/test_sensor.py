"""Tests for the Sigenergy Cloud sensor platform."""

from __future__ import annotations

from unittest.mock import MagicMock

from custom_components.sigenergy_cloud.sensor import (
    SENSOR_DESCRIPTIONS,
    SigenEnergySensor,
    _get_ef,
)

from .conftest import SAMPLE_ALL_DATA

# ---------------------------------------------------------------------------
# _get_ef helper
# ---------------------------------------------------------------------------


class TestGetEf:
    """Tests for the _get_ef extraction helper."""

    def test_extracts_float(self):
        data = {"energy_flow": {"pvPower": 5230.0}}
        assert _get_ef(data, "pvPower") == 5230.0

    def test_converts_string_to_float(self):
        data = {"energy_flow": {"pvPower": "1234.5"}}
        assert _get_ef(data, "pvPower") == 1234.5

    def test_returns_none_for_missing_key(self):
        data = {"energy_flow": {}}
        assert _get_ef(data, "pvPower") is None

    def test_returns_none_for_missing_energy_flow(self):
        data = {}
        assert _get_ef(data, "pvPower") is None

    def test_returns_none_for_non_numeric(self):
        data = {"energy_flow": {"pvPower": "not-a-number"}}
        assert _get_ef(data, "pvPower") is None

    def test_returns_none_for_none_value(self):
        data = {"energy_flow": {"pvPower": None}}
        assert _get_ef(data, "pvPower") is None

    def test_integer_converted_to_float(self):
        data = {"energy_flow": {"batterySoc": 80}}
        assert _get_ef(data, "batterySoc") == 80.0


# ---------------------------------------------------------------------------
# Sensor descriptions
# ---------------------------------------------------------------------------


class TestSensorDescriptions:
    """Tests for sensor entity descriptions."""

    def test_all_descriptions_have_keys(self):
        for desc in SENSOR_DESCRIPTIONS:
            assert desc.key, f"Description missing key: {desc}"
            assert desc.value_fn is not None

    def test_pv_power_value(self):
        desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "pv_power")
        assert desc.value_fn(SAMPLE_ALL_DATA) == 5230.0

    def test_battery_soc_value(self):
        desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "battery_soc")
        assert desc.value_fn(SAMPLE_ALL_DATA) == 78.5

    def test_battery_soh_value(self):
        desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "battery_soh")
        assert desc.value_fn(SAMPLE_ALL_DATA) == 99.1

    def test_battery_power_value(self):
        desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "battery_power")
        assert desc.value_fn(SAMPLE_ALL_DATA) == -1200.0

    def test_grid_power_value(self):
        desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "grid_power")
        assert desc.value_fn(SAMPLE_ALL_DATA) == 150.0

    def test_load_power_value(self):
        desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "load_power")
        assert desc.value_fn(SAMPLE_ALL_DATA) == 4080.0

    def test_system_online_value(self):
        desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "system_online")
        assert desc.value_fn(SAMPLE_ALL_DATA) is True

    def test_values_with_empty_data(self):
        """All descriptions should handle empty data gracefully."""
        for desc in SENSOR_DESCRIPTIONS:
            val = desc.value_fn({})
            assert val is None, f"{desc.key} did not return None for empty data"


# ---------------------------------------------------------------------------
# SigenEnergySensor entity
# ---------------------------------------------------------------------------


class TestSigenEnergySensor:
    """Tests for the sensor entity class."""

    def _make_sensor(self, coordinator_data=None):
        """Build a SigenEnergySensor with a mock coordinator."""
        coordinator = MagicMock()
        coordinator.data = coordinator_data

        desc = SENSOR_DESCRIPTIONS[0]  # pv_power
        sensor = SigenEnergySensor.__new__(SigenEnergySensor)
        sensor.coordinator = coordinator
        sensor.entity_description = desc
        sensor._station_id = "STATION001"
        sensor._attr_unique_id = f"STATION001_{desc.key}"
        sensor._attr_device_info = {
            "identifiers": {("sigenergy_cloud", "STATION001")},
        }
        return sensor

    def test_native_value_returns_data(self):
        sensor = self._make_sensor(SAMPLE_ALL_DATA)
        assert sensor.native_value == 5230.0

    def test_native_value_none_when_no_data(self):
        sensor = self._make_sensor(None)
        assert sensor.native_value is None

    def test_unique_id_format(self):
        sensor = self._make_sensor(SAMPLE_ALL_DATA)
        assert sensor._attr_unique_id == "STATION001_pv_power"

    def test_device_info(self):
        sensor = self._make_sensor(SAMPLE_ALL_DATA)
        assert ("sigenergy_cloud", "STATION001") in sensor._attr_device_info["identifiers"]
