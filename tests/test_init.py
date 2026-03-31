"""Tests for the Sigenergy Cloud __init__ module (coordinator, setup/unload)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.sigenergy_cloud.api import (
    SigenCloudApiError,
    SigenCloudAuthError,
)
from custom_components.sigenergy_cloud.const import CONF_REGION, DEFAULT_REGION, DOMAIN

from .conftest import SAMPLE_ALL_DATA, SAMPLE_STATION

# ---------------------------------------------------------------------------
# SigenEnergyDataUpdateCoordinator
# ---------------------------------------------------------------------------


class TestCoordinator:
    """Tests for the data update coordinator."""

    @pytest.mark.asyncio
    async def test_update_success(self):
        """Coordinator should return get_all_data result."""
        from custom_components.sigenergy_cloud import SigenEnergyDataUpdateCoordinator

        client = AsyncMock()
        client.get_all_data = AsyncMock(return_value=SAMPLE_ALL_DATA)

        coordinator = SigenEnergyDataUpdateCoordinator.__new__(
            SigenEnergyDataUpdateCoordinator
        )
        coordinator.client = client
        coordinator.station_id = "STATION001"

        result = await coordinator._async_update_data()

        assert result == SAMPLE_ALL_DATA
        client.get_all_data.assert_called_once_with("STATION001")

    @pytest.mark.asyncio
    async def test_update_auth_error(self):
        """Auth errors should raise ConfigEntryAuthFailed."""
        from custom_components.sigenergy_cloud import SigenEnergyDataUpdateCoordinator

        # We can't import ConfigEntryAuthFailed without HA, so we check exception type
        client = AsyncMock()
        client.get_all_data = AsyncMock(
            side_effect=SigenCloudAuthError("token expired")
        )

        coordinator = SigenEnergyDataUpdateCoordinator.__new__(
            SigenEnergyDataUpdateCoordinator
        )
        coordinator.client = client
        coordinator.station_id = "STATION001"

        # ConfigEntryAuthFailed is from HA; we'll catch its parent Exception
        with pytest.raises(Exception, match="token expired"):
            await coordinator._async_update_data()

    @pytest.mark.asyncio
    async def test_update_api_error(self):
        """API errors should raise UpdateFailed."""
        from custom_components.sigenergy_cloud import SigenEnergyDataUpdateCoordinator

        client = AsyncMock()
        client.get_all_data = AsyncMock(
            side_effect=SigenCloudApiError("connection lost")
        )

        coordinator = SigenEnergyDataUpdateCoordinator.__new__(
            SigenEnergyDataUpdateCoordinator
        )
        coordinator.client = client
        coordinator.station_id = "STATION001"

        with pytest.raises(Exception, match="Error communicating with API"):
            await coordinator._async_update_data()


# ---------------------------------------------------------------------------
# SigenEnergyData
# ---------------------------------------------------------------------------


class TestSigenEnergyData:
    """Tests for the runtime data container."""

    def test_attributes(self):
        from custom_components.sigenergy_cloud import SigenEnergyData

        client = MagicMock()
        coordinator = MagicMock()

        data = SigenEnergyData(
            client=client,
            coordinator=coordinator,
            station_id="STATION001",
            station_info=SAMPLE_STATION,
        )

        assert data.client is client
        assert data.coordinator is coordinator
        assert data.station_id == "STATION001"
        assert data.station_info == SAMPLE_STATION


# ---------------------------------------------------------------------------
# async_setup_entry / async_unload_entry
# ---------------------------------------------------------------------------


class TestSetupEntry:
    """Tests for the entry setup and teardown."""

    @pytest.mark.asyncio
    @patch("custom_components.sigenergy_cloud.async_get_clientsession")
    @patch("custom_components.sigenergy_cloud.SigenCloudApiClient")
    @patch("custom_components.sigenergy_cloud.SigenEnergyDataUpdateCoordinator")
    async def test_setup_entry_success(
        self, MockCoordinator, MockClient, mock_get_session
    ):
        """Successful setup should store data and forward platforms."""
        from custom_components.sigenergy_cloud import async_setup_entry

        mock_get_session.return_value = MagicMock()

        client_instance = AsyncMock()
        client_instance.authenticate = AsyncMock()
        client_instance.get_station = AsyncMock(return_value=SAMPLE_STATION)
        MockClient.return_value = client_instance

        coord_instance = AsyncMock()
        coord_instance.async_config_entry_first_refresh = AsyncMock()
        MockCoordinator.return_value = coord_instance

        hass = MagicMock()
        hass.data = {}
        hass.config_entries.async_forward_entry_setups = AsyncMock()

        entry = MagicMock()
        entry.data = {
            "username": "user@test.com",
            "password": "pass",
            CONF_REGION: DEFAULT_REGION,
        }
        entry.entry_id = "test-entry-id"

        result = await async_setup_entry(hass, entry)

        assert result is True
        assert DOMAIN in hass.data
        assert "test-entry-id" in hass.data[DOMAIN]

        stored = hass.data[DOMAIN]["test-entry-id"]
        assert stored.station_id == "STATION001"
        assert stored.client is client_instance

        hass.config_entries.async_forward_entry_setups.assert_called_once()

    @pytest.mark.asyncio
    @patch("custom_components.sigenergy_cloud.async_get_clientsession")
    @patch("custom_components.sigenergy_cloud.SigenCloudApiClient")
    async def test_setup_entry_auth_failure(self, MockClient, mock_get_session):
        """Auth failure during setup should raise ConfigEntryAuthFailed."""
        from custom_components.sigenergy_cloud import async_setup_entry

        mock_get_session.return_value = MagicMock()

        client_instance = AsyncMock()
        client_instance.authenticate = AsyncMock(
            side_effect=SigenCloudAuthError("bad creds")
        )
        MockClient.return_value = client_instance

        hass = MagicMock()
        entry = MagicMock()
        entry.data = {
            "username": "u",
            "password": "p",
            CONF_REGION: DEFAULT_REGION,
        }

        with pytest.raises(Exception, match="bad creds"):
            await async_setup_entry(hass, entry)

    @pytest.mark.asyncio
    @patch("custom_components.sigenergy_cloud.async_get_clientsession")
    @patch("custom_components.sigenergy_cloud.SigenCloudApiClient")
    async def test_setup_entry_no_station(self, MockClient, mock_get_session):
        """Missing stationId should raise."""
        from custom_components.sigenergy_cloud import async_setup_entry

        mock_get_session.return_value = MagicMock()

        client_instance = AsyncMock()
        client_instance.authenticate = AsyncMock()
        client_instance.get_station = AsyncMock(return_value={})
        MockClient.return_value = client_instance

        hass = MagicMock()
        entry = MagicMock()
        entry.data = {"username": "u", "password": "p", CONF_REGION: DEFAULT_REGION}

        with pytest.raises(Exception, match="No station found"):
            await async_setup_entry(hass, entry)

    @pytest.mark.asyncio
    async def test_unload_entry(self):
        """Unloading should clear hass.data and unload platforms."""
        from custom_components.sigenergy_cloud import async_unload_entry

        hass = MagicMock()
        hass.data = {DOMAIN: {"entry-1": MagicMock()}}
        hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)

        entry = MagicMock()
        entry.entry_id = "entry-1"

        result = await async_unload_entry(hass, entry)

        assert result is True
        assert "entry-1" not in hass.data[DOMAIN]

    @pytest.mark.asyncio
    async def test_unload_entry_failure(self):
        """Failed unload should not remove data."""
        from custom_components.sigenergy_cloud import async_unload_entry

        hass = MagicMock()
        hass.data = {DOMAIN: {"entry-1": MagicMock()}}
        hass.config_entries.async_unload_platforms = AsyncMock(return_value=False)

        entry = MagicMock()
        entry.entry_id = "entry-1"

        result = await async_unload_entry(hass, entry)

        assert result is False
        assert "entry-1" in hass.data[DOMAIN]
