"""Tests for dependency-free Ford telemetry parsing."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

_SPEC = spec_from_file_location(
    "ford_connect_telemetry",
    Path(__file__).parents[1] / "custom_components" / "ford_connect" / "telemetry.py",
)
assert _SPEC and _SPEC.loader
_TELEMETRY = module_from_spec(_SPEC)
_SPEC.loader.exec_module(_TELEMETRY)

location_from_metrics = _TELEMETRY.location_from_metrics
normalized_door_name = _TELEMETRY.normalized_door_name
normalized_wheel_name = _TELEMETRY.normalized_wheel_name
vehicle_records = _TELEMETRY.vehicle_records


def test_vehicle_records_accepts_a_garage_envelope() -> None:
    """Garage vehicles are indexed by their stable Ford IDs."""
    assert vehicle_records({"vehicles": [{"vehicleId": "vehicle-1"}]}) == {
        "vehicle-1": {"vehicleId": "vehicle-1"}
    }


def test_door_mapping_uses_ford_role_metadata() -> None:
    """The documented driver-side front record maps to front left."""
    assert (
        normalized_door_name(
            {
                "vehicleDoor": "UNSPECIFIED_FRONT",
                "vehicleOccupantRole": "DRIVER",
                "vehicleSide": "DRIVER",
            }
        )
        == "front_left"
    )


def test_location_requires_both_coordinates() -> None:
    """A partial position never creates a misleading tracker location."""
    assert (
        location_from_metrics({"position": {"value": {"location": {"lat": 45.0}}}})
        is None
    )


def test_wheel_mapping_and_missing_metrics_are_safe() -> None:
    """Tire identifiers are normalized and absent values remain harmless."""
    assert normalized_wheel_name({"vehicleWheel": "REAR_RIGHT"}) == "rear_right"
    assert location_from_metrics({}) is None
