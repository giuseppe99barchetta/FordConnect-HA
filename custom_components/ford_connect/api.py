"""Async client for the documented Ford Connect query API."""

from __future__ import annotations

from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any

from aiohttp import ClientError
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session

from .const import API_BASE_URL, CONF_TOKEN


class FordConnectApiError(Exception):
    """Raised when Ford Connect cannot complete an API request."""


class FordConnectAuthenticationError(FordConnectApiError):
    """Raised when the API rejects the current Ford Connect token."""


class FordConnectRateLimitError(FordConnectApiError):
    """Raised when Ford Connect asks the client to slow down."""

    def __init__(self, retry_after: int | None) -> None:
        """Initialize an API rate-limit error."""
        super().__init__("Ford Connect rate limit reached")
        self.retry_after = retry_after


class FordConnectApi:
    """Make authenticated, privacy-conscious requests to Ford Connect."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, oauth_session: OAuth2Session
    ) -> None:
        """Initialize the API client."""
        self._hass = hass
        self._entry = entry
        self._oauth_session = oauth_session

    async def async_get_garage(self) -> Any:
        """Return the account garage response."""
        return await self._async_get_json("/garage")

    async def async_get_telemetry(self) -> Any:
        """Return the account telemetry response."""
        return await self._async_get_json("/telemetry")

    async def _async_get_json(self, path: str) -> Any:
        """Get a JSON resource and retry exactly once after a 401 refresh."""
        for attempt in range(2):
            try:
                response = await self._oauth_session.async_request(
                    "GET", f"{API_BASE_URL}{path}", timeout=30
                )
            except ClientError as err:
                raise FordConnectApiError(
                    "Ford Connect network request failed"
                ) from err
            try:
                if response.status == 401 and attempt == 0:
                    await self._async_force_token_refresh()
                    continue
                if response.status in {401, 403}:
                    raise FordConnectAuthenticationError(
                        "Ford Connect authorization failed"
                    )
                if response.status == 429:
                    raise FordConnectRateLimitError(
                        _retry_after_seconds(response.headers.get("Retry-After"))
                    )
                if response.status >= 500:
                    raise FordConnectApiError(
                        "Ford Connect service is temporarily unavailable"
                    )
                if response.status >= 400:
                    raise FordConnectApiError(
                        f"Ford Connect request failed with HTTP {response.status}"
                    )
                try:
                    return await response.json(content_type=None)
                except (ClientError, ValueError) as err:
                    raise FordConnectApiError(
                        "Ford Connect returned invalid JSON"
                    ) from err
            finally:
                response.release()
        raise FordConnectAuthenticationError("Ford Connect authorization failed")

    async def _async_force_token_refresh(self) -> None:
        """Refresh once and atomically replace Ford's rotated refresh token."""
        token = await self._oauth_session.implementation.async_refresh_token(
            self._oauth_session.token
        )
        self._hass.config_entries.async_update_entry(
            self._entry,
            data={**self._entry.data, CONF_TOKEN: token},
        )


def _retry_after_seconds(value: str | None) -> int | None:
    """Parse a Retry-After header without raising on malformed input."""
    if not value:
        return None
    try:
        return max(0, int(value))
    except ValueError:
        try:
            return max(
                0,
                int(
                    (
                        parsedate_to_datetime(value) - datetime.now().astimezone()
                    ).total_seconds()
                ),
            )
        except (TypeError, ValueError):
            return None
