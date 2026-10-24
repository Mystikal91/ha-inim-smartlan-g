"""System voltage and GSM (Nexus) sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfElectricPotential
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import InimConfigEntry, InimCoordinator
from .entity import InimEntity


@dataclass(frozen=True, kw_only=True)
class InimSensorDescription(SensorEntityDescription):
    value_fn: Callable[[dict[str, Any]], Any]
    gsm: bool = False


_V = {
    "device_class": SensorDeviceClass.VOLTAGE,
    "native_unit_of_measurement": UnitOfElectricPotential.VOLT,
    "state_class": SensorStateClass.MEASUREMENT,
    "entity_category": EntityCategory.DIAGNOSTIC,
}

SENSORS: tuple[InimSensorDescription, ...] = (
    InimSensorDescription(
        key="system_voltage",
        translation_key="system_voltage",
        value_fn=lambda d: d.get("system_voltage"),
        **_V,
    ),
    InimSensorDescription(
        key="gsm_voltage",
        translation_key="gsm_voltage",
        gsm=True,
        value_fn=lambda d: (d.get("gsm") or {}).get("voltage"),
        **_V,
    ),
    InimSensorDescription(
        key="gsm_signal",
        translation_key="gsm_signal",
        gsm=True,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: (d.get("gsm") or {}).get("signal"),
    ),
    InimSensorDescription(
        key="gsm_operator",
        translation_key="gsm_operator",
        gsm=True,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: (d.get("gsm") or {}).get("operator"),
    ),
    InimSensorDescription(
        key="gsm_credit",
        translation_key="gsm_credit",
        gsm=True,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: (d.get("gsm") or {}).get("credit"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: InimConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    c = entry.runtime_data
    entities: list[SensorEntity] = [InimSensor(c, d) for d in SENSORS if c.has_gsm or not d.gsm]
    entities.append(InimLastEvent(c))
    async_add_entities(entities)


class InimSensor(InimEntity, SensorEntity):
    entity_description: InimSensorDescription

    def __init__(self, coordinator: InimCoordinator, description: InimSensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.coordinator.data)


class InimLastEvent(InimEntity, SensorEntity):
    """Latest entry of the panel event log (refreshed on the slow poll)."""

    _attr_translation_key = "last_event"

    def __init__(self, coordinator: InimCoordinator) -> None:
        super().__init__(coordinator, "last_event")

    @property
    def _event(self) -> dict[str, Any] | None:
        return self.coordinator.data.get("last_event")

    @property
    def native_value(self) -> str | None:
        event = self._event
        return None if event is None else event.get("type")

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        event = self._event
        if event is None:
            return None
        when = event.get("time")
        # The panel clock has no zone: assume it follows the Home Assistant one.
        stamp = when.replace(tzinfo=dt_util.get_default_time_zone()).isoformat() if when else None
        return {
            "event_id": event.get("id"),
            "time": stamp,
            "agent": event.get("agent"),
            "location": event.get("location"),
            "partitions": event.get("partitions"),
        }
