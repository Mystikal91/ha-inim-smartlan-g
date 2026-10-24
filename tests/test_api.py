"""Offline test of api.py against a mock panel (no Home Assistant needed).

pip install aiohttp && python tests/test_api.py
"""

import asyncio
import importlib.util
import pathlib

import aiohttp
from aiohttp import web

spec = importlib.util.spec_from_file_location(
    "inim_api", pathlib.Path(__file__).parent.parent / "custom_components/inim_smartlan/api.py"
)
api = importlib.util.module_from_spec(spec)
spec.loader.exec_module(api)

spec2 = importlib.util.spec_from_file_location(
    "inim_schedule",
    pathlib.Path(__file__).parent.parent / "custom_components/inim_smartlan/schedule.py",
)
schedule = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(schedule)

STATE = {"tk": "A" * 32, "masks": []}
ZONES = [
    {"lb": "Kitchen   ", "st": "1", "mm": "0", "by": "1", "tl": str(t), "id": str(i)}
    for t, i in [(0, 0), (1, 1), (6, 6), (10, 20), (18, 33)]
]


async def cgi(request):
    d = await request.post()
    if d.get("mod") == "auth":
        if (d["user"], d["pass"], d["code"]) != ("u", "p", "c"):
            return web.Response(text="<div id='msg_content'>NACK</div>", content_type="text/html")
        return web.Response(
            text=f"<div id='msg_content' qindex='30' tk='{STATE['tk']}'>ACK</div>",
            content_type="text/html",
        )
    if d.get("tk") != STATE["tk"]:
        return web.Response(text="<html>login</html>", content_type="text/html")
    mod, par = d.get("mod"), d.get("par")
    if mod == "sce" and par == "now":
        return web.json_response({"lb": "Away    ", "id": "2"})
    if mod == "sce":
        return web.json_response({"sce": [{"lb": "Home", "id": "0"}, {"lb": "Away", "id": "2"}]})
    if mod == "zone":
        STATE["masks"].append(par)
        return web.json_response({"zone": ZONES})
    if mod == "fau":
        return web.json_response({"fau": "256", "vcc": "13,8"})
    if mod == "tmr":
        return web.json_response({"tmr": [{"lb": "Timer 1  ", "st": "0", "id": "0"}]})
    if mod == "log":
        return web.json_response(
            {
                "log": [
                    {"id": "9", "dt": "23/10/2026 17:34:47", "ty": "Old     ", "ag": "", "lo": ""},
                    {
                        "id": "10",
                        "dt": "23/10/2026 17:35:00",
                        "ty": "Valid key   ",
                        "ag": "Bob   ",
                        "lo": "Reader  ",
                        "al": [{"id": "0", "lb": "Perimeter "}],
                    },
                ]
            }
        )
    if mod == "do_part":
        STATE.setdefault("parts", []).append((par, d.get("act")))
        return web.json_response({"do_part": par})
    if mod == "nrza":
        STATE.setdefault("nrz", []).append((mod, par, d.get("act")))
        return web.json_response({"nrz": [{"lb": "Window   "}] if par == "1" else []})
    if mod == "nrzs":
        STATE.setdefault("nrz", []).append((mod, par, d.get("act")))
        return web.json_response({"nrz": []})
    if mod == "do_zone":
        STATE.setdefault("zones_set", []).append((par, d.get("act")))
        return web.json_response({"do_zone": par})
    if mod == "do_sce":
        return web.json_response({"do_sce": par})
    return web.json_response({})


async def main():
    sch = schedule.PollSchedule(slack=1.0)
    assert sch.due("a", 10, 100.0)  # never polled
    sch.mark("a", 100.0)
    assert not sch.due("a", 10, 105.0)
    assert sch.due("a", 10, 109.5)  # tick fired slightly early: still due
    assert sch.due("a", 10, 110.0)
    sch.invalidate("a")
    assert sch.due("a", 10, 100.5)
    assert (
        api.build_mask([0, 1, 2, 3, 4, 5, 6, 10, 11, 18])
        == "00040c7f,00000000,00000000,00000000,00000000,00000000,00000000"
    )
    assert api.build_mask([33]) == "00000000,00000002,00000000,00000000,00000000,00000000,00000000"
    for bad in ("<div id='msg_content'>NACK</div>", "<html></html>"):
        try:
            api.parse_login(bad)
            raise SystemExit("should fail")
        except api.InimAuthError:
            pass
    assert api.to_float("13,8") == 13.8 and api.clean("--") is None

    app = web.Application()
    app.router.add_post("/cgi-bin/web.cgi", cgi)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    async with aiohttp.ClientSession() as s:
        bad = api.InimClient(s, "127.0.0.1", port, "u", "WRONG", "c")
        try:
            await bad.async_login()
            raise SystemExit("bad login accepted")
        except api.InimAuthError:
            pass
        c = api.InimClient(s, "127.0.0.1", port, "u", "p", "c")
        await c.async_login()
        assert [x["id"] for x in await c.async_get_scenarios()] == ["0", "2"]
        assert (await c.async_get_current_scenario())["id"] == "2"
        zones = await c.async_get_zones()
        mask = api.build_mask(z["tl"] for z in zones)
        await c.async_get_zones(mask)
        assert STATE["masks"] == [None, mask], STATE["masks"]
        assert await c.async_get_faults() == {"fault_code": 256, "system_voltage": 13.8}
        assert [t["id"] for t in await c.async_get_timers()] == ["0"]
        ev = await c.async_get_last_event()
        assert ev["id"] == 10 and ev["type"] == "Valid key" and ev["agent"] == "Bob"
        assert ev["partitions"] == ["Perimeter"] and ev["time"].year == 2026, ev
        assert api.parse_event_time("garbage") is None
        await c.async_set_partition(1, 5)
        assert STATE["parts"] == [("1", "5")], STATE["parts"]
        assert await c.async_get_not_ready_zones("partition", 1, 1) == ["Window"]
        assert await c.async_get_not_ready_zones("partition", 0, 3) == []
        assert await c.async_get_not_ready_zones("scenario", 2) == []
        assert STATE["nrz"] == [
            ("nrza", "1", "0"),
            ("nrza", "0", "2"),
            ("nrzs", "2", "0"),
        ], STATE["nrz"]
        await c.async_set_zone_excluded(6, True)
        await c.async_set_zone_excluded("6", False)
        assert STATE["zones_set"] == [("6", "1"), ("6", "0")], STATE["zones_set"]
        # token rotated server side -> transparent re-login
        STATE["tk"] = "B" * 32
        assert (await c.async_get_current_scenario())["id"] == "2"
        assert (await c.async_set_scenario(0)) == {"do_sce": "0"}
    await runner.cleanup()
    print("ALL OK")


if __name__ == "__main__":
    asyncio.run(main())
