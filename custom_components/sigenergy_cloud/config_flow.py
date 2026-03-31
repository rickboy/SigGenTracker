"""Config flow for Sigenergy Cloud integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SigenCloudApiClient, SigenCloudApiError, SigenCloudAuthError
from .const import CONF_REGION, DEFAULT_REGION, DOMAIN, REGIONS

_LOGGER = logging.getLogger(__name__)


class SigenEnergyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sigenergy Cloud."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step — collect credentials and region."""
        errors: dict[str, str] = {}

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            client = SigenCloudApiClient(
                session=session,
                username=user_input[CONF_USERNAME],
                password=user_input[CONF_PASSWORD],
                region=user_input.get(CONF_REGION, DEFAULT_REGION),
            )

            try:
                await client.authenticate()
                station = await client.get_station()
            except SigenCloudAuthError:
                errors["base"] = "invalid_auth"
            except SigenCloudApiError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception during setup")
                errors["base"] = "unknown"
            else:
                station_id = str(station.get("stationId", ""))
                await self.async_set_unique_id(station_id)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"Sigenergy ({station_id})",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Optional(CONF_REGION, default=DEFAULT_REGION): vol.In(REGIONS),
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> FlowResult:
        """Handle re-authentication when tokens expire."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle re-auth confirmation with new credentials."""
        errors: dict[str, str] = {}

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            reauth_entry = self._get_reauth_entry()
            client = SigenCloudApiClient(
                session=session,
                username=user_input[CONF_USERNAME],
                password=user_input[CONF_PASSWORD],
                region=reauth_entry.data.get(CONF_REGION, DEFAULT_REGION),
            )

            try:
                await client.authenticate()
            except SigenCloudAuthError:
                errors["base"] = "invalid_auth"
            except SigenCloudApiError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception during reauth")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data={
                        **reauth_entry.data,
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )
