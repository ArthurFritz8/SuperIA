"""Lightweight local metrics (in-memory).

Goals:
- zero external deps
- safe defaults (no network)
- low overhead
- easy to snapshot into runlog

This is not intended to be a full tracing system.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any


@dataclass
class Timer:
    start: float


class Metrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[str, int] = {}
        self._timings_ms_sum: dict[str, float] = {}
        self._timings_ms_count: dict[str, int] = {}

    def inc(self, name: str, value: int = 1) -> None:
        if not name:
            return
        with self._lock:
            self._counters[name] = int(self._counters.get(name, 0)) + int(value)

    def timer(self) -> Timer:
        return Timer(start=time.perf_counter())

    def observe_ms(self, name: str, t: Timer) -> None:
        if not name:
            return
        elapsed_ms = (time.perf_counter() - float(t.start)) * 1000.0
        with self._lock:
            self._timings_ms_sum[name] = float(self._timings_ms_sum.get(name, 0.0)) + float(elapsed_ms)
            self._timings_ms_count[name] = int(self._timings_ms_count.get(name, 0)) + 1

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            timings: dict[str, dict[str, float]] = {}
            for name, total in self._timings_ms_sum.items():
                count = int(self._timings_ms_count.get(name, 0))
                if count <= 0:
                    continue
                timings[name] = {
                    "count": float(count),
                    "sum_ms": float(total),
                    "avg_ms": float(total) / float(count),
                }
            return {
                "counters": dict(self._counters),
                "timings_ms": timings,
            }


_NOOP = Metrics()


def get_noop_metrics() -> Metrics:
    return _NOOP
