"""Defensive parsers for Ford Connect garage and telemetry payloads.

This module deliberately has no Home Assistant dependency so its payload handling
can be tested independently and does not assign meaning to undocumented fields.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


def value_from_metric(metric: Any) -> Any:
    """Return a metric value without interpreting it."""
    return metric.get("value") if isinstance(metric, Mapping) else None


def scalar_value_from_metric(metric: Any, key: str | None = None) -> Any:
    """Return a scalar metric value, never a mapping or list entity state."""
    value = value_from_metric(metric)
    if isinstance(value, Mapping) and key:
        value = value.get(key)
    elif value is None and isinstance(metric, Mapping) and key:
        value = metric.get(key)
    return value if not isinstance(value, (Mapping, list, tuple, set)) else None


def update_time_from_metric(metric: Any) -> str | None:
    """Return Ford's per-metric timestamp if it is present."""
    if not isinstance(metric, Mapping):
        return None
    timestamp = metric.get("updateTime") or metric.get("gpsModuleTimestamp")
    return str(timestamp) if timestamp is not None else None


def metric_attributes(metric: Any) -> dict[str, Any]:
    """Return non-value metadata supplied for a metric."""
    if not isinstance(metric, Mapping):
        return {}
    return {
        str(key): value
        for key, value in metric.items()
        if key not in {"value", "updateTime"} and value is not None
    }


def metric_at(metrics: Mapping[str, Any], dotted_key: str) -> Any:
    """Look up a metric, supporting documented dotted metric names."""
    current: Any = metrics
    for key in dotted_key.split("."):
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def as_records(metric: Any) -> list[Mapping[str, Any]]:
    """Normalize a metric that can be represented by one or many records."""
    if isinstance(metric, Mapping):
        value = metric.get("value")
        if isinstance(value, list):
            return [item for item in value if isinstance(item, Mapping)]
        return [metric]
    if isinstance(metric, list):
        return [item for item in metric if isinstance(item, Mapping)]
    return []


def matching_metric_record(
    metrics: Mapping[str, Any], metric_key: str, **expected: str
) -> Mapping[str, Any] | None:
    """Find a metric record whose Ford metadata matches every expected value."""
    for record in as_records(metric_at(metrics, metric_key)):
        value = record.get("value")
        candidates = (record, value) if isinstance(value, Mapping) else (record,)
        for candidate in candidates:
            if all(candidate.get(key) == wanted for key, wanted in expected.items()):
                return record
    return None


def vehicle_id_from_record(record: Mapping[str, Any]) -> str | None:
    """Extract a stable Ford vehicle identifier from a response object."""
    for key in ("vehicleId", "vehicle_id", "id"):
        if record.get(key) is not None:
            return str(record[key])
    return None


def vehicle_records(payload: Any) -> dict[str, Mapping[str, Any]]:
    """Extract vehicle records from common Ford list and envelope responses."""
    candidates: Iterable[Any]
    if isinstance(payload, list):
        candidates = payload
    elif isinstance(payload, Mapping):
        if vehicle_id_from_record(payload):
            candidates = [payload]
        else:
            candidates = next(
                (
                    value
                    for key, value in payload.items()
                    if key in {"vehicles", "garage", "data", "items"}
                    and isinstance(value, list)
                ),
                [],
            )
    else:
        candidates = []

    return {
        vehicle_id: record
        for record in candidates
        if isinstance(record, Mapping)
        and (vehicle_id := vehicle_id_from_record(record)) is not None
    }


def telemetry_records(payload: Any) -> dict[str, Mapping[str, Any]]:
    """Extract telemetry records without assuming a multi-vehicle envelope."""
    records = vehicle_records(payload)
    if records:
        return records
    if isinstance(payload, Mapping):
        vehicles = payload.get("vehicles") or payload.get("data")
        if isinstance(vehicles, list):
            return vehicle_records(vehicles)
    return {}


def location_from_metrics(metrics: Mapping[str, Any]) -> Mapping[str, Any] | None:
    """Return the raw Ford location mapping when latitude and longitude exist."""
    position = metric_at(metrics, "position")
    value = value_from_metric(position)
    if not isinstance(value, Mapping):
        return None
    location = value.get("location")
    if not isinstance(location, Mapping):
        return None
    if location.get("lat") is None or location.get("lon") is None:
        return None
    return location


def normalized_door_name(record: Mapping[str, Any]) -> str | None:
    """Map Ford door metadata to a stable Home Assistant door name."""
    value = record.get("value")
    source = value if isinstance(value, Mapping) else record
    door = str(source.get("vehicleDoor", record.get("vehicleDoor", ""))).upper()
    role = str(
        source.get("vehicleOccupantRole", record.get("vehicleOccupantRole", ""))
    ).upper()
    side = str(source.get("vehicleSide", record.get("vehicleSide", ""))).upper()

    direct = {
        "FRONT_LEFT": "front_left",
        "FRONT_RIGHT": "front_right",
        "REAR_LEFT": "rear_left",
        "REAR_RIGHT": "rear_right",
        "TAILGATE": "tailgate",
        "LIFTGATE": "tailgate",
    }
    if door in direct:
        return direct[door]
    if "TAIL" in door or "LIFT" in door:
        return "tailgate"
    position = "front" if "FRONT" in door else "rear" if "REAR" in door else None
    if position is None:
        return None
    resolved_side = {
        "LEFT": "left",
        "RIGHT": "right",
        "DRIVER": "left",
        "PASSENGER": "right",
    }.get(side) or {"DRIVER": "left", "PASSENGER": "right"}.get(role)
    return f"{position}_{resolved_side}" if resolved_side else None


def normalized_wheel_name(record: Mapping[str, Any]) -> str | None:
    """Map common Ford wheel identifiers to a stable wheel name."""
    value = record.get("value")
    source = value if isinstance(value, Mapping) else record
    wheel = str(
        source.get("vehicleWheel", record.get("vehicleWheel", source.get("wheel", "")))
    ).upper()
    for needle, normalized in {
        "FRONT_LEFT": "front_left",
        "FRONT_RIGHT": "front_right",
        "REAR_LEFT": "rear_left",
        "REAR_RIGHT": "rear_right",
    }.items():
        if needle in wheel:
            return normalized
    return None
