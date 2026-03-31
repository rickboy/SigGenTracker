"""Tests for the Sigenergy Cloud switch platform (smart loads)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.sigenergy_cloud.api import SigenCloudApiError
from custom_components.sigenergy_cloud.switch import SigenSmartLoadSwitch

# ---------------------------------------------------------------------------
# SigenSmartLoadSwitch entity
# ---------------------------------------------------------------------------


def _make_switch(client=None, is_on=False):
    """Build a SigenSmartLoadSwitch with mocks."""
    coordinator = MagicMock()
    coordinator.data = {}

    entity = SigenSmartLoadSwitch.__new__(SigenSmartLoadSwitch)
    entity.coordinator = coordinator
    entity._client = client or AsyncMock()
    entity._station_id = "STATION001"
    entity._load_path = "/load/pool_pump"
    entity._attr_name = "Pool Pump"
    entity._attr_unique_id = "STATION001_smartload_/load/pool_pump"
    entity._attr_device_info = {
        "identifiers": {("sigenergy_cloud", "STATION001")},
    }
    entity._is_on = is_on
    entity.async_write_ha_state = MagicMock()
    return entity


class TestSigenSmartLoadSwitch:
    """Tests for the smart load switch entity."""

    def test_is_on_default_false(self):
        entity = _make_switch()
        assert entity.is_on is False

    def test_is_on_when_set(self):
        entity = _make_switch(is_on=True)
        assert entity.is_on is True

    @pytest.mark.asyncio
    async def test_turn_on(self):
        client = AsyncMock()
        entity = _make_switch(client=client)

        await entity.async_turn_on()

        client.toggle_smart_load.assert_called_once_with(
            "STATION001", "/load/pool_pump", True
        )
        assert entity._is_on is True
        entity.async_write_ha_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_turn_off(self):
        client = AsyncMock()
        entity = _make_switch(client=client, is_on=True)

        await entity.async_turn_off()

        client.toggle_smart_load.assert_called_once_with(
            "STATION001", "/load/pool_pump", False
        )
        assert entity._is_on is False
        entity.async_write_ha_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_turn_on_api_error(self):
        """API error should be caught, state should not change."""
        client = AsyncMock()
        client.toggle_smart_load = AsyncMock(
            side_effect=SigenCloudApiError("fail")
        )
        entity = _make_switch(client=client, is_on=False)

        await entity.async_turn_on()

        # State should NOT have been updated (error caught before write)
        assert entity._is_on is False
        entity.async_write_ha_state.assert_not_called()

    @pytest.mark.asyncio
    async def test_turn_off_api_error(self):
        """API error should be caught, state should not change."""
        client = AsyncMock()
        client.toggle_smart_load = AsyncMock(
            side_effect=SigenCloudApiError("fail")
        )
        entity = _make_switch(client=client, is_on=True)

        await entity.async_turn_off()

        assert entity._is_on is True
        entity.async_write_ha_state.assert_not_called()

    def test_unique_id(self):
        entity = _make_switch()
        assert entity._attr_unique_id == "STATION001_smartload_/load/pool_pump"

    def test_name(self):
        entity = _make_switch()
        assert entity._attr_name == "Pool Pump"
