"""Ford-specific OAuth callback and state handling."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from aiohttp import web
from homeassistant.components.http import KEY_HASS, HomeAssistantView
from homeassistant.core import HomeAssistant
from homeassistant.helpers.network import NoURLAvailableError, get_url
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN, OAUTH_CALLBACK_PATH, OAUTH_STATE_TTL

DATA_PENDING_OAUTH_STATES: HassKey[dict[str, PendingOAuthState]] = HassKey(
    f"{DOMAIN}_pending_oauth_states"
)
DATA_CALLBACK_VIEW_REGISTERED: HassKey[bool] = HassKey(
    f"{DOMAIN}_callback_view_registered"
)


class FordConnectExternalUrlError(Exception):
    """Raised when Ford cannot call back to Home Assistant securely."""


@dataclass(frozen=True, slots=True)
class PendingOAuthState:
    """One-time state that binds a Ford response to a config flow."""

    flow_id: str
    redirect_uri: str
    expires_at: datetime


def async_get_redirect_uri(hass: HomeAssistant) -> str:
    """Return Ford's required externally reachable HTTPS callback URI."""
    try:
        base_url = get_url(hass, require_ssl=True, allow_internal=False).rstrip("/")
    except NoURLAvailableError as err:
        raise FordConnectExternalUrlError(
            "Ford Connect requires a configured external HTTPS URL"
        ) from err
    if not base_url.lower().startswith("https://"):
        raise FordConnectExternalUrlError(
            "Ford Connect requires a configured external HTTPS URL"
        )
    return f"{base_url}{OAUTH_CALLBACK_PATH}"


def async_create_pending_state(
    hass: HomeAssistant, flow_id: str, redirect_uri: str
) -> str:
    """Create and retain a secure, short-lived Ford-compatible OAuth state."""
    pending = hass.data.setdefault(DATA_PENDING_OAUTH_STATES, {})
    now = _utcnow()
    _remove_expired_states(pending, now)

    state = secrets.token_urlsafe(32)
    while state in pending:
        state = secrets.token_urlsafe(32)
    pending[state] = PendingOAuthState(
        flow_id=flow_id,
        redirect_uri=redirect_uri,
        expires_at=now + OAUTH_STATE_TTL,
    )
    return state


def async_consume_pending_state(
    hass: HomeAssistant, state: str
) -> PendingOAuthState | None:
    """Consume a state exactly once, returning nothing for invalid or stale state."""
    pending = hass.data.setdefault(DATA_PENDING_OAUTH_STATES, {})
    now = _utcnow()
    _remove_expired_states(pending, now)
    item = pending.pop(state, None)
    if item is None or item.expires_at <= now:
        return None
    return item


def async_register_callback_view(hass: HomeAssistant) -> None:
    """Register the Ford callback view once for this Home Assistant instance."""
    if hass.data.get(DATA_CALLBACK_VIEW_REGISTERED):
        return
    hass.http.register_view(FordConnectOAuthCallbackView())
    hass.data[DATA_CALLBACK_VIEW_REGISTERED] = True


class FordConnectOAuthCallbackView(HomeAssistantView):
    """Receive Ford OAuth responses without relying on Home Assistant JWT state."""

    requires_auth = False
    url = OAUTH_CALLBACK_PATH
    name = "api:ford_connect:oauth_callback"

    async def get(self, request: web.Request) -> web.Response:
        """Validate one-time state and continue the original config flow."""
        state = request.query.get("state")
        if not state:
            return web.Response(status=400, text="Missing OAuth state")

        hass = request.app[KEY_HASS]
        pending = async_consume_pending_state(hass, state)
        if pending is None:
            return web.Response(status=400, text="Invalid or expired OAuth state")

        code = request.query.get("code")
        error = request.query.get("error")
        if code:
            user_input: dict[str, Any] = {
                "code": code,
                "redirect_uri": pending.redirect_uri,
            }
            text = "Authorization succeeded. This window can be closed."
        elif error:
            user_input = {"error": error}
            text = "Authorization was not completed. This window can be closed."
        else:
            return web.Response(status=400, text="Missing OAuth code or error")

        await hass.config_entries.flow.async_configure(
            flow_id=pending.flow_id,
            user_input=user_input,
        )
        return web.Response(
            headers={"content-type": "text/html"},
            text=f"<script>window.close()</script>{text}",
        )


def _remove_expired_states(
    pending: dict[str, PendingOAuthState], now: datetime
) -> None:
    """Delete expired state records without logging their sensitive values."""
    for state, item in list(pending.items()):
        if item.expires_at <= now:
            del pending[state]


def _utcnow() -> datetime:
    """Return an aware UTC timestamp for state expiry checks."""
    return datetime.now(UTC)
