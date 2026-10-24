"""Config flow: setup, errors, duplicates, reauth, reconfigure."""

from __future__ import annotations

from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.inim_smartlan.const import CONF_CODE, DOMAIN

from .conftest import CODE, PASSWORD, USER, FakePanel


def _user_input(port: int, **over) -> dict:
    data = {
        "host": "127.0.0.1",
        "port": port,
        "username": USER,
        "password": PASSWORD,
        CONF_CODE: CODE,
    }
    data.update(over)
    return data


async def test_user_flow_creates_entry(hass: HomeAssistant, panel_port: int) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _user_input(panel_port)
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "INIM 515"
    assert result["data"]["port"] == panel_port


async def test_invalid_auth(hass: HomeAssistant, panel_port: int) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _user_input(panel_port, password="wrong")
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_cannot_connect(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], _user_input(1))
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_already_configured(hass: HomeAssistant, panel_port: int, make_entry) -> None:
    make_entry().add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _user_input(panel_port)
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth(hass: HomeAssistant, panel: FakePanel, make_entry) -> None:
    entry = make_entry()
    entry.add_to_hass(hass)
    panel.password = "new-password"

    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"password": "new-password", CONF_CODE: CODE}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data["password"] == "new-password"


async def test_reconfigure_changes_port(
    hass: HomeAssistant, panel: FakePanel, panel_port: int, make_entry, aiohttp_server
) -> None:
    from .conftest import _make_app

    entry = make_entry()
    entry.add_to_hass(hass)
    second = await aiohttp_server(_make_app(panel))

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    # empty password / code keep the stored ones
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"host": "127.0.0.1", "port": second.port, "username": USER},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data["port"] == second.port
    assert entry.data["password"] == PASSWORD
    assert entry.unique_id == f"127.0.0.1:{second.port}"
