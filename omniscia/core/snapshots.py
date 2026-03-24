"""Workspace snapshots (zip) for safe rollbacks.

Goals:
- Create a local snapshot before risky changes (best-effort).
- Allow listing and restoring snapshots.

Notes:
- Snapshots are stored under `data/snapshots/` by default.
- Restore is destructive and should be gated by HITL.
"""

from __future__ import annotations

import json
import os
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


_DEFAULT_EXCLUDES = (
    ".git/",
    ".venv/",
    "__pycache__/",
    ".pytest_cache/",
    ".ruff_cache/",
    "data/",  # keep runtime data (approvals/memory) out of code rollback by default
    "build/",
    "dist/",
    "omniscia.egg-info/",
)


def _now_stamp() -> str:
    return time.strftime("%Y%m%d_%H%M%S", time.localtime())


def _norm_rel(p: Path) -> str:
    return str(p).replace("\\", "/")


def _is_excluded(rel: str, *, exclude_prefixes: Iterable[str]) -> bool:
    r = (rel or "").replace("\\", "/")
    for pref in exclude_prefixes:
        pp = (pref or "").replace("\\", "/")
        if not pp:
            continue
        if r.startswith(pp):
            return True
    return False


@dataclass(frozen=True)
class SnapshotInfo:
    snapshot_id: str
    zip_path: str
    created_at: float
    label: str
    file_count: int


class SnapshotManager:
    def __init__(self, *, root_dir: str | Path | None = None, snapshots_dir: str = "data/snapshots") -> None:
        self.root = Path(root_dir) if root_dir is not None else Path.cwd().resolve()
        self.dir = (self.root / snapshots_dir).resolve()
        self.dir.mkdir(parents=True, exist_ok=True)

    def create(
        self,
        *,
        label: str = "auto",
        exclude_prefixes: Iterable[str] = _DEFAULT_EXCLUDES,
        max_file_mb: int = 10,
    ) -> SnapshotInfo:
        stamp = _now_stamp()
        snapshot_id = f"{stamp}_{label.strip().replace(' ', '_')[:40] or 'snapshot'}"
        zip_path = self.dir / f"{snapshot_id}.zip"

        root = self.root
        count = 0
        with zipfile.ZipFile(zip_path, mode="w", compression=zipfile.ZIP_DEFLATED) as z:
            for base, dirs, files in os.walk(root):
                base_p = Path(base)
                rel_base = _norm_rel(base_p.relative_to(root))
                if rel_base and not rel_base.endswith("/"):
                    rel_base = rel_base + "/"

                # Prune excluded dirs early
                pruned_dirs: list[str] = []
                for d in list(dirs):
                    rel_dir = rel_base + d + "/" if rel_base else d + "/"
                    if _is_excluded(rel_dir, exclude_prefixes=exclude_prefixes):
                        pruned_dirs.append(d)
                for d in pruned_dirs:
                    dirs.remove(d)

                for fn in files:
                    rel_file = rel_base + fn if rel_base else fn
                    if _is_excluded(rel_file, exclude_prefixes=exclude_prefixes):
                        continue
                    full = base_p / fn
                    try:
                        size = full.stat().st_size
                        if size > max_file_mb * 1024 * 1024:
                            continue
                        z.write(full, arcname=rel_file)
                        count += 1
                    except Exception:
                        continue

            meta = {
                "snapshot_id": snapshot_id,
                "created_at": time.time(),
                "label": label,
                "file_count": count,
                "root": str(root),
                "exclude_prefixes": list(exclude_prefixes),
            }
            z.writestr("__snapshot__.json", json.dumps(meta, ensure_ascii=False, indent=2))

        return SnapshotInfo(
            snapshot_id=snapshot_id,
            zip_path=str(zip_path),
            created_at=time.time(),
            label=label,
            file_count=count,
        )

    def list(self, *, limit: int = 20) -> list[SnapshotInfo]:
        files = sorted(self.dir.glob("*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
        out: list[SnapshotInfo] = []
        for p in files[: max(0, min(limit, 200))]:
            snap_id = p.stem
            out.append(
                SnapshotInfo(
                    snapshot_id=snap_id,
                    zip_path=str(p),
                    created_at=p.stat().st_mtime,
                    label="",
                    file_count=0,
                )
            )
        return out

    def restore(self, snapshot_id: str) -> str:
        snap = (snapshot_id or "").strip()
        if not snap:
            raise ValueError("snapshot_id vazio")

        zip_path = self.dir / (snap + ".zip")
        if not zip_path.exists():
            raise FileNotFoundError("snapshot não encontrado")

        root = self.root
        with zipfile.ZipFile(zip_path, mode="r") as z:
            for info in z.infolist():
                name = info.filename
                if name == "__snapshot__.json":
                    continue
                # Security: prevent zip-slip
                target = (root / name).resolve()
                target.relative_to(root)

            z.extractall(root)

        return f"restored {snap}"
