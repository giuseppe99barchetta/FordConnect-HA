"""Shared entity support for Ford Connect."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FordConnectCoordinator, FordVehicleData


class FordConnectEntity(CoordinatorEntity[FordConnectCoordinator], Entity):
    """Base entity tied to one vehicle in the account coordinator."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: FordConnectCoordinator, vehicle_id: str) -> None:
        """Initialize a vehicle entity."""
        super().__init__(coordinator)
        self._vehicle_id = vehicle_id

    @property
    def vehicle(self) -> FordVehicleData | None:
        """Return this entity's current vehicle data."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.vehicles.get(self._vehicle_id)

    @property
    def device_info(self) -> DeviceInfo:
        """Return a distinct device for each stable Ford vehicle identifier."""
        garage: dict[str, Any] = self.vehicle.garage if self.vehicle else {}
        model = _first_text(garage, "model", "vehicleModel", "modelName")
        year = _first_text(garage, "modelYear", "year")
        name = _first_text(garage, "nickname", "name", "vehicleName")
        return DeviceInfo(
            identifiers={(DOMAIN, self._vehicle_id)},
            manufacturer="Ford",
            model=model,
            model_id=year,
            name=name or f"Ford vehicle {self._vehicle_id[-6:]}",
        )


def _first_text(source: dict[str, Any], *keys: str) -> str | None:
    """Return the first usable text field without exposing a VIN by default."""
    for key in keys:
        value = source.get(key)
        if value is not None and str(value).strip():
            return str(value)
    return None
