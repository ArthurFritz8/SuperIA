"""Persistência de aprovações de HITL (opt-in).

Objetivo:
- Quando o usuário aprova uma ação (HITL), evitar pedir a mesma aprovação de novo.

Princípios:
- Somente para ferramentas consideradas persistíveis (allowlist).
- Nunca auto-aprovar/persistir ações CRITICAL.
- Armazenamento local e auditável em JSON no workspace.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stable_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


# Ferramentas que podem ter aprovação persistida.
# Regra: preferir ferramentas com impacto controlado e sem efeitos destrutivos.
_PERSIST_PREFIXES = (
    "vscode.",
)

_PERSIST_EXACT = {
    "os.open_app",
    "os.open_url",
    "os.open_explorer",
    "win.focus_window",
    "win.list_windows",
}

# Ferramentas explicitamente não persistíveis.
_DENY_PREFIXES = (
    "fs.",
    "gui.",
    "screen.click_text",
    "ui.",
)

_DENY_EXACT = {
    "dev.exec",
    "dev.create_tool",
    "dev.genesis",
    "fs.delete",
    "write_file",
}


def is_tool_persistable(tool_name: str) -> bool:
    t = (tool_name or "").strip()
    if not t:
        return False
    if t in _DENY_EXACT:
        return False
    if any(t.startswith(p) for p in _DENY_PREFIXES):
        return False
    if t in _PERSIST_EXACT:
        return True
    if any(t.startswith(p) for p in _PERSIST_PREFIXES):
        return True
    return False


def approval_key(tool_name: str, args: dict[str, Any]) -> str:
    """Compute a stable approval key for a tool call.

    Keys are intentionally coarse-grained to avoid overfitting to noisy args.
    """

    t = (tool_name or "").strip()
    a = args or {}

    if t == "os.open_app":
        app = str(a.get("app", "") or "").strip().lower()
        return f"{t}:app={app or '*'}"

    if t in {"vscode.install_extension", "vscode.uninstall_extension"}:
        ext = str(a.get("extension_id", "") or "").strip().lower()
        return f"{t}:id={ext or '*'}"

    if t == "vscode.open_file":
        path = str(a.get("path", "") or "").strip().replace("\\", "/")
        return f"{t}:path={path or '*'}"

    if t in {"vscode.settings_update", "vscode.settings_get", "vscode.settings_read"}:
        return f"{t}"

    if t in {"vscode.extensions_read", "vscode.extensions_update"}:
        return f"{t}"

    # Default: tool-level approval
    return t


@dataclass
class ApprovalEntry:
    key: str
    created_at: str


class ApprovalStore:
    def __init__(self, path: str = "data/hitl_approvals.json") -> None:
        self.path = Path(path)
        self._keys: set[str] = set()

    def load(self) -> None:
        try:
            if not self.path.exists():
                self._keys = set()
                return
            data = json.loads(self.path.read_text(encoding="utf-8", errors="replace"))
            entries = (data or {}).get("entries") if isinstance(data, dict) else None
            out: set[str] = set()
            if isinstance(entries, list):
                for e in entries:
                    if isinstance(e, dict):
                        k = str(e.get("key", "") or "").strip()
                        if k:
                            out.add(k)
                    elif isinstance(e, str):
                        k = e.strip()
                        if k:
                            out.add(k)
            self._keys = out
        except Exception:
            self._keys = set()

    def save(self) -> None:
        payload = {
            "version": 1,
            "updated_at": _now_iso(),
            "entries": [{"key": k, "created_at": _now_iso()} for k in sorted(self._keys)],
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(_stable_json(payload), encoding="utf-8")

    def list_keys(self) -> list[str]:
        return sorted(self._keys)

    def reset(self) -> None:
        self._keys = set()
        try:
            if self.path.exists():
                self.path.unlink()
        except Exception:
            # best-effort
            pass

    def revoke(self, keys: Iterable[str]) -> int:
        """Remove explicit approval keys. Returns number removed."""
        before = len(self._keys)
        for k in keys:
            kk = (k or "").strip()
            if kk:
                self._keys.discard(kk)
        return max(0, before - len(self._keys))

    def revoke_where_contains(self, needle: str) -> int:
        """Remove any approval keys containing a substring (case-insensitive)."""
        n = (needle or "").strip().casefold()
        if not n:
            return 0
        to_remove = [k for k in self._keys if n in k.casefold()]
        return self.revoke(to_remove)

    def allow(self, keys: Iterable[str]) -> int:
        before = len(self._keys)
        for k in keys:
            kk = (k or "").strip()
            if kk:
                self._keys.add(kk)
        return max(0, len(self._keys) - before)

    def is_allowed(self, key: str) -> bool:
        return (key or "").strip() in self._keys

    def is_allowed_all(self, keys: Iterable[str]) -> bool:
        for k in keys:
            if not self.is_allowed(k):
                return False
        return True

    def keys_for_calls(self, calls: list[dict[str, Any]] | None) -> list[str]:
        out: list[str] = []
        for c in calls or []:
            try:
                tool = str(c.get("tool_name", "") or "").strip()
                args = c.get("args")
                args_d = args if isinstance(args, dict) else {}
                if not is_tool_persistable(tool):
                    continue
                out.append(approval_key(tool, args_d))
            except Exception:
                continue
        # Dedup while preserving order
        seen: set[str] = set()
        dedup: list[str] = []
        for k in out:
            if k in seen:
                continue
            seen.add(k)
            dedup.append(k)
        return dedup
