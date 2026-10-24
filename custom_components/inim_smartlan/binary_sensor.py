"""Zones and panel faults."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import clean
from .const import FAULT_BITS, FAULTS_ENABLED_DEFAULT
from .coordinator import InimConfigEntry, InimCoordinator
from .entity import InimEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: InimConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    c = entry.runtime_data
    entities: list[BinarySensorEntity] = [InimZone(c, zid) for zid in c.zone_meta]
    entities.extend(InimTimer(c, tid) for tid in c.timers_meta)
    entities.append(InimFault(c, None))
    entities.extend(InimFault(c, bit) for bit in FAULT_BITS)
    async_add_entities(entities)


class InimZone(InimEntity, BinarySensorEntity):
    """On when the zone reports status 2 (movement / open / alarm)."""

    def __init__(self, coordinator: InimCoordinator, zid: str) -> None:
        super().__init__(coordinator, f"zone_{zid}")
        self._zid = zid
        meta = coordinator.zone_meta[zid]
        self._attr_name = clean(meta.get("lb")) or f"Zone {zid}"

    @property
    def _row(self) -> dict[str, Any] | None:
        return self.coordinator.data["zones"].get(self._zid)

    @property
    def available(self) -> bool:
        return super().available and self._row is not None

    @property
    def is_on(self) -> bool | None:
        row = self._row
        return None if row is None else str(row.get("st")) == "2"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        row = self._row or {}
        return {
            "status_code": row.get("st"),
            "alarm_memory": str(row.get("mm")) == "1",
            "by": row.get("by"),  # raw flag, meaning still to be confirmed
        }


class InimTimer(InimEntity, BinarySensorEntity):
    """Panel timer, read only. On when the timer reports status 1 (meaning unverified)."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: InimCoordinator, tid: str) -> None:
        super().__init__(coordinator, f"timer_{tid}")
        self._tid = tid
        self._attr_name = clean(coordinator.timers_meta[tid].get("lb")) or f"Timer {tid}"

    @property
    def _row(self) -> dict[str, Any] | None:
        timers = self.coordinator.data.get("timers") or self.coordinator.timers_meta
        return timers.get(self._tid)

    @property
    def is_on(self) -> bool | None:
        row = self._row
        return None if row is None else str(row.get("st")) == "1"


class InimFault(InimEntity, BinarySensorEntity):
    """bit=None -> aggregated 'any fault'; otherwise one specific fault bit."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator: InimCoordinator, bit: int | None) -> None:
        super().__init__(coordinator, "fault" if bit is None else f"fault_{bit}")
        self._bit = bit
        if bit is None:
            self._attr_translation_key = "panel_fault"
        else:
            self._attr_translation_key = f"fault_{FAULT_BITS[bit]}"
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
            self._attr_entity_registry_enabled_default = bit in FAULTS_ENABLED_DEFAULT

    @property
    def _code(self) -> int | None:
        return self.coordinator.data.get("fault_code")

    @property
    def is_on(self) -> bool | None:
        code = self._code
        if code is None:
            return None
        return code != 0 if self._bit is None else bool(code & self._bit)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self._bit is not None or self._code is None:
            return None
        return {
            "fault_code": self._code,
            "active_faults": [n for b, n in FAULT_BITS.items() if self._code & b],
        }
