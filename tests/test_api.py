"""Tests for the shared Ford Connect authenticated request client."""

from __future__ import annotations

import asyncio
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

ROOT = Path(__file__).parents[1] / "custom_components" / "ford_connect"
PACKAGE = "ford_connect_api_test"


class _ClientError(Exception):
    pass


class _Response:
    def __init__(self, status: int, payload=None, headers=None) -> None:
        self.status = status
        self.payload = payload
        self.headers = headers or {}
        self.released = False

    async def json(self, content_type=None):
        del content_type
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload

    def release(self) -> None:
        self.released = True


class _Session:
    def __init__(self, responses) -> None:
        self.responses = list(responses)
        self.requests = []
        self.token = {"refresh_token": "old"}
        self.implementation = SimpleNamespace(async_refresh_token=self._refresh)

    async def _refresh(self, token):
        assert token == self.token
        return {"access_token": "fresh", "refresh_token": "rotated"}

    async def async_request(self, *args, **kwargs):
        self.requests.append((args, kwargs))
        result = self.responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


class _Hass:
    def __init__(self) -> None:
        self.config_entries = SimpleNamespace(async_update_entry=self._update)
        self.updated = []

    def _update(self, entry, *, data) -> None:
        self.updated.append((entry, data))


@pytest.fixture
def api_module(monkeypatch):
    for name in list(sys.modules):
        if name == PACKAGE or name.startswith(f"{PACKAGE}."):
            monkeypatch.delitem(sys.modules, name, raising=False)
    package = ModuleType(PACKAGE)
    package.__path__ = [str(ROOT)]
    monkeypatch.setitem(sys.modules, PACKAGE, package)

    aiohttp = ModuleType("aiohttp")
    aiohttp.ClientError = _ClientError
    config_entries = ModuleType("homeassistant.config_entries")
    config_entries.ConfigEntry = object
    core = ModuleType("homeassistant.core")
    core.HomeAssistant = object
    oauth_flow = ModuleType("homeassistant.helpers.config_entry_oauth2_flow")
    oauth_flow.OAuth2Session = object
    const = ModuleType(f"{PACKAGE}.const")
    const.API_BASE_URL = "https://ford.example/fcon-query/v1"
    const.CONF_TOKEN = "token"
    for name, module in {
        "aiohttp": aiohttp,
        "homeassistant.config_entries": config_entries,
        "homeassistant.core": core,
        "homeassistant.helpers.config_entry_oauth2_flow": oauth_flow,
        f"{PACKAGE}.const": const,
    }.items():
        monkeypatch.setitem(sys.modules, name, module)
    spec = spec_from_file_location(f"{PACKAGE}.api", ROOT / "api.py")
    assert spec and spec.loader
    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _client(api_module, responses):
    hass = _Hass()
    entry = SimpleNamespace(data={"token": {"refresh_token": "old"}})
    session = _Session(responses)
    return api_module.FordConnectApi(hass, entry, session), hass, session


def test_all_verified_query_methods_use_shared_authenticated_get(api_module) -> None:
    client, _, session = _client(api_module, [_Response(200, {}) for _ in range(7)])
    asyncio.run(client.async_get_garage())
    asyncio.run(client.async_get_telemetry())
    asyncio.run(client.async_get_vehicle_health_alerts())
    asyncio.run(client.async_get_wallbox())
    asyncio.run(client.async_get_departure_times())
    asyncio.run(client.async_get_charge_schedules())
    asyncio.run(
        client.async_get_charging_station_activity(
            "2026-01-01", "2026-01-02", "station"
        )
    )
    urls = [request[0][1] for request in session.requests]
    assert urls == [
        "https://ford.example/fcon-query/v1/garage",
        "https://ford.example/fcon-query/v1/telemetry",
        "https://ford.example/fcon-query/v1/vehicle-health/alerts",
        "https://ford.example/fcon-query/v1/wallbox",
        "https://ford.example/fcon-query/v1/electric/departure-times",
        "https://ford.example/fcon-query/v1/electric/charge-schedules",
        "https://ford.example/fcon-query/v1/fccs",
    ]
    assert session.requests[-1][1]["headers"] == {"chargingStationId": "station"}


def test_401_refreshes_once_and_persists_rotated_token(api_module) -> None:
    client, hass, session = _client(
        api_module, [_Response(401), _Response(200, {"ok": True})]
    )
    assert asyncio.run(client.async_get_garage()) == {"ok": True}
    assert len(session.requests) == 2
    assert hass.updated[0][1]["token"]["refresh_token"] == "rotated"


def test_optional_404_and_http_errors_are_classified(api_module) -> None:
    client, _, _ = _client(
        api_module,
        [_Response(404), _Response(403), _Response(429, headers={"Retry-After": "12"})],
    )
    with pytest.raises(api_module.FordConnectUnsupportedError):
        asyncio.run(client.async_get_wallbox())
    with pytest.raises(api_module.FordConnectAuthenticationError):
        asyncio.run(client.async_get_garage())
    with pytest.raises(api_module.FordConnectRateLimitError, match="rate limit") as err:
        asyncio.run(client.async_get_garage())
    assert err.value.retry_after == 12


def test_network_invalid_json_and_server_errors_are_safe(api_module) -> None:
    client, _, _ = _client(
        api_module,
        [_ClientError(), _Response(200, ValueError()), _Response(500)],
    )
    with pytest.raises(api_module.FordConnectApiError, match="network"):
        asyncio.run(client.async_get_garage())
    with pytest.raises(api_module.FordConnectApiError, match="invalid JSON"):
        asyncio.run(client.async_get_garage())
    with pytest.raises(api_module.FordConnectApiError, match="temporarily unavailable"):
        asyncio.run(client.async_get_garage())
