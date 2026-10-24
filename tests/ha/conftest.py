"""Fixtures: a simulated SmartLAN/G panel served on 127.0.0.1 and a ready config entry."""

from __future__ import annotations

from typing import Any

import pytest
from aiohttp import web
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.inim_smartlan.const import CONF_CODE, DOMAIN

USER, PASSWORD, CODE = "user", "pass", "1234"
TOKEN = "T" * 32


class FakePanel:
    """Just enough of the web.cgi protocol for the integration (see docs/protocol.md)."""

    def __init__(self) -> None:
        self.password = PASSWORD
        self.scenario = "2"
        self.not_ready: dict[str, list[str]] = {}  # partition id -> zone labels
        self.calls: list[tuple[str, str | None, str | None]] = []
        self.partitions = [
            {"lb": "Garage         ", "am": "4", "st": "1", "mm": "0", "id": "0"},
            {"lb": "House          ", "am": "4", "st": "1", "mm": "1", "id": "1"},
        ]
        self.zones = [
            {"lb": "Kitchen   ", "tl": "0", "st": "1", "mm": "0", "by": "1", "id": "0"},
            {"lb": "Window    ", "tl": "1", "st": "2", "mm": "0", "by": "1", "id": "1"},
        ]
        self.outputs = [{"lb": "Siren     ", "tl": "20", "st": "0", "t": "0", "id": "0"}]

    def _reply(self, mod: str, par: str | None) -> Any:
        if mod == "sce":
            if par == "now":
                return {"lb": "Away", "id": self.scenario}
            return {"sce": [{"lb": "Home", "id": "0"}, {"lb": "Away", "id": "2"}]}
        if mod == "part":
            return {"part": self.partitions}
        if mod == "zone":
            return {"zone": self.zones}
        if mod == "cmd":
            return {"cmd": self.outputs}
        if mod == "tmr":
            return {"tmr": [{"lb": "Timer 1  ", "st": "0", "id": "0"}]}
        if mod == "fau":
            return {"fau": "0", "vcc": "13,8"}
        if mod == "gsm":
            return {}
        if mod == "log":
            return {
                "log": [
                    {
                        "id": "10",
                        "dt": "23/10/2026 17:35:00",
                        "ty": "Valid key   ",
                        "ag": "Bob   ",
                        "lo": "Reader  ",
                        "al": [{"id": "0", "lb": "Garage   "}],
                    }
                ]
            }
        if mod == "nrza":
            return {"nrz": [{"lb": z} for z in self.not_ready.get(par or "", [])]}
        if mod == "nrzs":
            return {"nrz": []}
        return {}

    async def handle(self, request: web.Request) -> web.Response:
        data = await request.post()
        mod, par, act = data.get("mod"), data.get("par"), data.get("act")
        if mod == "auth":
            ok = (data.get("user"), data.get("pass"), data.get("code")) == (
                USER,
                self.password,
                CODE,
            )
            body = (
                f"<div id='msg_content' qindex='0' tk='{TOKEN}'>ACK</div>"
                if ok
                else "<div id='msg_content'>NACK</div>"
            )
            return web.Response(text=body, content_type="text/html")
        if data.get("tk") != TOKEN:
            return web.Response(text="<html>login</html>", content_type="text/html")
        if mod and mod.startswith("do_"):
            self.calls.append((mod, par, act))
            self._apply(mod, par, act)
            return web.json_response({mod: par})
        return web.json_response(self._reply(mod or "", par))

    def _apply(self, mod: str, par: str | None, act: str | None) -> None:
        if mod == "do_sce":
            self.scenario = str(par)
        elif mod == "do_part":
            for p in self.partitions:
                if p["id"] == par:
                    p["am"] = str(act)
                    if act == "5":
                        p["mm"] = "0"
        elif mod == "do_cmd":
            for o in self.outputs:
                if o["id"] == par:
                    o["st"] = str(act)
        elif mod == "do_zone":
            for z in self.zones:
                if z["id"] == par:
                    z["by"] = "0" if act == "1" else "1"

    def commands(self, mod: str) -> list[tuple[str | None, str | None]]:
        return [(p, a) for m, p, a in self.calls if m == mod]


def _make_app(panel: FakePanel) -> web.Application:
    app = web.Application()
    app.router.add_post("/cgi-bin/web.cgi", panel.handle)

    async def firmware(_: web.Request) -> web.Response:
        return web.Response(text="6.01 00515")

    async def version(_: web.Request) -> web.Response:
        return web.Response(text="<html><body>SmartLAN/G v. 6.12</body></html>")

    app.router.add_get("/sw_str_panel", firmware)
    app.router.add_get("/version.html", version)
    return app


@pytest.fixture(autouse=True)
def _enable_custom_integrations(enable_custom_integrations: None, socket_enabled: None) -> None:
    """Load custom_components/ of this repository and allow the localhost panel server."""


@pytest.fixture
def panel() -> FakePanel:
    return FakePanel()


@pytest.fixture
async def panel_port(panel: FakePanel, aiohttp_server) -> int:
    server = await aiohttp_server(_make_app(panel))
    return server.port


@pytest.fixture
def entry_data(panel_port: int) -> dict[str, Any]:
    return {
        "host": "127.0.0.1",
        "port": panel_port,
        "username": USER,
        "password": PASSWORD,
        CONF_CODE: CODE,
    }


@pytest.fixture
def make_entry(entry_data):
    def _make(**kwargs: Any) -> MockConfigEntry:
        return MockConfigEntry(
            domain=DOMAIN,
            data=entry_data,
            unique_id=f"127.0.0.1:{entry_data['port']}",
            **kwargs,
        )

    return _make
