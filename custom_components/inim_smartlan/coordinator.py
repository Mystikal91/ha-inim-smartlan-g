"""Data coordinator for the INIM SmartLAN integration."""

from __future__ import annotations

import logging
import time
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import InimAuthError, InimClient, InimError, build_mask, clean
from .const import (
    CONF_NOTIFY_OUTPUT,
    CONF_NOTIFY_SCENARIO,
    CONF_SLOW_INTERVAL,
    CONF_ZONE_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SLOW_INTERVAL,
    DEFAULT_ZONE_INTERVAL,
    DOMAIN,
    EVENT_OUTPUT_ACTIVE,
    EVENT_SCENARIO_CHANGED,
)
from .notifications import async_notify
from .schedule import PollSchedule

_LOGGER = logging.getLogger(__name__)

type InimConfigEntry = ConfigEntry[InimCoordinator]


class InimCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Polls the panel. Everything is discovered at startup, then polled."""

    config_entry: InimConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: InimConfigEntry,
        client: InimClient,
    ) -> None:
        opts = entry.options
        self._state_interval = opts.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        self._zone_interval = opts.get(CONF_ZONE_INTERVAL, DEFAULT_ZONE_INTERVAL)
        self._slow_interval = opts.get(CONF_SLOW_INTERVAL, DEFAULT_SLOW_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            # The tick is the fastest group; slower groups are skipped until due.
            update_interval=timedelta(seconds=min(self._state_interval, self._zone_interval)),
        )
        self.client = client
        self.panel_info: dict[str, str] = {}
        self.scenarios: list[dict[str, Any]] = []
        self.zone_meta: dict[str, dict[str, Any]] = {}
        self.outputs_meta: dict[str, dict[str, Any]] = {}
        self.timers_meta: dict[str, dict[str, Any]] = {}
        self.has_gsm = False
        self._zone_mask: str | None = None
        self._schedule = PollSchedule()
        self._cache: dict[str, Any] = {
            "scenario_id": None,
            "partitions": {},
            "zones": {},
            "outputs": {},
        }
        self._seen = False  # first poll only records the state, no notifications
        self._prev_scenario: str | None = None
        self._prev_outputs: dict[str, str] = {}
        self._slow: dict[str, Any] = {}

    async def _async_setup(self) -> None:
        """Login and discover what the panel exposes."""
        try:
            await self.client.async_login()
            self.panel_info = await self.client.async_get_panel_info()
            self.scenarios = await self.client.async_get_scenarios()
            zones = await self.client.async_get_zones()
            self.zone_meta = {str(z["id"]): z for z in zones if "id" in z}
            try:
                self._zone_mask = build_mask(z["tl"] for z in zones)
            except (KeyError, ValueError):
                self._zone_mask = None  # fall back to unmasked (slower) polls
            outputs = await self.client.async_get_outputs()
            self.outputs_meta = {str(o["id"]): o for o in outputs if "id" in o}
            try:  # timers are optional: never block the setup
                timers = await self.client.async_get_timers()
                self.timers_meta = {str(t["id"]): t for t in timers if "id" in t}
            except InimError:
                self.timers_meta = {}
            try:
                self.has_gsm = await self.client.async_get_gsm() is not None
            except InimError:
                self.has_gsm = False
        except InimAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except InimError as err:
            raise UpdateFailed(str(err)) from err

    @property
    def supports_ready_check(self) -> bool:
        """The web UI skips the zone pre-check on firmware older than 5.x."""
        try:
            return int(str(self.panel_info.get("firmware", "")).split(".")[0]) >= 5
        except ValueError:
            return False

    async def async_ensure_ready(self, kind: str, target_id: str, arm_code: int = 0) -> None:
        """Refuse to arm while zones are not ready (same check as the panel web UI).

        A failure of the check itself never blocks arming.
        """
        if not self.supports_ready_check:
            return
        try:
            zones = await self.client.async_get_not_ready_zones(kind, target_id, arm_code)
        except InimAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except InimError as err:
            _LOGGER.debug("Zone pre-check not available: %s", err)
            return
        if zones:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="zones_not_ready",
                translation_placeholders={"zones": ", ".join(zones)},
            )

    def _scenario_name(self, sid: str) -> str:
        for s in self.scenarios:
            if str(s.get("id")) == sid:
                return clean(s.get("lb")) or f"Scenario {sid}"
        return f"Scenario {sid}"

    def _detect_changes(self, data: dict[str, Any]) -> None:
        """Fire events (always) and notifications (if enabled) on scenario / output changes."""
        entry = self.config_entry
        scenario = data.get("scenario_id")
        outputs = {oid: str(row.get("st")) for oid, row in data["outputs"].items()}
        if self._seen:
            if scenario is not None and scenario != self._prev_scenario:
                name = self._scenario_name(scenario)
                self.hass.bus.async_fire(
                    EVENT_SCENARIO_CHANGED,
                    {"entry_id": entry.entry_id, "id": scenario, "name": name},
                )
                if entry.options.get(CONF_NOTIFY_SCENARIO):
                    self.hass.async_create_task(
                        async_notify(self.hass, entry.options, "scenario", name, entry.entry_id)
                    )
            for oid, st in outputs.items():
                if st == "1" and self._prev_outputs.get(oid) == "0":
                    meta = self.outputs_meta.get(oid, {})
                    name = clean(meta.get("lb")) or f"Output {oid}"
                    self.hass.bus.async_fire(
                        EVENT_OUTPUT_ACTIVE, {"entry_id": entry.entry_id, "id": oid, "name": name}
                    )
                    if entry.options.get(CONF_NOTIFY_OUTPUT):
                        self.hass.async_create_task(
                            async_notify(self.hass, entry.options, "output", name, entry.entry_id)
                        )
        self._seen = True
        self._prev_scenario = scenario
        self._prev_outputs = outputs

    async def _async_refresh_optional(self) -> None:
        """Timers and the event log are nice to have: a failure keeps the last values."""
        try:
            if self.timers_meta:
                timers = await self.client.async_get_timers()
                self._slow["timers"] = {str(t["id"]): t for t in timers if "id" in t}
            self._slow["last_event"] = await self.client.async_get_last_event()
        except InimAuthError:
            raise
        except InimError as err:
            _LOGGER.debug("Optional data not refreshed: %s", err)

    async def async_request_refresh(self) -> None:
        """Refresh now (after a command): state and zones must not wait for their interval."""
        self._schedule.invalidate("state", "zones")
        await super().async_request_refresh()

    async def _async_update_data(self) -> dict[str, Any]:
        client = self.client
        sched = self._schedule
        now = time.monotonic()
        try:
            if sched.due("state", self._state_interval, now):
                current = await client.async_get_current_scenario()
                sid = current.get("id")
                self._cache["scenario_id"] = None if sid in (None, "") else str(sid)
                self._cache["partitions"] = {
                    str(p["id"]): p for p in await client.async_get_partitions()
                }
                if self.outputs_meta:
                    self._cache["outputs"] = {
                        str(o["id"]): o for o in await client.async_get_outputs()
                    }
                sched.mark("state", now)
            if self.zone_meta and sched.due("zones", self._zone_interval, now):
                zones = await client.async_get_zones(self._zone_mask)
                if not zones and self._zone_mask:
                    zones = await client.async_get_zones()
                self._cache["zones"] = {str(z["id"]): z for z in zones}
                sched.mark("zones", now)
            if sched.due("slow", self._slow_interval, now):
                self._slow = await client.async_get_faults()
                self._slow["gsm"] = await client.async_get_gsm() if self.has_gsm else None
                await self._async_refresh_optional()
                sched.mark("slow", now)
            data = {**self._cache, **self._slow}
            self._detect_changes(data)
            return data
        except InimAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except (InimError, KeyError, TypeError) as err:
            raise UpdateFailed(f"Error talking to the panel: {err}") from err
