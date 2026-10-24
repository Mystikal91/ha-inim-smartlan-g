"""Config flow for the INIM SmartLAN integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import InimAuthError, InimClient, InimError
from .const import (
    CONF_CODE,
    CONF_NOTIFY_OUTPUT,
    CONF_NOTIFY_SCENARIO,
    CONF_NOTIFY_TARGET,
    CONF_SLOW_INTERVAL,
    CONF_ZONE_INTERVAL,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SLOW_INTERVAL,
    DEFAULT_ZONE_INTERVAL,
    DOMAIN,
    NOTIFY_PERSISTENT,
)

_SECRET = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))


async def _validate(hass: HomeAssistant, data: Mapping[str, Any]) -> dict[str, str]:
    client = InimClient(
        async_get_clientsession(hass),
        data[CONF_HOST],
        data[CONF_PORT],
        data[CONF_USERNAME],
        data[CONF_PASSWORD],
        data[CONF_CODE],
    )
    await client.async_login()
    return await client.async_get_panel_info()


class InimConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}")
            self._abort_if_unique_id_configured()
            try:
                info = await _validate(self.hass, user_input)
            except InimAuthError:
                errors["base"] = "invalid_auth"
            except InimError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                errors["base"] = "unknown"
            else:
                model = info.get("model_code")
                return self.async_create_entry(
                    title=f"INIM {model}" if model else "INIM alarm panel",
                    data=user_input,
                )
        schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): _SECRET,
                vol.Required(CONF_CODE): _SECRET,
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(schema, user_input),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            data = {**entry.data, **user_input}
            try:
                await _validate(self.hass, data)
            except InimAuthError:
                errors["base"] = "invalid_auth"
            except InimError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(entry, data_updates=user_input)
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {vol.Required(CONF_PASSWORD): _SECRET, vol.Required(CONF_CODE): _SECRET}
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change host, port or credentials without recreating the entities."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            # Empty secrets keep the stored ones.
            data = {**entry.data, **{k: v for k, v in user_input.items() if v not in ("", None)}}
            unique_id = f"{data[CONF_HOST]}:{data[CONF_PORT]}"
            if any(
                other.unique_id == unique_id
                for other in self._async_current_entries()
                if other.entry_id != entry.entry_id
            ):
                return self.async_abort(reason="already_configured")
            try:
                await _validate(self.hass, data)
            except InimAuthError:
                errors["base"] = "invalid_auth"
            except InimError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    entry, unique_id=unique_id, data_updates=data
                )
        schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_PORT): int,
                vol.Required(CONF_USERNAME): str,
                vol.Optional(CONF_PASSWORD): _SECRET,
                vol.Optional(CONF_CODE): _SECRET,
            }
        )
        current = {k: entry.data[k] for k in (CONF_HOST, CONF_PORT, CONF_USERNAME)}
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(schema, user_input or current),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> OptionsFlow:
        return InimOptionsFlow()


class InimOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        opts = self.config_entry.options
        services = sorted(
            name
            for name in self.hass.services.async_services_for_domain("notify")
            if name != "send_message"
        )
        targets = [NOTIFY_PERSISTENT, *[n for n in services if n != NOTIFY_PERSISTENT]]
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=opts.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                    ): vol.All(int, vol.Range(min=5, max=300)),
                    vol.Required(
                        CONF_ZONE_INTERVAL,
                        default=opts.get(CONF_ZONE_INTERVAL, DEFAULT_ZONE_INTERVAL),
                    ): vol.All(int, vol.Range(min=5, max=300)),
                    vol.Required(
                        CONF_SLOW_INTERVAL,
                        default=opts.get(CONF_SLOW_INTERVAL, DEFAULT_SLOW_INTERVAL),
                    ): vol.All(int, vol.Range(min=10, max=3600)),
                    vol.Required(
                        CONF_NOTIFY_SCENARIO, default=opts.get(CONF_NOTIFY_SCENARIO, False)
                    ): BooleanSelector(),
                    vol.Required(
                        CONF_NOTIFY_OUTPUT, default=opts.get(CONF_NOTIFY_OUTPUT, False)
                    ): BooleanSelector(),
                    vol.Required(
                        CONF_NOTIFY_TARGET, default=opts.get(CONF_NOTIFY_TARGET, NOTIFY_PERSISTENT)
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=targets,
                            mode=SelectSelectorMode.DROPDOWN,
                            translation_key="notify_target",
                        )
                    ),
                }
            ),
        )
