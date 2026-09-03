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
PLATFORMS: Final = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.DEVICE_TRACKER]
UPDATE_INTERVAL: Final = timedelta(minutes=15)

CONF_AUTH_IMPLEMENTATION: Final = "auth_implementation"
CONF_TOKEN: Final = "token"
