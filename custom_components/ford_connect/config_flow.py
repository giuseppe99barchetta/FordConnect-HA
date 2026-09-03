"""Config flow for Ford Connect."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.selector import SelectSelector, SelectSelectorConfig

from .const import (
    AUTH_MODE_AUTOMATIC,
    AUTH_MODE_MANUAL,
    CONF_AUTH_MODE,
    DOMAIN,
    NAME,
)
from .oauth import (
    FordConnectExternalUrlError,
    async_parse_manual_callback,
    async_register_callback_view,
)

_LOGGER = logging.getLogger(__name__)


class FordConnectConfigFlow(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Handle a Ford Connect OAuth2 configuration flow."""

    DOMAIN = DOMAIN
    VERSION = 2

    @property
    def logger(self) -> logging.Logger:
        """Return the integration logger required by the OAuth2 base flow."""
        return _LOGGER

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Let the user select Ford's reachable or localhost OAuth flow."""
        async_register_callback_view(self.hass)
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_AUTH_MODE): SelectSelector(
                            SelectSelectorConfig(
                                options=[
                                    {
                                        "value": AUTH_MODE_AUTOMATIC,
                                        "label": "Automatic",
                                    },
                                    {"value": AUTH_MODE_MANUAL, "label": "Manual"},
                                ]
                            )
                        )
                    }
                ),
            )
        self._auth_mode = user_input[CONF_AUTH_MODE]
        if self._auth_mode == AUTH_MODE_MANUAL:
            return await self.async_step_manual_auth()
        return await super().async_step_user(user_input)

    async def async_step_manual_auth(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Show Ford's URL and accept the complete localhost callback URL."""
        if user_input is None:
            implementation = self.flow_impl
            authorize_url = await implementation.async_generate_manual_authorize_url(
                self.flow_id
            )
            return self.async_show_form(
                step_id="manual_auth",
                data_schema=vol.Schema({vol.Required("callback_url"): str}),
                description_placeholders={"authorization_url": authorize_url},
            )
        try:
            external_data = async_parse_manual_callback(
                self.hass, self.flow_id, user_input["callback_url"]
            )
        except (KeyError, TypeError, ValueError) as err:
            return self.async_show_form(
                step_id="manual_auth",
                data_schema=vol.Schema({vol.Required("callback_url"): str}),
                errors={"base": str(err)},
            )
        return await self.async_step_auth(external_data)

    async def async_step_auth(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Return a useful error when Home Assistant has no HTTPS external URL."""
        try:
            return await super().async_step_auth(user_input)
        except FordConnectExternalUrlError:
            return self.async_abort(reason="external_url_required")

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> config_entries.ConfigFlowResult:
        """Start a reauthentication flow for an existing account entry."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Ask for confirmation before opening Ford's authorization page."""
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")
        return await self.async_step_user()

    async def async_oauth_create_entry(
        self, data: dict[str, Any]
    ) -> config_entries.ConfigFlowResult:
        """Update the current entry during reauth, otherwise create an account entry."""
        data = {
            **data,
            CONF_AUTH_MODE: getattr(self, "_auth_mode", AUTH_MODE_AUTOMATIC),
        }
        if self.source == SOURCE_REAUTH:
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(), data_updates=data
            )
        return self.async_create_entry(title=NAME, data=data)
