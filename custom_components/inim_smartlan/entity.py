"""Base entity."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import InimCoordinator


class InimEntity(CoordinatorEntity[InimCoordinator]):
    """Entity attached to the single panel device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: InimCoordinator, key: str) -> None:
        super().__init__(coordinator)
        entry_id = coordinator.config_entry.entry_id
        self._attr_unique_id = f"{entry_id}_{key}"
        info = coordinator.panel_info
        model = info.get("model_code")
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            manufacturer="INIM Electronics",
            name=f"INIM {model}" if model else "INIM alarm panel",
            model=f"Panel {model} + SmartLAN/G" if model else "SmartLAN/G",
            sw_version=info.get("firmware"),
        )
