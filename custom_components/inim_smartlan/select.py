"""Arming scenarios as a select entity."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import InimError, clean
from .coordinator import InimConfigEntry, InimCoordinator
from .entity import InimEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: InimConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    c = entry.runtime_data
    if c.scenarios:
        async_add_entities([InimScenario(c)])


class InimScenario(InimEntity, SelectEntity):
    _attr_translation_key = "scenario"

    def __init__(self, coordinator: InimCoordinator) -> None:
        super().__init__(coordinator, "scenario")
        self._label_to_id: dict[str, str] = {}
        for s in coordinator.scenarios:
            sid = str(s.get("id"))
            label = clean(s.get("lb")) or f"Scenario {sid}"
            if label in self._label_to_id:
                label = f"{label} ({sid})"
            self._label_to_id[label] = sid
        self._attr_options = list(self._label_to_id)

    @property
    def current_option(self) -> str | None:
        sid = self.coordinator.data.get("scenario_id")
        for label, s in self._label_to_id.items():
            if s == sid:
                return label
        return None

    async def async_select_option(self, option: str) -> None:
        sid = self._label_to_id[option]
        await self.coordinator.async_ensure_ready("scenario", sid)
        try:
            await self.coordinator.client.async_set_scenario(sid)
        except InimError as err:
            raise HomeAssistantError(str(err)) from err
        await self.coordinator.async_request_refresh()
