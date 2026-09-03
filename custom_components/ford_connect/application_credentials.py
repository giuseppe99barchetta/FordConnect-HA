"""Ford Connect OAuth application credential support."""

from __future__ import annotations

from typing import Any

from homeassistant.components.application_credentials import (
    AuthorizationServer,
    ClientCredential,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import (
    AbstractOAuth2Implementation,
    LocalOAuth2Implementation,
)

from .const import AUTHORIZE_URL, OAUTH_AUTHORIZE_SCOPE, TOKEN_URL


class FordConnectOAuth2Implementation(LocalOAuth2Implementation):
    """OAuth2 implementation for Ford's B2C authorization server."""

    @property
    def extra_authorize_data(self) -> dict[str, str]:
        """Return the documented Ford authorization scope."""
        return {"scope": OAUTH_AUTHORIZE_SCOPE}

    @property
    def extra_token_resolve_data(self) -> dict[str, str]:
        """Return the documented Ford authorization-code scope."""
        return {
            "scope": f"{self.client_id} offline_access openid",
        }

    async def _async_refresh_token(self, token: dict[str, Any]) -> dict[str, Any]:
        """Refresh a token, persisting Ford's replacement refresh token atomically."""
        refreshed = await self._token_request(
            {
                "grant_type": "refresh_token",
                "refresh_token": token["refresh_token"],
                "redirect_uri": self.redirect_uri,
                "scope": f"{self.client_id} offline_access openid",
            }
        )
        return {**token, **refreshed}


async def async_get_auth_implementation(
    hass: HomeAssistant,
    auth_domain: str,
    credential: ClientCredential,
) -> AbstractOAuth2Implementation:
    """Return an OAuth implementation configured by Application Credentials."""
    return FordConnectOAuth2Implementation(
        hass=hass,
        domain=auth_domain,
        client_id=credential.client_id,
        client_secret=credential.client_secret,
        authorize_url=AUTHORIZE_URL,
        token_url=TOKEN_URL,
    )


async def async_get_authorization_server(hass: HomeAssistant) -> AuthorizationServer:
    """Return Ford's authorization and token endpoints."""
    return AuthorizationServer(authorize_url=AUTHORIZE_URL, token_url=TOKEN_URL)


async def async_get_description_placeholders(hass: HomeAssistant) -> dict[str, str]:
    """Return links used by the application credential dialog."""
    return {"developer_url": "https://developer.ford.com"}
