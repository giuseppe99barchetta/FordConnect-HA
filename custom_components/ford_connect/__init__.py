"""The Ford Connect integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_entry_oauth2_flow, config_validation as cv
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session

from .api import FordConnectApi
from .const import (
    AUTH_MODE_MANUAL,
    CONF_AUTH_MODE,
    DOMAIN,
    MANUAL_REDIRECT_URI,
    PLATFORMS,
)
from .coordinator import FordConnectCoordinator
from .oauth import async_register_callback_view

type FordConnectConfigEntry = ConfigEntry[FordConnectCoordinator]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Register the OAuth callback before a Ford flow can be started."""
    async_register_callback_view(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: FordConnectConfigEntry) -> bool:
    """Set up Ford Connect from a configuration entry."""
    async_register_callback_view(hass)
    try:
        implementation = (
            await config_entry_oauth2_flow.async_get_config_entry_implementation(
                hass, entry
            )
        )
    except config_entry_oauth2_flow.ImplementationUnavailableError as err:
        raise ConfigEntryNotReady(
            "Ford Connect OAuth is temporarily unavailable"
        ) from err

    oauth_session = OAuth2Session(hass, entry, implementation)
    coordinator = FordConnectCoordinator(
        hass, FordConnectApi(hass, entry, oauth_session)
    )
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: FordConnectConfigEntry
) -> bool:
    """Unload a Ford Connect configuration entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Record the redirect mode for entries created before mode selection existed."""
    if entry.version > 2:
        return False
    if entry.version < 2:
        token = entry.data.get("token", {})
        redirect_uri = (
            token.get("_ford_redirect_uri") if isinstance(token, dict) else None
        )
        auth_mode = (
            AUTH_MODE_MANUAL if redirect_uri == MANUAL_REDIRECT_URI else "automatic"
        )
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_AUTH_MODE: auth_mode}, version=2
        )
    return True
