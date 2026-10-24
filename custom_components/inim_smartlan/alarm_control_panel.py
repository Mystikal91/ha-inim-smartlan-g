"""Partitions as alarm control panels."""

from __future__ import annotations

from typing import Any

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import InimError, clean
from .const import ARM_AWAY, ARM_INSTANT, ARM_STAY, DISARM
from .coordinator import InimConfigEntry, InimCoordinator
from .entity import InimEntity

# "am" values returned by mod=part. 3 (instant) is mapped to "night" for lack
# of a better Home Assistant equivalent.
_ARM_MAP = {
    str(ARM_AWAY): AlarmControlPanelState.ARMED_AWAY,
    str(ARM_STAY): AlarmControlPanelState.ARMED_HOME,
    str(ARM_INSTANT): AlarmControlPanelState.ARMED_NIGHT,
}


async def async_setup_entry(
    hass: HomeAssistant, entry: InimConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(InimPartition(coordinator, pid) for pid in coordinator.data["partitions"])


class InimPartition(InimEntity, AlarmControlPanelEntity):
    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_AWAY
        | AlarmControlPanelEntityFeature.ARM_HOME
        | AlarmControlPanelEntityFeature.ARM_NIGHT
    )
    _attr_code_arm_required = False

    def __init__(self, coordinator: InimCoordinator, pid: str) -> None:
        super().__init__(coordinator, f"partition_{pid}")
        self._pid = pid
        label = clean(coordinator.data["partitions"][pid].get("lb"))
        self._attr_name = label or f"Partition {pid}"

    @property
    def _row(self) -> dict[str, Any] | None:
        return self.coordinator.data["partitions"].get(self._pid)

    @property
    def available(self) -> bool:
        return super().available and self._row is not None

    @property
    def alarm_state(self) -> AlarmControlPanelState | None:
        row = self._row
        if row is None:
            return None
        am = str(row.get("am"))
        if am in ("4", "5"):
            return AlarmControlPanelState.DISARMED
        if str(row.get("mm")) == "1":
            return AlarmControlPanelState.TRIGGERED
        return _ARM_MAP.get(am)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        row = self._row or {}
        return {
            "alarm_memory": str(row.get("mm")) == "1",
            "status_code": row.get("st"),
            "arming_code": row.get("am"),
        }

    async def _set(self, code: int) -> None:
        if code in (ARM_AWAY, ARM_STAY, ARM_INSTANT):
            await self.coordinator.async_ensure_ready("partition", self._pid, code)
        try:
            await self.coordinator.client.async_set_partition(self._pid, code)
        except InimError as err:
            raise HomeAssistantError(str(err)) from err
        await self.coordinator.async_request_refresh()

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        await self._set(DISARM)

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        await self._set(ARM_AWAY)

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        await self._set(ARM_STAY)

    async def async_alarm_arm_night(self, code: str | None = None) -> None:
        await self._set(ARM_INSTANT)
