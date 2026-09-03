"""Binary sensor entities for Ford Connect telemetry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import FordConnectCoordinator
from .entity import FordConnectEntity
from .telemetry import (
    as_records,
    matching_metric_record,
    metric_at,
    metric_attributes,
    normalized_door_name,
    update_time_from_metric,
    value_from_metric,
)


@dataclass(frozen=True, kw_only=True)
class FordBinaryDescription(BinarySensorEntityDescription):
    """Description of a Ford status metric."""

    metric: str
    on_values: frozenset[str]


BINARY_SENSORS: tuple[FordBinaryDescription, ...] = (
    FordBinaryDescription(
        key="ignition",
        translation_key="ignition",
        metric="ignitionStatus",
        on_values=frozenset({"ON", "RUNNING", "STARTED"}),
    ),
    FordBinaryDescription(
        key="hood",
        translation_key="hood",
        metric="hoodStatus",
        on_values=frozenset({"OPEN", "AJAR"}),
    ),
    FordBinaryDescription(
        key="alarm",
        translation_key="alarm",
        metric="alarmStatus",
        on_values=frozenset({"ON", "ACTIVE", "TRIGGERED"}),
    ),
    FordBinaryDescription(
        key="parking_brake",
        translation_key="parking_brake",
        metric="parkingBrakeStatus",
        on_values=frozenset({"ON", "ENGAGED", "APPLIED"}),
    ),
    FordBinaryDescription(
        key="doors_locked",
        translation_key="doors_locked",
        metric="doorLockStatus",
        on_values=frozenset({"LOCKED"}),
    ),
    FordBinaryDescription(
        key="tire_pressure_system_problem",
        translation_key="tire_pressure_system_problem",
        metric="tirePressureSystemStatus",
        on_values=frozenset({"FAULT", "WARNING", "ERROR", "MALFUNCTION"}),
    ),
)
DOORS = ("front_left", "front_right", "rear_left", "rear_right", "tailgate")


async def async_setup_entry(
    hass: HomeAssistant,
    entry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Ford Connect binary sensor entities."""
    coordinator: FordConnectCoordinator = entry.runtime_data
    async_add_entities(
        [
            FordStatusBinarySensor(coordinator, vehicle_id, description)
            for vehicle_id in coordinator.data.vehicles
            for description in BINARY_SENSORS
        ]
        + [
            FordDoorBinarySensor(coordinator, vehicle_id, door)
            for vehicle_id in coordinator.data.vehicles
            for door in DOORS
        ]
    )


class FordStatusBinarySensor(FordConnectEntity, BinarySensorEntity):
    """Expose a Ford status only when its documented state is recognized."""

    entity_description: FordBinaryDescription

    def __init__(
        self,
        coordinator: FordConnectCoordinator,
        vehicle_id: str,
        description: FordBinaryDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, vehicle_id)
        self.entity_description = description
        self._attr_unique_id = f"{vehicle_id}_{description.key}"

    @property
    def _metric(self) -> Any:
        if not self.vehicle:
            return None
        metrics = self.vehicle.metrics
        if self.entity_description.key == "doors_locked":
            return matching_metric_record(
                metrics, self.entity_description.metric, vehicleDoor="ALL_DOORS"
            ) or metric_at(metrics, self.entity_description.metric)
        return metric_at(metrics, self.entity_description.metric)

    @property
    def is_on(self) -> bool | None:
        """Return a state only for a known string status."""
        value = value_from_metric(self._metric)
        if not isinstance(value, str):
            return None
        return value.upper() in self.entity_description.on_values

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the source value and timestamp for cautious interpretation."""
        metric = self._metric
        attributes = metric_attributes(metric)
        if timestamp := update_time_from_metric(metric):
            attributes["ford_update_time"] = timestamp
        return attributes


class FordDoorBinarySensor(FordConnectEntity, BinarySensorEntity):
    """Expose one physical door when Ford provides enough identifying metadata."""

    def __init__(
        self, coordinator: FordConnectCoordinator, vehicle_id: str, door: str
    ) -> None:
        """Initialize a door binary sensor."""
        super().__init__(coordinator, vehicle_id)
        self._door = door
        self._attr_translation_key = f"door_{door}"
        self._attr_unique_id = f"{vehicle_id}_door_{door}"

    @property
    def _record(self) -> dict[str, Any] | None:
        if not self.vehicle:
            return None
        for record in as_records(metric_at(self.vehicle.metrics, "doorStatus")):
            if normalized_door_name(record) == self._door:
                return dict(record)
        return None

    @property
    def is_on(self) -> bool | None:
        """Return true for the explicitly open Ford door states."""
        value = value_from_metric(self._record)
        if isinstance(value, dict):
            value = value.get("status")
        if not isinstance(value, str):
            return None
        return value.upper() in {"OPEN", "AJAR"}

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Preserve Ford metadata and its individual update timestamp."""
        attributes = metric_attributes(self._record)
        if timestamp := update_time_from_metric(self._record):
            attributes["ford_update_time"] = timestamp
        return attributes
