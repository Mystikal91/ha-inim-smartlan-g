"""Alarm memory reset, one button per partition."""

from __future__ import annotations

from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import InimError, clean
from .const import RESET
from .coordinator import InimConfigEntry, InimCoordinator
from .entity import InimEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: InimConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    c = entry.runtime_data
    async_add_entities(InimResetMemory(c, pid) for pid in c.data["partitions"])


class InimResetMemory(InimEntity, ButtonEntity):
    """Clears the alarm memory of a partition (mod=do_part, act=5).

    Always available, like the Reset entry of the panel web UI.
    """

    _attr_translation_key = "reset_alarm_memory"

    def __init__(self, coordinator: InimCoordinator, pid: str) -> None:
        super().__init__(coordinator, f"reset_memory_{pid}")
        self._pid = pid
        label = clean(coordinator.data["partitions"][pid].get("lb")) or f"Partition {pid}"
        self._attr_translation_placeholders = {"partition": label}

    @property
    def _row(self) -> dict[str, Any] | None:
        return self.coordinator.data["partitions"].get(self._pid)

    @property
    def available(self) -> bool:
        row = self._row
        return super().available and row is not None

    async def async_press(self) -> None:
        try:
            await self.coordinator.client.async_set_partition(self._pid, RESET)
        except InimError as err:
            raise HomeAssistantError(str(err)) from err
        await self.coordinator.async_request_refresh()
