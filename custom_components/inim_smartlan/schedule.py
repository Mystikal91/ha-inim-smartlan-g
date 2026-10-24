"""Per-key poll scheduling, without Home Assistant dependencies."""

from __future__ import annotations


class PollSchedule:
    """Tells which data groups are due, given a coordinator tick shorter than their interval.

    `slack` avoids skipping a whole tick when it fires a few ms before the interval elapsed.
    """

    def __init__(self, slack: float = 1.0) -> None:
        self._slack = slack
        self._last: dict[str, float] = {}

    def due(self, key: str, interval: float, now: float) -> bool:
        last = self._last.get(key)
        return last is None or now - last >= interval - self._slack

    def mark(self, key: str, now: float) -> None:
        self._last[key] = now

    def invalidate(self, *keys: str) -> None:
        for key in keys:
            self._last.pop(key, None)
