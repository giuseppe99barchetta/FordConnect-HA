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
from yarl import URL

from .const import (
    AUTHORIZE_URL,
    OAUTH_AUTHORIZE_SCOPE,
    OAUTH_TOKEN_SCOPE,
    TOKEN_URL,
)
from .oauth import (
    async_create_pending_state,
    async_get_redirect_uri,
    async_register_callback_view,
)


class FordConnectOAuth2Implementation(LocalOAuth2Implementation):
    """OAuth2 implementation for Ford's B2C authorization server."""

    @property
    def redirect_uri(self) -> str:
        """Return the Ford-specific external HTTPS callback URI."""
        return async_get_redirect_uri(self.hass)

    async def async_generate_authorize_url(self, flow_id: str) -> str:
        """Generate Ford's authorization URL with a one-time compatible state."""
        async_register_callback_view(self.hass)
        redirect_uri = self.redirect_uri
        state = async_create_pending_state(self.hass, flow_id, redirect_uri)
        return str(
            URL(self.authorize_url).with_query(
                {
                    "response_type": "code",
                    "client_id": self.client_id,
                    "redirect_uri": redirect_uri,
                    "state": state,
                    "scope": OAUTH_AUTHORIZE_SCOPE,
                }
            )
        )

    @property
    def extra_authorize_data(self) -> dict[str, str]:
        """Return the documented Ford authorization scope."""
        return {"scope": OAUTH_AUTHORIZE_SCOPE}

    @property
    def extra_token_resolve_data(self) -> dict[str, str]:
        """Return the documented Ford authorization-code scope."""
        return {"scope": OAUTH_TOKEN_SCOPE.format(client_id=self.client_id)}

    async def async_resolve_external_data(self, external_data: Any) -> dict[str, Any]:
        """Exchange a callback code using its exact registered redirect URI."""
        redirect_uri = external_data.get("redirect_uri")
        if not isinstance(redirect_uri, str) or not redirect_uri:
            raise ValueError(
                "Ford Connect OAuth callback did not provide a redirect URI"
            )
        token = await self._token_request(
            {
                "grant_type": "authorization_code",
                "code": external_data["code"],
                "redirect_uri": redirect_uri,
                **self.extra_token_resolve_data,
            }
        )
        return {**token, "_ford_redirect_uri": redirect_uri}

    async def _async_refresh_token(self, token: dict[str, Any]) -> dict[str, Any]:
        """Refresh a token, persisting Ford's replacement refresh token atomically."""
        redirect_uri = token.get("_ford_redirect_uri") or self.redirect_uri
        refreshed = await self._token_request(
            {
                "grant_type": "refresh_token",
                "refresh_token": token["refresh_token"],
                "redirect_uri": redirect_uri,
                **self.extra_token_resolve_data,
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
