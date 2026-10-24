"""Setup, entities, commands, notifications and diagnostics against the simulated panel."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_capture_events

from custom_components.inim_smartlan.const import (
    DOMAIN,
    EVENT_OUTPUT_ACTIVE,
    EVENT_SCENARIO_CHANGED,
)
from custom_components.inim_smartlan.diagnostics import async_get_config_entry_diagnostics

from .conftest import FakePanel


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> MockConfigEntry:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    return entry


def _eid(hass: HomeAssistant, entry: MockConfigEntry, domain: str, key: str) -> str:
    entity_id = er.async_get(hass).async_get_entity_id(domain, DOMAIN, f"{entry.entry_id}_{key}")
    assert entity_id, f"no {domain} entity for {key}"
    return entity_id


async def _refresh(entry: MockConfigEntry, *groups: str) -> None:
    coordinator = entry.runtime_data
    coordinator._schedule.invalidate(*groups)
    await coordinator.async_refresh()


async def test_setup_creates_entities(hass: HomeAssistant, make_entry) -> None:
    entry = await _setup(hass, make_entry())

    assert hass.states.get(_eid(hass, entry, "alarm_control_panel", "partition_0")).state == (
        "disarmed"
    )
    assert hass.states.get(_eid(hass, entry, "select", "scenario")).state == "Away"
    assert hass.states.get(_eid(hass, entry, "switch", "output_0")).state == "off"
    assert hass.states.get(_eid(hass, entry, "binary_sensor", "zone_0")).state == "off"
    assert hass.states.get(_eid(hass, entry, "binary_sensor", "zone_1")).state == "on"
    assert hass.states.get(_eid(hass, entry, "sensor", "last_event")).state == "Valid key"
    # the reset button is always available, even without an alarm memory
    button = hass.states.get(_eid(hass, entry, "button", "reset_memory_0"))
    assert button.state != "unavailable"


async def test_unload(hass: HomeAssistant, make_entry) -> None:
    entry = await _setup(hass, make_entry())
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_arm_away_sends_command(hass: HomeAssistant, panel: FakePanel, make_entry) -> None:
    entry = await _setup(hass, make_entry())
    await hass.services.async_call(
        "alarm_control_panel",
        "alarm_arm_away",
        {"entity_id": _eid(hass, entry, "alarm_control_panel", "partition_0")},
        blocking=True,
    )
    assert panel.commands("do_part") == [("0", "1")]


async def test_arm_blocked_when_zones_not_ready(
    hass: HomeAssistant, panel: FakePanel, make_entry
) -> None:
    entry = await _setup(hass, make_entry())
    panel.not_ready = {"0": ["Window"]}
    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            "alarm_control_panel",
            "alarm_arm_away",
            {"entity_id": _eid(hass, entry, "alarm_control_panel", "partition_0")},
            blocking=True,
        )
    assert err.value.translation_key == "zones_not_ready"
    assert err.value.translation_placeholders == {"zones": "Window"}
    assert panel.commands("do_part") == []


async def test_disarm_is_never_blocked(hass: HomeAssistant, panel: FakePanel, make_entry) -> None:
    entry = await _setup(hass, make_entry())
    panel.not_ready = {"0": ["Window"]}
    await hass.services.async_call(
        "alarm_control_panel",
        "alarm_disarm",
        {"entity_id": _eid(hass, entry, "alarm_control_panel", "partition_0")},
        blocking=True,
    )
    assert panel.commands("do_part") == [("0", "4")]


async def test_select_scenario(hass: HomeAssistant, panel: FakePanel, make_entry) -> None:
    entry = await _setup(hass, make_entry())
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": _eid(hass, entry, "select", "scenario"), "option": "Home"},
        blocking=True,
    )
    assert panel.commands("do_sce") == [("0", None)]


async def test_reset_alarm_memory_button(hass: HomeAssistant, panel: FakePanel, make_entry) -> None:
    entry = await _setup(hass, make_entry())
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": _eid(hass, entry, "button", "reset_memory_1")},
        blocking=True,
    )
    assert panel.commands("do_part") == [("1", "5")]


async def test_output_switch(hass: HomeAssistant, panel: FakePanel, make_entry) -> None:
    entry = await _setup(hass, make_entry())
    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": _eid(hass, entry, "switch", "output_0")},
        blocking=True,
    )
    assert panel.commands("do_cmd") == [("0", "1")]


async def test_scenario_change_event_and_notification(
    hass: HomeAssistant, panel: FakePanel, make_entry
) -> None:
    entry = await _setup(hass, make_entry(options={"notify_scenario": True}))
    events = async_capture_events(hass, EVENT_SCENARIO_CHANGED)

    panel.scenario = "0"
    with patch(
        "custom_components.inim_smartlan.notifications.persistent_notification.async_create"
    ) as create:
        await _refresh(entry, "state")
        await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].data["name"] == "Home"
    create.assert_called_once()


async def test_no_notification_when_disabled(
    hass: HomeAssistant, panel: FakePanel, make_entry
) -> None:
    entry = await _setup(hass, make_entry())
    events = async_capture_events(hass, EVENT_SCENARIO_CHANGED)

    panel.scenario = "0"
    with patch(
        "custom_components.inim_smartlan.notifications.persistent_notification.async_create"
    ) as create:
        await _refresh(entry, "state")
        await hass.async_block_till_done()

    assert len(events) == 1  # the event is always fired
    create.assert_not_called()


async def test_output_active_event(hass: HomeAssistant, panel: FakePanel, make_entry) -> None:
    entry = await _setup(hass, make_entry())
    events = async_capture_events(hass, EVENT_OUTPUT_ACTIVE)

    panel.outputs[0]["st"] = "1"
    await _refresh(entry, "state")
    await hass.async_block_till_done()
    assert [e.data["name"] for e in events] == ["Siren"]

    await _refresh(entry, "state")  # still on: no second event
    await hass.async_block_till_done()
    assert len(events) == 1


async def test_diagnostics_are_redacted(hass: HomeAssistant, make_entry) -> None:
    entry = await _setup(hass, make_entry())
    result = await async_get_config_entry_diagnostics(hass, entry)
    dump = json.dumps(result, default=str)

    assert result["entry"]["data"]["password"] == "**REDACTED**"
    assert result["entry"]["data"]["code"] == "**REDACTED**"
    for private in ("127.0.0.1", "Garage", "Kitchen", "Siren", "Bob", "Reader"):
        assert private not in dump, private
    assert result["discovered"]["timers"] == 1
