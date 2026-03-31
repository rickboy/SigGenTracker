"""Tests for the Sigenergy Cloud select platform (operational mode)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.sigenergy_cloud.const import OPERATIONAL_MODES
from custom_components.sigenergy_cloud.select import (
    _MODE_NAME_TO_ID,
    SigenEnergyModeSelect,
)

from .conftest import SAMPLE_ALL_DATA

# ---------------------------------------------------------------------------
# Mode name <-> ID mapping
# ---------------------------------------------------------------------------


class TestModeMapping:
    """Tests for the mode name/ID reverse lookup."""

    def test_reverse_map_contains_all_modes(self):
        for mode_id, name in OPERATIONAL_MODES.items():
            assert _MODE_NAME_TO_ID[name] == mode_id

    def test_round_trip(self):
        for mode_id, _name in OPERATIONAL_MODES.items():
            assert _MODE_NAME_TO_ID[OPERATIONAL_MODES[mode_id]] == mode_id


# ---------------------------------------------------------------------------
# SigenEnergyModeSelect entity
# ---------------------------------------------------------------------------


def _make_select(coordinator_data=None, client=None):
    """Build a SigenEnergyModeSelect with mocks."""
    coordinator = MagicMock()
    coordinator.data = coordinator_data
    coordinator.async_request_refresh = AsyncMock()

    entity = SigenEnergyModeSelect.__new__(SigenEnergyModeSelect)
    entity.coordinator = coordinator
    entity._station_id = "STATION001"
    entity._client = client or AsyncMock()
    entity._attr_unique_id = "STATION001_operational_mode"
    entity._attr_options = list(OPERATIONAL_MODES.values())
    entity._attr_device_info = {
        "identifiers": {("sigenergy_cloud", "STATION001")},
    }
    return entity


class TestSigenEnergyModeSelect:
    """Tests for the mode select entity."""

    def test_current_option_msc(self):
        entity = _make_select(SAMPLE_ALL_DATA)
        assert entity.current_option == "Maximum Self-Consumption"

    def test_current_option_ffg(self):
        data = {"current_mode": {"currentMode": 5}}
        entity = _make_select(data)
        assert entity.current_option == "Fully Feed-in to Grid"

    def test_current_option_vpp(self):
        data = {"current_mode": {"currentMode": 6}}
        entity = _make_select(data)
        assert entity.current_option == "VPP"

    def test_current_option_tou(self):
        data = {"current_mode": {"currentMode": 9}}
        entity = _make_select(data)
        assert entity.current_option == "Time of Use"

    def test_current_option_none_when_no_data(self):
        entity = _make_select(None)
        assert entity.current_option is None

    def test_current_option_none_when_no_mode(self):
        entity = _make_select({"current_mode": {}})
        assert entity.current_option is None

    def test_current_option_unknown_mode_id(self):
        data = {"current_mode": {"currentMode": 999}}
        entity = _make_select(data)
        assert entity.current_option is None

    @pytest.mark.asyncio
    async def test_select_option_calls_api(self):
        client = AsyncMock()
        entity = _make_select(SAMPLE_ALL_DATA, client=client)

        await entity.async_select_option("Fully Feed-in to Grid")

        client.set_operational_mode.assert_called_once_with("STATION001", 5)
        entity.coordinator.async_request_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_select_option_unknown_does_not_call_api(self):
        client = AsyncMock()
        entity = _make_select(SAMPLE_ALL_DATA, client=client)

        await entity.async_select_option("Nonexistent Mode")

        client.set_operational_mode.assert_not_called()

    def test_unique_id(self):
        entity = _make_select(SAMPLE_ALL_DATA)
        assert entity._attr_unique_id == "STATION001_operational_mode"

    def test_options_list(self):
        entity = _make_select(SAMPLE_ALL_DATA)
        assert "Maximum Self-Consumption" in entity._attr_options
        assert "Fully Feed-in to Grid" in entity._attr_options
        assert "VPP" in entity._attr_options
        assert "Time of Use" in entity._attr_options
