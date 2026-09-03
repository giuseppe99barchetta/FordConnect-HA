# Ford Connect for Home Assistant

Ford Connect is a Home Assistant custom integration for the official FordConnect Query API. It uses Ford OAuth, the documented query endpoints, and no reverse-engineered FordPass API.

## Authentication and Ford Developer Portal

Create a FordConnect application at [Ford Developer](https://developer.ford.com), then choose the same authentication mode in the portal and in Home Assistant:

| Mode | Home Assistant Internet exposure | Ford Redirect URI |
| --- | --- | --- |
| Automatic | External HTTPS URL or Home Assistant Cloud required | `<EXTERNAL_URL>/api/ford_connect/oauth/callback` |
| Manual | Not required | `http://localhost:8080/callback` |

Automatic is the easiest mode when Home Assistant already has a working public HTTPS address (Home Assistant Cloud, reverse proxy, or tunnel). Ford redirects to the integration’s protected callback after login.

Manual is for LAN-only Home Assistant. It needs no port forwarding, reverse proxy, Cloudflare Tunnel, public DNS, or Home Assistant Cloud. Register exactly `http://localhost:8080/callback`, select **Manual** in the setup flow, open the presented Ford authorization link, and sign in. Ford will redirect the browser to localhost; a connection failure is expected because no localhost server is required. Copy the **complete** URL from the browser address bar and paste it into Home Assistant. Do not extract only the code.

The configured Ford redirect must exactly match the selected mode. Prefer configuring only the redirect you plan to use if Ford’s portal does not reliably support both. Do not use `https://my.home-assistant.io/redirect/oauth`: Ford rejects Home Assistant’s JWT-style OAuth state.

Keep the Client ID, Client Secret, callback URL, authorization code, tokens, full VIN, and location private.

## Installation and setup

Copy `custom_components/ford_connect` into Home Assistant’s `config/custom_components/ford_connect`, restart Home Assistant, add Ford Connect application credentials, then add the integration. The integration preserves Ford’s rotating refresh token and uses the exact redirect URI selected at initial authorization for both token exchange and refresh.

## Support matrix

| Feature | Support |
| --- | --- |
| Garage / vehicle discovery | Yes |
| Vehicle telemetry | Yes, when returned by Ford |
| Fuel, range, GPS, tires, doors, locks | Yes, when returned by Ford |
| Vehicle health alerts API | Queried and retained safely; schema-specific mapping awaits developer schema access |
| Wallbox API | Queried when available; no wallbox is treated as unsupported |
| EV departure times / charge schedules APIs | Queried when available; ICE accounts are supported normally |
| Charging station activity (FCCS) | Client method available only with a discovered station ID; never guessed or polled automatically |
| Remote commands | Not supported: no verified official FordConnect command endpoint is implemented |

An API being available does not mean a particular vehicle or account exposes that capability.

## Entities

The device page is capability-aware. Everyday telemetry is enabled by default: vehicle/fuel, 12-V battery state, engine, doors and security, tires, and location. Native units are used for percentages, km, °C, km/h, V, kPa, rpm, and heading degrees. Ford’s per-metric `updateTime` is exposed as `ford_update_time`, so stale cloud telemetry is not implied to be real-time.

Low-level diagnostics such as acceleration axes, pedal/torque values, yaw rate, gear/lifecycle modes, seat belt status, remote-start configuration, and display units are added only when Ford provides them and are disabled by default to keep the device page usable. Window position is deliberately not inferred because the available telemetry range semantics are not yet documented.

## Polling, privacy, and errors

Garage and telemetry refresh about every 15 minutes. Vehicle health refreshes hourly; wallbox and EV schedules refresh every six hours. Optional endpoint failures, unsupported 404 responses, or an absent EV capability do not make vehicle telemetry unavailable. 401 refreshes once, 429 honors `Retry-After`, and server/network failures remain temporary coordinator errors.

Diagnostics contain capability names, metric timestamps, and endpoint status only. They exclude credentials, tokens, codes, full identifiers, VIN, coordinates, precise location, and wallbox identifiers. The integration does not log those values.

## Development

Run `ruff check .`, JSON validation, and `pytest`. Test fixtures must stay anonymized and must never contain real Ford account data.
