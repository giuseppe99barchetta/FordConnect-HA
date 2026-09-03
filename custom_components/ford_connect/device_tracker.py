"""Device tracker entities for Ford Connect telemetry."""

from __future__ import annotations

from typing import Any

from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import FordConnectCoordinator
from .entity import FordConnectEntity
from .telemetry import (
    location_from_metrics,
    metric_at,
    update_time_from_metric,
    value_from_metric,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up one Ford Connect device tracker for each vehicle."""
    coordinator: FordConnectCoordinator = entry.runtime_data
    async_add_entities(
        FordVehicleTracker(coordinator, vehicle_id)
        for vehicle_id in coordinator.data.vehicles
    )


class FordVehicleTracker(FordConnectEntity, TrackerEntity):
    """Expose Ford latitude and longitude without logging the coordinates."""

    _attr_translation_key = "vehicle"

    def __init__(self, coordinator: FordConnectCoordinator, vehicle_id: str) -> None:
        """Initialize the vehicle tracker."""
        super().__init__(coordinator, vehicle_id)
        self._attr_unique_id = vehicle_id

    @property
    def _location(self) -> dict[str, Any] | None:
        if not self.vehicle:
            return None
        location = location_from_metrics(self.vehicle.metrics)
        return dict(location) if location else None

    @property
    def latitude(self) -> float | None:
        """Return Ford latitude when present."""
        location = self._location
        return location.get("lat") if location else None

    @property
    def longitude(self) -> float | None:
        """Return Ford longitude when present."""
        location = self._location
        return location.get("lon") if location else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose non-coordinate GPS metadata and telemetry timestamp."""
        if not self.vehicle:
            return {}
        position = metric_at(self.vehicle.metrics, "position")
        value = value_from_metric(position)
        attributes: dict[str, Any] = {}
        if isinstance(value, dict):
            for key in (
                "gpsDimension",
                "gpsCoordinateMethod",
                "pdop",
                "hdop",
                "vdop",
                "gdop",
            ):
                if value.get(key) is not None:
                    attributes[key] = value[key]
        if self._location and self._location.get("alt") is not None:
            attributes["altitude"] = self._location["alt"]
        for metric_key, attribute_key in (
            ("heading", "heading"),
            ("compassDirection", "compass_direction"),
        ):
            metric = metric_at(self.vehicle.metrics, metric_key)
            if (metric_value := value_from_metric(metric)) is not None:
                attributes[attribute_key] = metric_value
        if timestamp := update_time_from_metric(position):
            attributes["ford_gps_timestamp"] = timestamp
        return attributes
