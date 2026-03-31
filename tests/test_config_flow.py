"""Tests for the Sigenergy Cloud config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# We mock HA internals, so import the module we're testing
from custom_components.sigenergy_cloud.config_flow import SigenEnergyConfigFlow
from custom_components.sigenergy_cloud.const import (
    DEFAULT_REGION,
)

from .conftest import SAMPLE_STATION

VALID_USER_INPUT = {
    "username": "user@example.com",
    "password": "secret123",
    "region": DEFAULT_REGION,
}


def _make_flow(hass=None):
    """Instantiate a config flow with a mock hass."""
    flow = SigenEnergyConfigFlow.__new__(SigenEnergyConfigFlow)
    flow.hass = hass or MagicMock()
    flow.context = {}
    return flow


class TestUserStep:
    """Tests for async_step_user."""

    @pytest.mark.asyncio
    @patch("custom_components.sigenergy_cloud.config_flow.async_get_clientsession")
    @patch("custom_components.sigenergy_cloud.config_flow.SigenCloudApiClient")
    async def test_successful_setup(self, MockClient, mock_get_session):
        """Valid credentials should create an entry."""
        mock_get_session.return_value = MagicMock()

        client_instance = AsyncMock()
        client_instance.authenticate = AsyncMock()
        client_instance.get_station = AsyncMock(return_value=SAMPLE_STATION)
        MockClient.return_value = client_instance

        flow = _make_flow()
        flow.async_set_unique_id = AsyncMock()
        flow._abort_if_unique_id_configured = MagicMock()
        flow.async_create_entry = MagicMock(return_value={"type": "create_entry"})

        await flow.async_step_user(VALID_USER_INPUT)

        client_instance.authenticate.assert_called_once()
        client_instance.get_station.assert_called_once()
        flow.async_create_entry.assert_called_once()
        assert flow.async_create_entry.call_args[1]["title"] == "Sigenergy (STATION001)"

    @pytest.mark.asyncio
    @patch("custom_components.sigenergy_cloud.config_flow.async_get_clientsession")
    @patch("custom_components.sigenergy_cloud.config_flow.SigenCloudApiClient")
    async def test_invalid_auth(self, MockClient, mock_get_session):
        """Wrong credentials should show invalid_auth error."""
        from custom_components.sigenergy_cloud.api import SigenCloudAuthError

        mock_get_session.return_value = MagicMock()

        client_instance = AsyncMock()
        client_instance.authenticate = AsyncMock(
            side_effect=SigenCloudAuthError("bad creds")
        )
        MockClient.return_value = client_instance

        flow = _make_flow()
        flow.async_show_form = MagicMock(return_value={"type": "form"})

        await flow.async_step_user(VALID_USER_INPUT)

        flow.async_show_form.assert_called_once()
        call_kwargs = flow.async_show_form.call_args[1]
        assert call_kwargs["errors"] == {"base": "invalid_auth"}

    @pytest.mark.asyncio
    @patch("custom_components.sigenergy_cloud.config_flow.async_get_clientsession")
    @patch("custom_components.sigenergy_cloud.config_flow.SigenCloudApiClient")
    async def test_cannot_connect(self, MockClient, mock_get_session):
        """Connection error should show cannot_connect."""
        from custom_components.sigenergy_cloud.api import SigenCloudApiError

        mock_get_session.return_value = MagicMock()

        client_instance = AsyncMock()
        client_instance.authenticate = AsyncMock(
            side_effect=SigenCloudApiError("timeout")
        )
        MockClient.return_value = client_instance

        flow = _make_flow()
        flow.async_show_form = MagicMock(return_value={"type": "form"})

        await flow.async_step_user(VALID_USER_INPUT)

        call_kwargs = flow.async_show_form.call_args[1]
        assert call_kwargs["errors"] == {"base": "cannot_connect"}

    @pytest.mark.asyncio
    @patch("custom_components.sigenergy_cloud.config_flow.async_get_clientsession")
    @patch("custom_components.sigenergy_cloud.config_flow.SigenCloudApiClient")
    async def test_unexpected_exception(self, MockClient, mock_get_session):
        """Unexpected errors should show unknown."""
        mock_get_session.return_value = MagicMock()

        client_instance = AsyncMock()
        client_instance.authenticate = AsyncMock(side_effect=RuntimeError("boom"))
        MockClient.return_value = client_instance

        flow = _make_flow()
        flow.async_show_form = MagicMock(return_value={"type": "form"})

        await flow.async_step_user(VALID_USER_INPUT)

        call_kwargs = flow.async_show_form.call_args[1]
        assert call_kwargs["errors"] == {"base": "unknown"}

    @pytest.mark.asyncio
    async def test_show_form_when_no_input(self):
        """No user input should show the form."""
        flow = _make_flow()
        flow.async_show_form = MagicMock(return_value={"type": "form"})

        await flow.async_step_user(None)

        flow.async_show_form.assert_called_once()
        call_kwargs = flow.async_show_form.call_args[1]
        assert call_kwargs["step_id"] == "user"
        assert call_kwargs["errors"] == {}


class TestReauthStep:
    """Tests for async_step_reauth / async_step_reauth_confirm."""

    @pytest.mark.asyncio
    @patch("custom_components.sigenergy_cloud.config_flow.async_get_clientsession")
    @patch("custom_components.sigenergy_cloud.config_flow.SigenCloudApiClient")
    async def test_reauth_success(self, MockClient, mock_get_session):
        """Successful reauth should update and reload."""
        mock_get_session.return_value = MagicMock()

        client_instance = AsyncMock()
        client_instance.authenticate = AsyncMock()
        MockClient.return_value = client_instance

        flow = _make_flow()
        reauth_entry = MagicMock()
        reauth_entry.data = {
            "username": "old@test.com",
            "password": "old",
            "region": DEFAULT_REGION,
        }
        flow._get_reauth_entry = MagicMock(return_value=reauth_entry)
        flow.async_update_reload_and_abort = MagicMock(
            return_value={"type": "abort", "reason": "reauth_successful"}
        )

        await flow.async_step_reauth_confirm(
            {"username": "new@test.com", "password": "newpass"}
        )

        client_instance.authenticate.assert_called_once()
        flow.async_update_reload_and_abort.assert_called_once()

    @pytest.mark.asyncio
    @patch("custom_components.sigenergy_cloud.config_flow.async_get_clientsession")
    @patch("custom_components.sigenergy_cloud.config_flow.SigenCloudApiClient")
    async def test_reauth_invalid_auth(self, MockClient, mock_get_session):
        """Bad credentials during reauth should show error."""
        from custom_components.sigenergy_cloud.api import SigenCloudAuthError

        mock_get_session.return_value = MagicMock()

        client_instance = AsyncMock()
        client_instance.authenticate = AsyncMock(
            side_effect=SigenCloudAuthError("bad")
        )
        MockClient.return_value = client_instance

        flow = _make_flow()
        reauth_entry = MagicMock()
        reauth_entry.data = {"region": DEFAULT_REGION}
        flow._get_reauth_entry = MagicMock(return_value=reauth_entry)
        flow.async_show_form = MagicMock(return_value={"type": "form"})

        await flow.async_step_reauth_confirm(
            {"username": "u", "password": "p"}
        )

        call_kwargs = flow.async_show_form.call_args[1]
        assert call_kwargs["errors"] == {"base": "invalid_auth"}

    @pytest.mark.asyncio
    async def test_reauth_show_form_no_input(self):
        """No input should show the reauth form."""
        flow = _make_flow()
        flow.async_show_form = MagicMock(return_value={"type": "form"})

        await flow.async_step_reauth_confirm(None)

        flow.async_show_form.assert_called_once()
        call_kwargs = flow.async_show_form.call_args[1]
        assert call_kwargs["step_id"] == "reauth_confirm"
