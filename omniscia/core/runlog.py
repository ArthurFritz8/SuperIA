"""Run logging (JSONL) for observability and debugging.

This is separate from `data/memory/events.jsonl`:
- memory is a single timeline
- runlog is per-run, easier to inspect/replay/debug

Offline, local-only.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _now_stamp() -> str:
    return time.strftime("%Y%m%d_%H%M%S", time.localtime())


def _redact(obj: Any) -> Any:
    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for k, v in obj.items():
            kk = str(k).lower()
            if any(s in kk for s in ("key", "token", "password", "secret")):
                out[k] = "***"
            else:
                out[k] = _redact(v)
        return out
    if isinstance(obj, list):
        return [_redact(x) for x in obj]
    if isinstance(obj, str) and len(obj) > 4000:
        return obj[:4000] + "... [truncado]"
    return obj


@dataclass(frozen=True)
class RunInfo:
    run_id: str
    path: str


class RunLogger:
    def __init__(self, *, base_dir: str = "data/runs") -> None:
        self.base = Path(base_dir)
        self.base.mkdir(parents=True, exist_ok=True)

    def start(self, *, intent: str) -> RunInfo:
        rid = f"{_now_stamp()}_{(intent or 'run')[:40].replace(' ', '_')}"
        path = self.base / f"{rid}.jsonl"
        return RunInfo(run_id=rid, path=str(path))

    def append(self, run: RunInfo, kind: str, payload: dict[str, Any]) -> None:
        p = Path(run.path)
        line = json.dumps(
            {
                "ts": time.time(),
                "kind": str(kind),
                "payload": _redact(payload or {}),
            },
            ensure_ascii=False,
        )
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
