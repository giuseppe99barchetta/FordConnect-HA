"""Diagnostics support for Ford Connect without account or location disclosure."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_AUTH_MODE, DOMAIN
from .coordinator import FordConnectCoordinator

_SENSITIVE_HINTS = (
    "vin",
    "token",
    "secret",
    "code",
    "latitude",
    "longitude",
    "location",
)


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return operational summaries, deliberately excluding all sensitive values."""
    del hass
    coordinator: FordConnectCoordinator = entry.runtime_data
    data = coordinator.data
    vehicles: list[dict[str, Any]] = []
    if data:
        for vehicle in data.vehicles.values():
            timestamps = {
                name: _metric_timestamp(metric)
                for name, metric in vehicle.metrics.items()
                if _metric_timestamp(metric) is not None
            }
            vehicles.append(
                {
                    "metric_names": sorted(vehicle.metrics),
                    "metric_timestamps": timestamps,
                    "garage_fields": sorted(
                        key for key in vehicle.garage if not _is_sensitive(key)
                    ),
                }
            )
    return {
        "integration": DOMAIN,
        "config_entry_version": entry.version,
        "authentication_mode": entry.data.get(CONF_AUTH_MODE, "automatic"),
        "redirect_type": "localhost"
        if entry.data.get(CONF_AUTH_MODE) == "manual"
        else "external_https",
        "coordinator_last_update_success": coordinator.last_update_success,
        "coordinator_last_update": data.queried_at.isoformat() if data else None,
        "endpoint_status": data.endpoint_status if data else {},
        "vehicles": vehicles,
    }


def _metric_timestamp(metric: Any) -> str | None:
    if not isinstance(metric, dict):
        return None
    value = metric.get("updateTime") or metric.get("gpsModuleTimestamp")
    return str(value) if value is not None else None


def _is_sensitive(key: str) -> bool:
    return any(hint in key.lower() for hint in _SENSITIVE_HINTS)
