# Ford Connect for Home Assistant

Ford Connect is a native Home Assistant custom integration for Ford vehicles using the official FordConnect APIs at `developer.ford.com`. It uses only the documented OAuth, garage, and telemetry endpoints; it does not use reverse-engineered FordPass endpoints or enable remote commands.

## Current status

This is an installable first release for telemetry. It creates one Home Assistant device per vehicle returned by Ford's garage endpoint and updates the account every 15 minutes. The interval is deliberately conservative to respect cellular connectivity and Ford API limits.

Supported entities include fuel, range, odometer, battery voltage/state of charge, oil life, temperatures, speed, engine speed, heading, compass direction, four kPa tire-pressure sensors, status binary sensors, individually identified doors, and a GPS device tracker.

Ford metrics are optional. A missing metric does not prevent the other entities from updating. The integration retains Ford's individual `updateTime` as `ford_update_time` when supplied: this is the timestamp of that metric, not a claim that the value is real-time.

## Ford Developer Portal configuration

1. Create or open your FordConnect application in the Ford Developer Portal.
2. Configure Home Assistant's **External URL** with its publicly reachable HTTPS URL, then register this redirect URI exactly:

   ```text
   <HOME_ASSISTANT_EXTERNAL_URL>/api/ford_connect/oauth/callback
   ```

   For example:

   ```text
   https://home.example.com/api/ford_connect/oauth/callback
   ```

   Ford requires HTTPS for non-localhost redirect URIs. The URL must be externally reachable after Ford login and must match the Developer Portal entry exactly. Do not add a trailing slash. Ford redirect validation has shown quirks, so configure one Ford redirect URI where possible. Do not use the manual-test `localhost:8080/callback`, `https://my.home-assistant.io/redirect/oauth`, or Home Assistant's `/auth/external/callback` for this integration.
3. Keep the generated Client ID and Client Secret private. Do not commit either value, authorization codes, refresh tokens, access tokens, VINs, or vehicle coordinates.

## Installation

Copy this repository's `custom_components/ford_connect` directory to Home Assistant's `config/custom_components/ford_connect` directory, then restart Home Assistant. For HACS, add the repository as a custom integration after publishing it to GitHub.

## Configuration

1. In Home Assistant, open **Settings -> Devices & services -> Application credentials**.
2. Add **Ford Connect** and enter the Client ID and Client Secret created in Ford Developer Portal.
3. Open **Settings -> Devices & services -> Add integration**, select **Ford Connect**, and complete Ford's login page.

Home Assistant stores the OAuth token inside the config entry using its normal encrypted-storage mechanisms. Ford rotates refresh tokens; the implementation atomically replaces both access and refresh tokens after every refresh. A rejected token triggers one refresh and request retry, then Home Assistant requests reauthentication if it still fails.

## Privacy and limits

The integration does not log credentials, authorization codes, access or refresh tokens, full VINs, or GPS coordinates. Debug output is intentionally limited to non-sensitive operational errors. GPS coordinates are exposed only to the local Home Assistant device tracker entity.

Ford can return stale metric values, and endpoint availability, permissions, vehicle capabilities, and rate limits vary by account and vehicle. HTTP 429 responses are not retried in a loop; `Retry-After`, when supplied, blocks subsequent coordinator requests until that interval has elapsed. Remote lock, unlock, remote start, horn, and lights are deliberately not implemented because no verified official FordConnect command endpoint is included here.

## Development

Run the included unit tests with a Home Assistant development environment. The test fixtures must remain anonymized and must never contain real Ford account data.
