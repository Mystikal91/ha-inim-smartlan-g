"""User-selectable notifications for scenario changes and active outputs."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components import persistent_notification
from homeassistant.core import HomeAssistant

from .const import CONF_NOTIFY_TARGET, DOMAIN, NOTIFY_PERSISTENT

_LOGGER = logging.getLogger(__name__)

_TEXTS = {
    "scenario": {
        "en": ("Scenario changed", "Scenario is now: {name}"),
        "it": ("Scenario cambiato", "Lo scenario attivo ora è: {name}"),
    },
    "output": {
        "en": ("Output active", "Output active: {name}"),
        "it": ("Uscita attiva", "Uscita attiva: {name}"),
    },
}


def render(kind: str, language: str, name: str) -> tuple[str, str]:
    """Return (title, message) in Italian or English."""
    title, message = _TEXTS[kind]["it" if language.lower().startswith("it") else "en"]
    return title, message.format(name=name)


async def async_notify(
    hass: HomeAssistant, options: dict[str, Any], kind: str, name: str, entry_id: str
) -> None:
    """Send the notification to the target chosen in the options.

    The target is either a `notify.<service>` name or the default persistent notification.
    """
    title, message = render(kind, hass.config.language, name)
    target = options.get(CONF_NOTIFY_TARGET) or NOTIFY_PERSISTENT
    if target != NOTIFY_PERSISTENT and hass.services.has_service("notify", target):
        try:
            await hass.services.async_call(
                "notify", target, {"title": title, "message": message}, blocking=False
            )
            return
        except Exception:  # noqa: BLE001
            _LOGGER.warning("Notification via notify.%s failed, using persistent one", target)
    persistent_notification.async_create(
        hass, message, title=title, notification_id=f"{DOMAIN}_{entry_id}_{kind}"
    )
