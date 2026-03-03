"""Omni-Index: indexação de arquivos locais para memória vetorial (ChromaDB).

Design:
- Reutiliza `ChromaVectorMemory` (embeddings locais).
- Extrai texto de arquivos comuns (code/text). PDF é opt-in via `pypdf`.
- Mantém guardrails: ignora arquivos gigantes/binários e paths fora do workspace.

Isso é pensado para rodar em dois modos:
1) On-demand (tool `memory.index_paths`)
2) Daemon (watchdog) — ver `scripts/omni_index_daemon.py`
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any, Iterable


TEXT_EXTS = {
    ".py",
    ".md",
    ".txt",
    ".json",
    ".toml",
    ".yml",
    ".yaml",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".java",
    ".c",
    ".cpp",
    ".h",
    ".hpp",
    ".cs",
    ".go",
    ".rs",
    ".sql",
    ".ini",
}


def _sha256(s: str) -> str:
    h = hashlib.sha256()
    h.update(s.encode("utf-8", errors="ignore"))
    return h.hexdigest()


def _stable_file_id(path: Path, *, extra: str = "") -> str:
    try:
        st = path.stat()
        sig = f"{path.as_posix()}|{st.st_size}|{int(st.st_mtime)}|{extra}"
    except Exception:
        sig = f"{path.as_posix()}|{extra}"
    return _sha256(sig)[:28]


def _looks_binary(sample: bytes) -> bool:
    if not sample:
        return False
    # NUL byte is a strong signal.
    if b"\x00" in sample:
        return True
    # Heuristic: many non-text bytes.
    text = sum(1 for b in sample if 9 <= b <= 13 or 32 <= b <= 126)
    return (text / max(1, len(sample))) < 0.75


def extract_text_from_file(path: Path, *, max_chars: int = 60_000) -> str | None:
    suf = path.suffix.lower()
    if suf == ".pdf":
        try:
            from pypdf import PdfReader  # type: ignore

            reader = PdfReader(str(path))
            parts: list[str] = []
            for i, page in enumerate(reader.pages[:40]):
                try:
                    t = page.extract_text() or ""
                except Exception:
                    t = ""
                t = t.strip()
                if t:
                    parts.append(f"[p{i+1}]\n{t}")
                if sum(len(x) for x in parts) > max_chars:
                    break
            out = "\n\n".join(parts).strip()
            return out[:max_chars] if out else None
        except Exception:
            return None

    if suf not in TEXT_EXTS:
        return None

    try:
        with path.open("rb") as f:
            sample = f.read(4096)
            if _looks_binary(sample):
                return None
        text = path.read_text(encoding="utf-8", errors="ignore")
        text = (text or "").strip()
        if not text:
            return None
        if len(text) > max_chars:
            text = text[:max_chars] + "\n... [truncado]"
        return text
    except Exception:
        return None


def iter_files_under(paths: list[str], *, max_file_mb: int = 4) -> Iterable[Path]:
    max_bytes = int(max_file_mb) * 1024 * 1024

    for raw in paths:
        p = Path(raw).expanduser()
        if not p.exists():
            continue
        if p.is_file():
            yield p
            continue

        for fp in p.rglob("*"):
            try:
                if not fp.is_file():
                    continue
                if fp.name.startswith("."):
                    continue
                if fp.stat().st_size > max_bytes:
                    continue
            except Exception:
                continue
            yield fp


def index_paths_to_vector(
    *,
    vm,
    paths: list[str],
    source: str = "omni-index",
    workspace_root: str | None = None,
) -> tuple[int, int]:
    """Index paths into ChromaVectorMemory.

    Returns (seen_files, indexed_items).
    """

    root = Path(workspace_root or os.getcwd()).resolve()

    seen = 0
    indexed = 0
    for fp in iter_files_under(paths):
        seen += 1
        try:
            abs_fp = fp.resolve()
            # Guardrail: stay under workspace root by default.
            abs_fp.relative_to(root)
        except Exception:
            continue

        text = extract_text_from_file(abs_fp)
        if not text:
            continue

        item_id = _stable_file_id(abs_fp)
        meta: dict[str, Any] = {
            "kind": "file",
            "source": source,
            "path": abs_fp.as_posix(),
        }
        vm.upsert(item_id=item_id, text=f"FILE: {abs_fp.as_posix()}\n\n{text}", meta=meta)
        indexed += 1

    return seen, indexed
