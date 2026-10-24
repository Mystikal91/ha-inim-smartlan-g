"""INIM SmartLAN/G integration (unofficial, local polling)."""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.loader import async_get_integration

from .api import InimClient
from .const import CONF_CODE, DOMAIN, PLATFORMS
from .coordinator import InimConfigEntry, InimCoordinator

_LOGGER = logging.getLogger(__name__)

_FRONTEND_KEY = f"{DOMAIN}_frontend_registered"
_STRATEGY_FILE = Path(__file__).parent / "frontend" / "inim-smartlan-dashboard.js"
_STRATEGY_URL = f"/{DOMAIN}_static/inim-smartlan-dashboard.js"


async def _async_register_dashboard_strategy(hass: HomeAssistant) -> None:
    """Serve and load the dashboard strategy once (it is optional: never block the setup)."""
    if hass.data.get(_FRONTEND_KEY):
        return
    # Optional: only when the frontend is running (after_dependencies in the manifest).
    if "http" not in hass.config.components or "frontend" not in hass.config.components:
        return
    try:
        from homeassistant.components import frontend  # noqa: PLC0415
        from homeassistant.components.http import StaticPathConfig  # noqa: PLC0415

        integration = await async_get_integration(hass, DOMAIN)
        await hass.http.async_register_static_paths(
            [StaticPathConfig(_STRATEGY_URL, str(_STRATEGY_FILE), False)]
        )
        frontend.add_extra_js_url(hass, f"{_STRATEGY_URL}?v={integration.version}")
        hass.data[_FRONTEND_KEY] = True
    except Exception:  # noqa: BLE001
        _LOGGER.warning("Could not register the dashboard strategy", exc_info=True)


async def async_setup_entry(hass: HomeAssistant, entry: InimConfigEntry) -> bool:
    client = InimClient(
        async_get_clientsession(hass),
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        entry.data[CONF_CODE],
    )
    await _async_register_dashboard_strategy(hass)
    coordinator = InimCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def _async_reload(hass: HomeAssistant, entry: InimConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: InimConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
