"""Sensor entities for Ford Connect telemetry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.const import UnitOfPressure
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import FordConnectCoordinator
from .entity import FordConnectEntity
from .telemetry import (
    matching_metric_record,
    metric_at,
    metric_attributes,
    update_time_from_metric,
    value_from_metric,
)


@dataclass(frozen=True, kw_only=True)
class FordSensorDescription(SensorEntityDescription):
    """Description of one direct Ford metric sensor."""

    metric: str


SENSORS: tuple[FordSensorDescription, ...] = (
    FordSensorDescription(
        key="fuel_level", translation_key="fuel_level", metric="fuelLevel"
    ),
    FordSensorDescription(
        key="fuel_range", translation_key="fuel_range", metric="fuelRange"
    ),
    FordSensorDescription(
        key="odometer", translation_key="odometer", metric="odometer"
    ),
    FordSensorDescription(
        key="battery_voltage",
        translation_key="battery_voltage",
        metric="batteryVoltage",
    ),
    FordSensorDescription(
        key="battery_state_of_charge",
        translation_key="battery_state_of_charge",
        metric="batteryStateOfCharge",
    ),
    FordSensorDescription(
        key="oil_life", translation_key="oil_life", metric="oilLifeRemaining"
    ),
    FordSensorDescription(
        key="outside_temperature",
        translation_key="outside_temperature",
        metric="outsideTemperature",
    ),
    FordSensorDescription(
        key="engine_coolant_temperature",
        translation_key="engine_coolant_temperature",
        metric="engineCoolantTemp",
    ),
    FordSensorDescription(key="speed", translation_key="speed", metric="speed"),
    FordSensorDescription(
        key="engine_speed", translation_key="engine_speed", metric="engineSpeed"
    ),
    FordSensorDescription(
        key="compass_direction",
        translation_key="compass_direction",
        metric="compassDirection",
    ),
    FordSensorDescription(key="heading", translation_key="heading", metric="heading"),
)
TIRES = ("front_left", "front_right", "rear_left", "rear_right")


async def async_setup_entry(
    hass: HomeAssistant,
    entry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Ford Connect sensor entities."""
    coordinator: FordConnectCoordinator = entry.runtime_data
    async_add_entities(
        [
            FordMetricSensor(coordinator, vehicle_id, description)
            for vehicle_id in coordinator.data.vehicles
            for description in SENSORS
        ]
        + [
            FordTirePressureSensor(coordinator, vehicle_id, position)
            for vehicle_id in coordinator.data.vehicles
            for position in TIRES
        ]
    )


class FordMetricSensor(FordConnectEntity, SensorEntity):
    """Expose a raw Ford metric without treating it as real-time data."""

    entity_description: FordSensorDescription

    def __init__(
        self,
        coordinator: FordConnectCoordinator,
        vehicle_id: str,
        description: FordSensorDescription,
    ) -> None:
        """Initialize the metric sensor."""
        super().__init__(coordinator, vehicle_id)
        self.entity_description = description
        self._attr_unique_id = f"{vehicle_id}_{description.key}"

    @property
    def native_value(self) -> Any:
        """Return the unmodified Ford metric value."""
        return (
            value_from_metric(
                metric_at(self.vehicle.metrics, self.entity_description.metric)
            )
            if self.vehicle
            else None
        )

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Use a provider-supplied unit only; do not infer units."""
        metric = (
            metric_at(self.vehicle.metrics, self.entity_description.metric)
            if self.vehicle
            else None
        )
        if not isinstance(metric, dict):
            return None
        unit = metric.get("unit") or metric.get("unitOfMeasure") or metric.get("uom")
        return str(unit) if unit else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose Ford metadata including its per-metric timestamp."""
        metric = (
            metric_at(self.vehicle.metrics, self.entity_description.metric)
            if self.vehicle
            else None
        )
        attributes = metric_attributes(metric)
        if timestamp := update_time_from_metric(metric):
            attributes["ford_update_time"] = timestamp
        return attributes


class FordTirePressureSensor(FordConnectEntity, SensorEntity):
    """Expose an explicitly documented kPa tire-pressure value."""

    _attr_native_unit_of_measurement = UnitOfPressure.KPA

    def __init__(
        self, coordinator: FordConnectCoordinator, vehicle_id: str, position: str
    ) -> None:
        """Initialize a pressure sensor for one wheel position."""
        super().__init__(coordinator, vehicle_id)
        self._position = position
        self._attr_translation_key = f"tire_pressure_{position}"
        self._attr_unique_id = f"{vehicle_id}_{position}_tire_pressure"

    @property
    def _record(self) -> dict[str, Any] | None:
        if not self.vehicle:
            return None
        target = position_to_ford(self._position)
        record = matching_metric_record(
            self.vehicle.metrics, "tirePressure", vehicleWheel=target
        )
        return dict(record) if record else None

    @property
    def native_value(self) -> Any:
        """Return the kPa pressure value when Ford identifies this wheel."""
        return value_from_metric(self._record)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Preserve Ford wheel placard and timestamp metadata."""
        attributes = metric_attributes(self._record)
        if timestamp := update_time_from_metric(self._record):
            attributes["ford_update_time"] = timestamp
        return attributes


def position_to_ford(position: str) -> str:
    """Return the Ford wheel label matched by the documented telemetry."""
    return position.upper()
