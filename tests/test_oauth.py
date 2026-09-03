"""Tests for the Ford-specific OAuth state, callback, and token behavior."""

from __future__ import annotations

import asyncio
import re
import sys
from dataclasses import replace
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlparse

import pytest

ROOT = Path(__file__).parents[1] / "custom_components" / "ford_connect"
PACKAGE = "ford_connect_oauth_test"


class _Response:
    def __init__(self, *, status: int = 200, text: str = "", headers=None) -> None:
        self.status = status
        self.text = text
        self.headers = headers or {}


class _URL:
    def __init__(self, value: str) -> None:
        self._value = value

    def with_query(self, data: dict[str, str]) -> _URL:
        from urllib.parse import urlencode

        return _URL(f"{self._value}?{urlencode(data)}")

    def __str__(self) -> str:
        return self._value


class _HassKey(str):
    """Hashable stand-in for Home Assistant's typed data key."""


class _NoURLAvailableError(Exception):
    """Stand-in for Home Assistant's no-external-URL error."""


class _LocalOAuth2Implementation:
    def __init__(self, **kwargs) -> None:
        self.hass = kwargs["hass"]
        self.client_id = kwargs["client_id"]
        self.client_secret = kwargs["client_secret"]
        self.authorize_url = kwargs["authorize_url"]
        self.token_url = kwargs["token_url"]


class _OAuthFlowHandler:
    def __init_subclass__(cls, **kwargs) -> None:
        del kwargs

    async def async_step_user(self, user_input=None):
        return {"type": "user", "input": user_input}

    async def async_step_auth(self, user_input=None):
        if getattr(self, "_auth_error", None):
            raise self._auth_error
        return {"type": "auth", "input": user_input}

    def async_abort(self, *, reason: str):
        return {"type": "abort", "reason": reason}


class _Http:
    def __init__(self) -> None:
        self.views = []

    def register_view(self, view) -> None:
        self.views.append(view)


class _FlowManager:
    def __init__(self) -> None:
        self.calls = []

    async def async_configure(self, *, flow_id: str, user_input: dict) -> None:
        self.calls.append((flow_id, user_input))


class _Hass:
    def __init__(self, base_url: str | None = "https://home.example.com") -> None:
        self.data = {}
        self.http = _Http()
        self.config_entries = SimpleNamespace(flow=_FlowManager())
        self.base_url = base_url


class _Request:
    def __init__(self, hass: _Hass, query: dict[str, str]) -> None:
        self.app = {"hass": hass}
        self.query = query


@pytest.fixture
def oauth_modules(monkeypatch):
    """Load real OAuth source against focused Home Assistant test doubles."""
    for name in list(sys.modules):
        if name == PACKAGE or name.startswith(f"{PACKAGE}."):
            monkeypatch.delitem(sys.modules, name, raising=False)

    package = ModuleType(PACKAGE)
    package.__path__ = [str(ROOT)]
    monkeypatch.setitem(sys.modules, PACKAGE, package)

    homeassistant = ModuleType("homeassistant")
    components = ModuleType("homeassistant.components")
    http = ModuleType("homeassistant.components.http")
    http.KEY_HASS = "hass"
    http.HomeAssistantView = object
    application_credentials = ModuleType(
        "homeassistant.components.application_credentials"
    )
    application_credentials.AuthorizationServer = SimpleNamespace
    application_credentials.ClientCredential = SimpleNamespace
    core = ModuleType("homeassistant.core")
    core.HomeAssistant = object
    config_entries = ModuleType("homeassistant.config_entries")
    config_entries.SOURCE_REAUTH = "reauth"
    config_entries.ConfigFlowResult = dict
    helpers = ModuleType("homeassistant.helpers")
    network = ModuleType("homeassistant.helpers.network")
    network.NoURLAvailableError = _NoURLAvailableError
    network.get_url = lambda hass, **kwargs: _get_external_url(hass)
    oauth_flow = ModuleType("homeassistant.helpers.config_entry_oauth2_flow")
    oauth_flow.AbstractOAuth2Implementation = object
    oauth_flow.AbstractOAuth2FlowHandler = _OAuthFlowHandler
    oauth_flow.LocalOAuth2Implementation = _LocalOAuth2Implementation
    util = ModuleType("homeassistant.util")
    hass_dict = ModuleType("homeassistant.util.hass_dict")
    hass_dict.HassKey = _HassKey
    aiohttp = ModuleType("aiohttp")
    aiohttp.web = SimpleNamespace(Response=_Response, Request=object)
    yarl = ModuleType("yarl")
    yarl.URL = _URL

    for name, module in {
        "homeassistant": homeassistant,
        "homeassistant.components": components,
        "homeassistant.components.http": http,
        "homeassistant.components.application_credentials": application_credentials,
        "homeassistant.core": core,
        "homeassistant.config_entries": config_entries,
        "homeassistant.helpers": helpers,
        "homeassistant.helpers.network": network,
        "homeassistant.helpers.config_entry_oauth2_flow": oauth_flow,
        "homeassistant.util": util,
        "homeassistant.util.hass_dict": hass_dict,
        "aiohttp": aiohttp,
        "yarl": yarl,
    }.items():
        monkeypatch.setitem(sys.modules, name, module)

    const = ModuleType(f"{PACKAGE}.const")
    const.DOMAIN = "ford_connect"
    const.NAME = "Ford Connect"
    const.AUTHORIZE_URL = "https://ford.example/authorize"
    const.TOKEN_URL = "https://ford.example/token"
    const.OAUTH_AUTHORIZE_SCOPE = "openid offline_access"
    const.OAUTH_TOKEN_SCOPE = "{client_id} offline_access openid"
    const.OAUTH_CALLBACK_PATH = "/api/ford_connect/oauth/callback"
    from datetime import timedelta

    const.OAUTH_STATE_TTL = timedelta(minutes=10)
    monkeypatch.setitem(sys.modules, f"{PACKAGE}.const", const)

    oauth = _load_module(f"{PACKAGE}.oauth", ROOT / "oauth.py")
    application = _load_module(
        f"{PACKAGE}.application_credentials", ROOT / "application_credentials.py"
    )
    config_flow = _load_module(f"{PACKAGE}.config_flow", ROOT / "config_flow.py")
    return oauth, application, config_flow


def _load_module(name: str, path: Path) -> ModuleType:
    spec = spec_from_file_location(name, path)
    assert spec and spec.loader
    module = module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _get_external_url(hass: _Hass) -> str:
    if hass.base_url is None:
        raise _NoURLAvailableError
    return hass.base_url


def _implementation(application, hass: _Hass):
    return application.FordConnectOAuth2Implementation(
        hass=hass,
        domain="local",
        client_id="client-id",
        client_secret="client-secret",
        authorize_url="https://ford.example/authorize",
        token_url="https://ford.example/token",
    )


def _query(url: str) -> dict[str, str]:
    return {key: value[0] for key, value in parse_qs(urlparse(url).query).items()}


def test_generated_state_matches_ford_pattern_and_has_no_dots(oauth_modules) -> None:
    """Ford receives a state value accepted by its restrictive validation."""
    _, application, _ = oauth_modules
    state = _query(
        asyncio.run(
            _implementation(application, _Hass()).async_generate_authorize_url("flow-1")
        )
    )["state"]
    assert re.fullmatch(r"^[A-Za-z0-9_%&=-]{1,2000}$", state)
    assert "." not in state


def test_generated_state_is_random(oauth_modules) -> None:
    """Separate OAuth attempts get independently generated state values."""
    _, application, _ = oauth_modules
    implementation = _implementation(application, _Hass())
    first = _query(asyncio.run(implementation.async_generate_authorize_url("flow-1")))[
        "state"
    ]
    second = _query(asyncio.run(implementation.async_generate_authorize_url("flow-2")))[
        "state"
    ]
    assert first != second


def test_callback_resumes_correct_flow_and_preserves_redirect_uri(
    oauth_modules,
) -> None:
    """A valid callback resumes only its original flow and exact callback URI."""
    oauth, application, _ = oauth_modules
    hass = _Hass("https://home.example.com")
    query = _query(
        asyncio.run(
            _implementation(application, hass).async_generate_authorize_url("flow-a")
        )
    )
    response = asyncio.run(
        oauth.FordConnectOAuthCallbackView().get(
            _Request(hass, {"state": query["state"], "code": "authorization-code"})
        )
    )
    assert response.status == 200
    assert hass.config_entries.flow.calls == [
        (
            "flow-a",
            {
                "code": "authorization-code",
                "redirect_uri": "https://home.example.com/api/ford_connect/oauth/callback",
            },
        )
    ]


def test_callback_rejects_unknown_state(oauth_modules) -> None:
    """Unknown states are rejected without resuming a flow."""
    oauth, _, _ = oauth_modules
    hass = _Hass()
    response = asyncio.run(
        oauth.FordConnectOAuthCallbackView().get(
            _Request(hass, {"state": "unknown", "code": "x"})
        )
    )
    assert response.status == 400
    assert hass.config_entries.flow.calls == []


def test_callback_rejects_expired_state(oauth_modules) -> None:
    """Expired states are rejected before their flow can receive a code."""
    oauth, _, _ = oauth_modules
    hass = _Hass()
    state = oauth.async_create_pending_state(
        hass, "flow-a", "https://home.example.com/callback"
    )
    pending = hass.data[oauth.DATA_PENDING_OAUTH_STATES]
    pending[state] = replace(pending[state], expires_at=oauth._utcnow())
    response = asyncio.run(
        oauth.FordConnectOAuthCallbackView().get(
            _Request(hass, {"state": state, "code": "x"})
        )
    )
    assert response.status == 400


def test_callback_state_cannot_be_replayed(oauth_modules) -> None:
    """The callback consumes state before continuing a config flow."""
    oauth, _, _ = oauth_modules
    hass = _Hass()
    state = oauth.async_create_pending_state(
        hass, "flow-a", "https://home.example.com/callback"
    )
    view = oauth.FordConnectOAuthCallbackView()
    assert (
        asyncio.run(view.get(_Request(hass, {"state": state, "code": "x"}))).status
        == 200
    )
    assert (
        asyncio.run(view.get(_Request(hass, {"state": state, "code": "x"}))).status
        == 400
    )


def test_callback_passes_oauth_error_to_the_original_flow(oauth_modules) -> None:
    """Ford authorization errors use Home Assistant's normal rejection path."""
    oauth, _, _ = oauth_modules
    hass = _Hass()
    state = oauth.async_create_pending_state(
        hass, "flow-error", "https://home.example.com/callback"
    )
    response = asyncio.run(
        oauth.FordConnectOAuthCallbackView().get(
            _Request(hass, {"state": state, "error": "access_denied"})
        )
    )
    assert response.status == 200
    assert hass.config_entries.flow.calls == [
        ("flow-error", {"error": "access_denied"})
    ]


def test_multiple_flows_keep_state_and_redirect_uri_separate(oauth_modules) -> None:
    """Simultaneous OAuth flows cannot mix each other's callback data."""
    oauth, application, _ = oauth_modules
    hass = _Hass()
    implementation = _implementation(application, hass)
    first = _query(asyncio.run(implementation.async_generate_authorize_url("flow-1")))
    second = _query(asyncio.run(implementation.async_generate_authorize_url("flow-2")))
    view = oauth.FordConnectOAuthCallbackView()
    asyncio.run(view.get(_Request(hass, {"state": second["state"], "code": "two"})))
    asyncio.run(view.get(_Request(hass, {"state": first["state"], "code": "one"})))
    assert [call[0] for call in hass.config_entries.flow.calls] == ["flow-2", "flow-1"]
    assert all(
        call[1]["redirect_uri"] == first["redirect_uri"]
        for call in hass.config_entries.flow.calls
    )


def test_token_exchange_uses_ford_scope_and_callback_uri(oauth_modules) -> None:
    """Ford receives the required authorization-code scope and exact redirect URI."""
    _, application, _ = oauth_modules
    implementation = _implementation(application, _Hass())
    implementation._token_request = AsyncMock(return_value={"access_token": "new"})
    result = asyncio.run(
        implementation.async_resolve_external_data(
            {
                "code": "code",
                "redirect_uri": "https://home.example.com/api/ford_connect/oauth/callback",
            }
        )
    )
    assert implementation._token_request.await_args.args[0] == {
        "grant_type": "authorization_code",
        "code": "code",
        "redirect_uri": "https://home.example.com/api/ford_connect/oauth/callback",
        "scope": "client-id offline_access openid",
    }
    assert result["_ford_redirect_uri"] == (
        "https://home.example.com/api/ford_connect/oauth/callback"
    )


def test_refresh_rotation_retains_the_exact_callback_uri(oauth_modules) -> None:
    """A refresh uses and replaces Ford's rotating token values correctly."""
    _, application, _ = oauth_modules
    implementation = _implementation(application, _Hass())
    implementation._token_request = AsyncMock(
        return_value={"access_token": "new-access", "refresh_token": "new-refresh"}
    )
    token = {
        "access_token": "old-access",
        "refresh_token": "old-refresh",
        "_ford_redirect_uri": "https://home.example.com/api/ford_connect/oauth/callback",
    }
    result = asyncio.run(implementation._async_refresh_token(token))
    assert result["access_token"] == "new-access"
    assert result["refresh_token"] == "new-refresh"
    assert (
        implementation._token_request.await_args.args[0]["redirect_uri"]
        == token["_ford_redirect_uri"]
    )
    assert (
        implementation._token_request.await_args.args[0]["scope"]
        == "client-id offline_access openid"
    )


def test_missing_external_url_is_a_clean_config_flow_abort(oauth_modules) -> None:
    """A missing HTTPS external URL produces a UI error rather than a crash."""
    oauth, application, config_flow = oauth_modules
    with pytest.raises(oauth.FordConnectExternalUrlError):
        asyncio.run(
            _implementation(application, _Hass(None)).async_generate_authorize_url(
                "flow"
            )
        )

    handler = config_flow.FordConnectConfigFlow()
    handler._auth_error = oauth.FordConnectExternalUrlError("missing URL")
    assert asyncio.run(handler.async_step_auth()) == {
        "type": "abort",
        "reason": "external_url_required",
    }


def test_callback_view_is_registered_only_once(oauth_modules) -> None:
    """Repeated setup and flow starts do not register duplicate HTTP routes."""
    oauth, _, _ = oauth_modules
    hass = _Hass()
    oauth.async_register_callback_view(hass)
    oauth.async_register_callback_view(hass)
    assert len(hass.http.views) == 1
