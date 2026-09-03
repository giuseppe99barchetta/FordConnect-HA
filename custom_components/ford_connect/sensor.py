"""Sensor entities for Ford Connect telemetry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    DEGREE,
    PERCENTAGE,
    REVOLUTIONS_PER_MINUTE,
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfLength,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import FordConnectCoordinator
from .entity import FordConnectEntity
from .telemetry import (
    matching_metric_record,
    metric_at,
    metric_attributes,
    scalar_value_from_metric,
    update_time_from_metric,
    value_from_metric,
)


@dataclass(frozen=True, kw_only=True)
class FordSensorDescription(SensorEntityDescription):
    """Description of one direct Ford metric sensor."""

    metric: str
    value_key: str | None = None


SENSORS: tuple[FordSensorDescription, ...] = (
    FordSensorDescription(
        key="fuel_level",
        translation_key="fuel_level",
        metric="fuelLevel",
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
    ),
    FordSensorDescription(
        key="fuel_range",
        translation_key="fuel_range",
        metric="fuelRange",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    FordSensorDescription(
        key="odometer",
        translation_key="odometer",
        metric="odometer",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
    ),
    FordSensorDescription(
        key="battery_voltage",
        translation_key="battery_voltage",
        metric="batteryVoltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    FordSensorDescription(
        key="battery_state_of_charge",
        translation_key="battery_state_of_charge",
        metric="batteryStateOfCharge",
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
    ),
    FordSensorDescription(
        key="oil_life",
        translation_key="oil_life",
        metric="oilLifeRemaining",
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
    ),
    FordSensorDescription(
        key="outside_temperature",
        translation_key="outside_temperature",
        metric="outsideTemperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    FordSensorDescription(
        key="engine_coolant_temperature",
        translation_key="engine_coolant_temperature",
        metric="engineCoolantTemp",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    FordSensorDescription(
        key="speed",
        translation_key="speed",
        metric="speed",
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        device_class=SensorDeviceClass.SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    FordSensorDescription(
        key="engine_speed",
        translation_key="engine_speed",
        metric="engineSpeed",
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    FordSensorDescription(
        key="compass_direction",
        translation_key="compass_direction",
        metric="compassDirection",
    ),
    FordSensorDescription(
        key="heading",
        translation_key="heading",
        metric="heading",
        value_key="heading",
        native_unit_of_measurement=DEGREE,
        suggested_display_precision=0,
    ),
    FordSensorDescription(
        key="gear_lever_position",
        translation_key="gear_lever_position",
        metric="gearLeverPosition",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    FordSensorDescription(
        key="accelerator_pedal_position",
        translation_key="accelerator_pedal_position",
        metric="acceleratorPedalPosition",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    FordSensorDescription(
        key="acceleration_x",
        translation_key="acceleration_x",
        metric="acceleration",
        value_key="x",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    FordSensorDescription(
        key="acceleration_y",
        translation_key="acceleration_y",
        metric="acceleration",
        value_key="y",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    FordSensorDescription(
        key="acceleration_z",
        translation_key="acceleration_z",
        metric="acceleration",
        value_key="z",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    FordSensorDescription(
        key="brake_pedal_status",
        translation_key="brake_pedal_status",
        metric="brakePedalStatus",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    FordSensorDescription(
        key="brake_torque",
        translation_key="brake_torque",
        metric="brakeTorque",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    FordSensorDescription(
        key="yaw_rate",
        translation_key="yaw_rate",
        metric="yawRate",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    FordSensorDescription(
        key="remote_start_countdown",
        translation_key="remote_start_countdown",
        metric="remoteStartCountdownTimer",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    FordSensorDescription(
        key="vehicle_lifecycle_mode",
        translation_key="vehicle_lifecycle_mode",
        metric="vehicleLifeCycleMode",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    FordSensorDescription(
        key="torque_at_transmission",
        translation_key="torque_at_transmission",
        metric="torqueAtTransmission",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    FordSensorDescription(
        key="wheel_torque_status",
        translation_key="wheel_torque_status",
        metric="wheelTorqueStatus",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    FordSensorDescription(
        key="seat_belt_status",
        translation_key="seat_belt_status",
        metric="seatBeltStatus",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    FordSensorDescription(
        key="panic_alarm_status",
        translation_key="panic_alarm_status",
        metric="panicAlarmStatus",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    FordSensorDescription(
        key="trip_xev_battery_distance",
        translation_key="trip_xev_battery_distance",
        metric="tripXevBatteryDistanceAccumulated",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    FordSensorDescription(
        key="display_system_of_measure",
        translation_key="display_system_of_measure",
        metric="displaySystemOfMeasure",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    FordSensorDescription(
        key="remote_start_run_duration",
        translation_key="remote_start_run_duration",
        metric="configurations.remoteStartRunDurationSetting",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
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
            if description.entity_registry_enabled_default
            or metric_at(
                coordinator.data.vehicles[vehicle_id].metrics, description.metric
            )
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
        """Return only scalar Ford values; mappings belong in attributes."""
        return (
            scalar_value_from_metric(
                metric_at(self.vehicle.metrics, self.entity_description.metric),
                self.entity_description.value_key,
            )
            if self.vehicle
            else None
        )

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Use verified description units, then provider units for diagnostics."""
        if self.entity_description.native_unit_of_measurement:
            return self.entity_description.native_unit_of_measurement
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
    _attr_device_class = SensorDeviceClass.PRESSURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 0

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
