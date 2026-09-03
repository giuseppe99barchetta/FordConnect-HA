"""Account-level update coordinator for Ford Connect."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import (
    FordConnectApi,
    FordConnectApiError,
    FordConnectAuthenticationError,
    FordConnectRateLimitError,
    FordConnectUnsupportedError,
)
from .const import DOMAIN, UPDATE_INTERVAL
from .telemetry import telemetry_records, vehicle_records


@dataclass(frozen=True, slots=True)
class FordVehicleData:
    """Garage metadata and telemetry for one Ford vehicle."""

    vehicle_id: str
    garage: dict[str, Any]
    telemetry: dict[str, Any]

    @property
    def metrics(self) -> dict[str, Any]:
        """Return the telemetry metrics mapping, or an empty mapping."""
        metrics = self.telemetry.get("metrics", {})
        return dict(metrics) if isinstance(metrics, dict) else {}


@dataclass(frozen=True, slots=True)
class FordConnectData:
    """All data returned for a Ford Connect account update."""

    vehicles: dict[str, FordVehicleData]
    queried_at: datetime
    endpoint_data: dict[str, Any]
    endpoint_status: dict[str, str]


class FordConnectCoordinator(DataUpdateCoordinator[FordConnectData]):
    """Fetch garage and telemetry once for all entities in an account."""

    def __init__(self, hass: HomeAssistant, api: FordConnectApi) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            logger=logging.getLogger(__name__),
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.api = api
        self._not_before: datetime | None = None
        self._endpoint_data: dict[str, Any] = {}
        self._endpoint_status: dict[str, str] = {}
        self._endpoint_updated: dict[str, datetime] = {}
        self._initial_optional_refresh_pending = True

    async def _async_update_data(self) -> FordConnectData:
        """Fetch account data while preserving entities during partial failures."""
        if self._not_before and dt_util.utcnow() < self._not_before:
            raise UpdateFailed(
                "Ford Connect is waiting for its requested retry interval"
            )
        try:
            # Ford can rate-limit an account when several query resources are
            # requested at once. Telemetry is the priority, so avoid a setup burst.
            garage_payload = await self.api.async_get_garage()
            telemetry_payload = await self.api.async_get_telemetry()
        except FordConnectAuthenticationError as err:
            raise ConfigEntryAuthFailed("Ford Connect authentication failed") from err
        except FordConnectRateLimitError as err:
            if err.retry_after is not None:
                self._not_before = dt_util.utcnow() + timedelta(seconds=err.retry_after)
            raise UpdateFailed("Ford Connect rate limit reached") from err
        except FordConnectApiError as err:
            raise UpdateFailed(str(err)) from err

        await self._async_refresh_optional_endpoints()
        garage = vehicle_records(garage_payload)
        telemetry = telemetry_records(telemetry_payload)
        vehicle_ids = set(garage) | set(telemetry)
        return FordConnectData(
            vehicles={
                vehicle_id: FordVehicleData(
                    vehicle_id=vehicle_id,
                    garage=dict(garage.get(vehicle_id, {})),
                    telemetry=dict(telemetry.get(vehicle_id, {})),
                )
                for vehicle_id in vehicle_ids
            },
            queried_at=dt_util.utcnow(),
            endpoint_data=dict(self._endpoint_data),
            endpoint_status=dict(self._endpoint_status),
        )

    async def _async_refresh_optional_endpoints(self) -> None:
        """Refresh slower, optional endpoints without degrading telemetry.

        The published endpoint list does not establish response schemas for every
        account. Payloads are cached for diagnostics and only schema-safe summaries
        are exposed by entities.
        """
        now = dt_util.utcnow()
        if self._initial_optional_refresh_pending:
            self._initial_optional_refresh_pending = False
            self._endpoint_updated = {
                "vehicle_health_alerts": now,
                "wallbox": now,
                "departure_times": now,
                "charge_schedules": now,
            }
            return
        endpoints = {
            "vehicle_health_alerts": (
                self.api.async_get_vehicle_health_alerts,
                timedelta(hours=1),
            ),
            "wallbox": (self.api.async_get_wallbox, timedelta(hours=6)),
            "departure_times": (self.api.async_get_departure_times, timedelta(hours=6)),
            "charge_schedules": (
                self.api.async_get_charge_schedules,
                timedelta(hours=6),
            ),
        }
        due = [
            (name, request)
            for name, (request, interval) in endpoints.items()
            if now
            - self._endpoint_updated.get(name, datetime.min.replace(tzinfo=now.tzinfo))
            >= interval
        ]
        if not due:
            return
        name, request = due[0]
        result: Any
        try:
            result = await request()
        except Exception as err:  # Optional endpoint failures never hide telemetry.
            result = err
        self._endpoint_updated[name] = now
        if isinstance(result, FordConnectAuthenticationError):
            # Some optional Ford resources can require an entitlement that is
            # independent from the token used successfully for telemetry.
            # Keep the core coordinator available in that case.
            self._endpoint_status[name] = "error"
        elif isinstance(result, FordConnectUnsupportedError):
            self._endpoint_status[name] = "unsupported"
        elif isinstance(result, FordConnectRateLimitError):
            self._endpoint_status[name] = "rate_limited"
            if result.retry_after is not None:
                self._not_before = now + timedelta(seconds=result.retry_after)
        elif isinstance(result, FordConnectApiError):
            self._endpoint_status[name] = "error"
        elif isinstance(result, Exception):
            self._endpoint_status[name] = "error"
        else:
            self._endpoint_data[name] = result
            self._endpoint_status[name] = "ok"
