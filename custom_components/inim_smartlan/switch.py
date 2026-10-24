"""Panel outputs ("commands") as switches."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
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
    # Only plain on/off outputs (t missing or "0"); slider/dimmer types are ignored.
    entities: list[SwitchEntity] = [
        InimOutput(c, oid) for oid, meta in c.outputs_meta.items() if str(meta.get("t", "0")) == "0"
    ]
    entities.extend(InimZoneExclusion(c, zid) for zid in c.zone_meta)
    async_add_entities(entities)


class InimOutput(InimEntity, SwitchEntity):
    def __init__(self, coordinator: InimCoordinator, oid: str) -> None:
        super().__init__(coordinator, f"output_{oid}")
        self._oid = oid
        self._attr_name = clean(coordinator.outputs_meta[oid].get("lb")) or f"Output {oid}"

    @property
    def _row(self) -> dict[str, Any] | None:
        return self.coordinator.data["outputs"].get(self._oid)

    @property
    def available(self) -> bool:
        return super().available and self._row is not None

    @property
    def is_on(self) -> bool | None:
        row = self._row
        return None if row is None else str(row.get("st")) == "1"

    async def _set(self, on: bool) -> None:
        try:
            await self.coordinator.client.async_set_output(self._oid, on)
        except InimError as err:
            raise HomeAssistantError(str(err)) from err
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._set(False)


class InimZoneExclusion(InimEntity, SwitchEntity):
    """On = zone excluded (bypassed). Disabled by default: excluding lowers the protection.

    The state comes from the zone field `by` (1 = included). Which `act` value excludes
    comes from the web UI buttons (ON -> 0, OFF -> 1) and is not verified on a real panel.
    """

    _attr_translation_key = "zone_excluded"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: InimCoordinator, zid: str) -> None:
        super().__init__(coordinator, f"zone_excluded_{zid}")
        self._zid = zid
        label = clean(coordinator.zone_meta[zid].get("lb")) or f"Zone {zid}"
        self._attr_translation_placeholders = {"zone": label}

    @property
    def _row(self) -> dict[str, Any] | None:
        return self.coordinator.data["zones"].get(self._zid)

    @property
    def available(self) -> bool:
        return super().available and self._row is not None

    @property
    def is_on(self) -> bool | None:
        row = self._row
        if row is None or row.get("by") is None:
            return None
        return str(row.get("by")) != "1"

    async def _set(self, excluded: bool) -> None:
        try:
            await self.coordinator.client.async_set_zone_excluded(self._zid, excluded)
        except InimError as err:
            raise HomeAssistantError(str(err)) from err
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._set(False)
