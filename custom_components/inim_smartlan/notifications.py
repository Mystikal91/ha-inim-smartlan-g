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


def normalize_targets(value: Any) -> list[str]:
    """Targets from the options: a list, or a single string saved by version 0.2.0."""
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple)):
        return [NOTIFY_PERSISTENT]
    targets = list(dict.fromkeys(str(v) for v in value if v))
    return targets or [NOTIFY_PERSISTENT]


async def async_notify(
    hass: HomeAssistant, options: dict[str, Any], kind: str, name: str, entry_id: str
) -> None:
    """Send the notification to every target chosen in the options.

    A target is a `notify.<service>` name or the Home Assistant (persistent) notification.
    A failing target never stops the others; if nothing could be delivered, the persistent
    notification is used so the alert is not lost.
    """
    title, message = render(kind, hass.config.language, name)
    delivered = False
    persistent = False
    for target in normalize_targets(options.get(CONF_NOTIFY_TARGET)):
        if target == NOTIFY_PERSISTENT:
            persistent = True
        elif not hass.services.has_service("notify", target):
            _LOGGER.warning("Notification service notify.%s not found", target)
        else:
            try:
                await hass.services.async_call(
                    "notify", target, {"title": title, "message": message}, blocking=False
                )
                delivered = True
            except Exception:  # noqa: BLE001
                _LOGGER.warning("Notification via notify.%s failed", target, exc_info=True)
    if persistent or not delivered:
        persistent_notification.async_create(
            hass, message, title=title, notification_id=f"{DOMAIN}_{entry_id}_{kind}"
        )
