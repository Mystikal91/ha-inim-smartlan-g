"""Async client for the INIM SmartLAN/G local web interface (unofficial).

This module has no Home Assistant dependency so it can be tested and reused
on its own (see tools/probe.py for a stdlib-only diagnostic script).
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import Iterable
from datetime import datetime
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

CGI_PATH = "/cgi-bin/web.cgi"
MASK_WORDS = 7  # the web UI sends 7 hex words separated by commas
MASK_BITS = 32  # assumed bits per word (8 hex digits) - verified for word 0


class InimError(Exception):
    """Base error."""


class InimConnectionError(InimError):
    """Panel unreachable or HTTP error."""


class InimAuthError(InimError):
    """Login refused."""


class InimResponseError(InimError):
    """Unexpected / non-JSON response."""


def build_mask(indexes: Iterable[int | str]) -> str:
    """Build the bit mask the web UI sends in `par` for zone/cmd polling."""
    words = [0] * MASK_WORDS
    for idx in indexes:
        word, bit = divmod(int(idx), MASK_BITS)
        if word >= MASK_WORDS:
            raise ValueError(f"index {idx} does not fit in the mask")
        words[word] |= 1 << bit
    return ",".join(f"{w:08x}" for w in words)


_TAG_RE = re.compile(r"""(<div[^>]*id\s*=\s*['"]msg_content['"][^>]*>)(.*?)</div>""", re.S | re.I)
_TK_RE = re.compile(r"""\btk\s*=\s*['"]([^'"]+)['"]""")
_Q_RE = re.compile(r"""\bqindex\s*=\s*['"]([^'"]*)['"]""")


def parse_login(html: str) -> tuple[str, str]:
    """Return (tk, qindex) from the login response or raise InimAuthError."""
    match = _TAG_RE.search(html)
    if not match or match.group(2).strip() != "ACK":
        raise InimAuthError("Login refused by the panel")
    tk = _TK_RE.search(match.group(1))
    if not tk:
        raise InimAuthError("Login response without token")
    q = _Q_RE.search(match.group(1))
    return tk.group(1), (q.group(1) if q else "0")


def clean(value: Any) -> str | None:
    """Labels are padded with spaces; '--' means 'not available'."""
    if value is None:
        return None
    text = str(value).strip()
    return None if text in ("", "--") else text


def to_int(value: Any) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def to_float(value: Any) -> float | None:
    try:
        return float(str(value).strip().replace(",", "."))
    except (TypeError, ValueError):
        return None


def parse_event_time(value: Any) -> datetime | None:
    """Parse the panel log time (DD/MM/YYYY HH:MM:SS, panel local time, no zone)."""
    try:
        return datetime.strptime(str(value).strip(), "%d/%m/%Y %H:%M:%S")
    except ValueError:
        return None


def _rows(data: Any, key: str) -> list[dict[str, Any]]:
    if isinstance(data, dict) and isinstance(data.get(key), list):
        return [r for r in data[key] if isinstance(r, dict)]
    return []


def _try_json(text: str) -> Any | None:
    try:
        return json.loads(text.strip())
    except ValueError:
        return None


class InimClient:
    """Talks to the SmartLAN/G web server. Requests are serialised."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        port: int,
        username: str,
        password: str,
        code: str,
        timeout: float = 30,
    ) -> None:
        self._session = session
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._code = code
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._tk: str | None = None
        self._qindex = "0"
        self._lock = asyncio.Lock()

    @property
    def base_url(self) -> str:
        return f"http://{self._host}:{self._port}"

    # -- transport ---------------------------------------------------------
    async def _post(self, body: dict[str, str]) -> str:
        try:
            async with self._session.post(
                self.base_url + CGI_PATH, data=body, timeout=self._timeout
            ) as resp:
                if resp.status != 200:
                    raise InimConnectionError(f"HTTP {resp.status}")
                return await resp.text(errors="replace")
        except (aiohttp.ClientError, TimeoutError) as err:
            raise InimConnectionError(str(err) or type(err).__name__) from err

    async def _login(self) -> None:
        html = await self._post(
            {
                "user": self._username,
                "pass": self._password,
                "mod": "auth",
                "code": self._code,
            }
        )
        self._tk, self._qindex = parse_login(html)

    async def async_login(self) -> None:
        async with self._lock:
            await self._login()

    async def async_request(
        self, mod: str, par: str | int | None = None, act: str | int | None = None
    ) -> Any:
        """Send one command; re-login once if the reply is not JSON."""
        async with self._lock:
            for _ in range(2):
                if self._tk is None:
                    await self._login()
                body = {"tk": self._tk, "qindex": self._qindex, "mod": mod}
                if par is not None:
                    body["par"] = str(par)
                if act is not None:
                    body["act"] = str(act)
                data = _try_json(await self._post(body))
                if data is not None:
                    return data
                _LOGGER.debug("Non-JSON reply for mod=%s, logging in again", mod)
                self._tk = None
            raise InimResponseError(f"Invalid reply for mod={mod}")

    # -- info ---------------------------------------------------------------
    async def async_get_panel_info(self) -> dict[str, str]:
        info: dict[str, str] = {}
        try:
            async with self._session.get(
                self.base_url + "/sw_str_panel", timeout=self._timeout
            ) as resp:
                parts = (await resp.text(errors="replace")).split()
            if parts:
                info["firmware"] = parts[0]
            if len(parts) > 1 and parts[1].isdigit():
                info["model_code"] = str(int(parts[1]))
            async with self._session.get(
                self.base_url + "/version.html", timeout=self._timeout
            ) as resp:
                html = await resp.text(errors="replace")
            text = " ".join(re.sub(r"<[^>]+>", " ", html).split())
            if text:
                info["smartlan"] = text
        except (aiohttp.ClientError, TimeoutError) as err:
            _LOGGER.debug("Panel info not available: %s", err)
        return info

    # -- reads ----------------------------------------------------------------
    async def async_get_scenarios(self) -> list[dict[str, Any]]:
        return _rows(await self.async_request("sce"), "sce")

    async def async_get_current_scenario(self) -> dict[str, Any]:
        data = await self.async_request("sce", "now")
        return data if isinstance(data, dict) else {}

    async def async_get_partitions(self) -> list[dict[str, Any]]:
        return _rows(await self.async_request("part"), "part")

    async def async_get_zones(self, mask: str | None = None) -> list[dict[str, Any]]:
        return _rows(await self.async_request("zone", mask), "zone")

    async def async_get_outputs(self) -> list[dict[str, Any]]:
        return _rows(await self.async_request("cmd"), "cmd")

    async def async_get_timers(self) -> list[dict[str, Any]]:
        return _rows(await self.async_request("tmr"), "tmr")

    async def async_get_faults(self) -> dict[str, Any]:
        data = await self.async_request("fau")
        if not isinstance(data, dict):
            raise InimResponseError("Invalid reply for mod=fau")
        return {
            "fault_code": to_int(data.get("fau")),
            "system_voltage": to_float(data.get("vcc")),
        }

    async def async_get_gsm(self) -> dict[str, Any] | None:
        data = await self.async_request("gsm")
        if not isinstance(data, dict) or not any(k in data for k in ("gop", "gpw", "fwv")):
            return None
        return {
            "voltage": to_float(data.get("vcc")),
            "firmware": clean(data.get("fwv")),
            "operator": clean(data.get("gop")),
            "signal": to_int(data.get("gpw")),
            "credit": clean(data.get("cre")),
        }

    async def async_get_log(self, lines: int = 10) -> list[dict[str, Any]]:
        return _rows(await self.async_request("log", lines), "log")

    async def async_get_last_event(self) -> dict[str, Any] | None:
        """Most recent log entry (highest id), or None if the log is empty."""
        rows = [r for r in await self.async_get_log(1) if to_int(r.get("id")) is not None]
        if not rows:
            return None
        row = max(rows, key=lambda r: to_int(r["id"]) or 0)
        return {
            "id": to_int(row["id"]),
            "time": parse_event_time(row.get("dt")),
            "type": clean(row.get("ty")),
            "agent": clean(row.get("ag")),
            "location": clean(row.get("lo")),
            "partitions": [
                n for a in row.get("al") or [] if isinstance(a, dict) and (n := clean(a.get("lb")))
            ],
        }

    async def async_get_not_ready_zones(
        self, kind: str, target_id: str | int, arm_code: int = 0
    ) -> list[str]:
        """Labels of the zones that are not ready before arming (the web UI pre-check).

        kind "partition": target_id is the partition id, arm_code the arming code
        (1 away, 2 stay, 3 instant); the panel wants `arm_code - 1`.
        kind "scenario": target_id is the scenario id.
        """
        if kind == "partition":
            data = await self.async_request("nrza", target_id, arm_code - 1)
        else:
            data = await self.async_request("nrzs", target_id, 0)
        return [n for r in _rows(data, "nrz") if (n := clean(r.get("lb")))]

    # -- writes ---------------------------------------------------------------
    async def async_set_scenario(self, scenario_id: str | int) -> Any:
        return await self.async_request("do_sce", scenario_id)

    async def async_set_partition(self, partition_id: str | int, code: int) -> Any:
        return await self.async_request("do_part", partition_id, code)

    async def async_set_zone_excluded(self, zone_id: str | int, excluded: bool) -> Any:
        """Exclude (act=1) or include (act=0) a zone; values taken from the web UI buttons."""
        return await self.async_request("do_zone", zone_id, 1 if excluded else 0)

    async def async_set_output(self, output_id: str | int, on: bool) -> Any:
        return await self.async_request("do_cmd", output_id, 1 if on else 0)
