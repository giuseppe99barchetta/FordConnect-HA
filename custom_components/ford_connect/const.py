"""Constants for the Ford Connect integration."""

from datetime import timedelta
from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "ford_connect"
NAME: Final = "Ford Connect"

API_BASE_URL: Final = "https://api.vehicle.ford.com/fcon-query/v1"
AUTHORIZE_URL: Final = "https://api.vehicle.ford.com/fcon-public/v1/auth/init"
TOKEN_URL: Final = (
    "https://api.vehicle.ford.com/dah2vb2cprod.onmicrosoft.com/oauth2/v2.0/token"
    "?p=B2C_1A_FCON_AUTHORIZE"
)

OAUTH_AUTHORIZE_SCOPE: Final = "openid offline_access"
OAUTH_TOKEN_SCOPE: Final = "{client_id} offline_access openid"
OAUTH_CALLBACK_PATH: Final = "/api/ford_connect/oauth/callback"
MANUAL_REDIRECT_URI: Final = "http://localhost:8080/callback"
OAUTH_STATE_TTL: Final = timedelta(minutes=10)
PLATFORMS: Final = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.DEVICE_TRACKER]
UPDATE_INTERVAL: Final = timedelta(minutes=15)

CONF_AUTH_IMPLEMENTATION: Final = "auth_implementation"
CONF_TOKEN: Final = "token"
CONF_AUTH_MODE: Final = "auth_mode"
AUTH_MODE_AUTOMATIC: Final = "automatic"
AUTH_MODE_MANUAL: Final = "manual"
