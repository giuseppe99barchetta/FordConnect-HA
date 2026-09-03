"""Account-level update coordinator for Ford Connect."""

from __future__ import annotations

import asyncio
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

    async def _async_update_data(self) -> FordConnectData:
        """Fetch account data while preserving entities during partial failures."""
        if self._not_before and dt_util.utcnow() < self._not_before:
            raise UpdateFailed(
                "Ford Connect is waiting for its requested retry interval"
            )
        try:
            garage_payload, telemetry_payload = await asyncio.gather(
                self.api.async_get_garage(), self.api.async_get_telemetry()
            )
        except FordConnectAuthenticationError as err:
            raise ConfigEntryAuthFailed("Ford Connect authentication failed") from err
        except FordConnectRateLimitError as err:
            if err.retry_after is not None:
                self._not_before = dt_util.utcnow() + timedelta(seconds=err.retry_after)
            raise UpdateFailed("Ford Connect rate limit reached") from err
        except FordConnectApiError as err:
            raise UpdateFailed(str(err)) from err

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
        )
