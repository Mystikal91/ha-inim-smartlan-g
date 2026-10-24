"""Diagnostics: structure and raw status codes, never credentials, addresses or names."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import CONF_CODE
from .coordinator import InimConfigEntry

# Credentials, the panel address and every user-chosen name (zones, partitions, users, places).
TO_REDACT = {
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_CODE,
    "tk",
    "lb",
    "ag",
    "lo",
    "unique_id",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: InimConfigEntry
) -> dict[str, Any]:
    c = entry.runtime_data
    data = dict(c.data or {})
    event = data.pop("last_event", None) or {}
    return {
        "entry": async_redact_data(
            {
                "data": dict(entry.data),
                "options": dict(entry.options),
                "unique_id": entry.unique_id,
            },
            TO_REDACT,
        ),
        "panel_info": c.panel_info,
        "discovered": {
            "scenarios": async_redact_data(c.scenarios, TO_REDACT),
            "zones": async_redact_data(list(c.zone_meta.values()), TO_REDACT),
            "outputs": async_redact_data(list(c.outputs_meta.values()), TO_REDACT),
            "timers": len(c.timers_meta),
            "has_gsm": c.has_gsm,
        },
        "data": async_redact_data(data, TO_REDACT),
        "last_event": {k: event.get(k) for k in ("id", "time", "type")},
    }
