from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _data_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "data" / "router"


@lru_cache(maxsize=1)
def load_static_tools_block() -> str:
    """Load the static tools block from a data file.

    Best-effort: returns empty string on failure.
    """

    p = _data_dir() / "static_tools_block.txt"
    try:
        return p.read_text(encoding="utf-8").strip() + "\n"
    except Exception as exc:  # noqa: BLE001
        logger.debug("Failed to load %s: %s", p, exc)
        return ""


@lru_cache(maxsize=1)
def load_schema_hints() -> dict[str, str]:
    """Load schema hints map from a JSON file.

    Best-effort: returns empty dict on failure.
    """

    p = _data_dir() / "schema_hints.json"
    try:
        obj: Any = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(obj, dict):
            out: dict[str, str] = {}
            for k, v in obj.items():
                kk = str(k)
                vv = str(v)
                if kk.strip() and vv.strip():
                    out[kk.strip()] = vv
            return out
        return {}
    except Exception as exc:  # noqa: BLE001
        logger.debug("Failed to load %s: %s", p, exc)
        return {}
