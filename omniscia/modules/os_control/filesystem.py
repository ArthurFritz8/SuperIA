"""Ferramentas de filesystem (guardrailed).

Rationale:
- Um agente que manipula arquivos precisa de guardrails fortes.

Guardrails principais:
- Apenas paths relativos (sem drive letter, sem "/", sem ".." escapando)
- Operações destrutivas (delete) devem ser marcadas como CRITICAL no plano (HITL)

Nota:
- Neste MVP, o "workspace root" é o diretório atual do processo.
  Depois podemos fixar explicitamente via Settings.
"""

from __future__ import annotations

from pathlib import Path
import shutil
from typing import Any
import sys
import ctypes
from ctypes import wintypes

from omniscia.core.tools import ToolRegistry, ToolSpec
from omniscia.core.types import ToolResult


def register_filesystem_tools(registry: ToolRegistry) -> None:
    registry.register(
        ToolSpec(
            name="fs.list_dir",
            description="Lista arquivos/pastas em um path relativo",
            risk="LOW",
            fn=_fs_list_dir,
        )
    )
    registry.register(
        ToolSpec(
            name="fs.read_text",
            description="Lê arquivo texto (utf-8) em path relativo",
            risk="MEDIUM",
            fn=_fs_read_text,
        )
    )
    registry.register(
        ToolSpec(
            name="fs.delete",
            description="Apaga arquivo/pasta (recursivo) em path relativo (CRITICAL)",
            risk="CRITICAL",
            fn=_fs_delete,
        )
    )

    registry.register(
        ToolSpec(
            name="fs.mkdir",
            description="Cria diretório (mkdir -p) em path relativo",
            risk="LOW",
            fn=_fs_mkdir,
        )
    )

    registry.register(
        ToolSpec(
            name="os.mkdir",
            description=(
                "Cria diretório (mkdir -p) fora do workspace (Windows). "
                "Aceita path absoluto (ex: D:/Pasta) ou known_folder+name (desktop/downloads/documents)."
            ),
            risk="HIGH",
            fn=_os_mkdir,
        )
    )

    registry.register(
        ToolSpec(
            name="fs.copy",
            description="Copia arquivo/pasta (recursivo) em paths relativos (não sobrescreve por padrão)",
            risk="MEDIUM",
            fn=_fs_copy,
        )
    )

    registry.register(
        ToolSpec(
            name="fs.move",
            description="Move/renomeia arquivo/pasta em paths relativos (não sobrescreve por padrão)",
            risk="HIGH",
            fn=_fs_move,
        )
    )


def _safe_rel_path(raw: str) -> Path:
    path = (raw or "").strip().replace("\\", "/")
    if not path:
        raise ValueError("path vazio")
    if path.startswith("~") or "/~" in path or "~" in path.split("/"):
        raise ValueError("path não pode usar '~' (use path relativo ao workspace)")
    if path.startswith("/") or ":" in path:
        raise ValueError("path deve ser relativo ao workspace")

    p = Path(path)

    # Evita path traversal fora do workspace.
    if any(part == ".." for part in p.parts):
        raise ValueError("path não pode conter '..'")

    return p


def _fs_list_dir(args: dict[str, Any]) -> ToolResult:
    try:
        p = _safe_rel_path(str(args.get("path", ".")))
        if not p.exists():
            return ToolResult(status="error", error="path não existe")
        if not p.is_dir():
            return ToolResult(status="error", error="path não é diretório")

        items = []
        for child in sorted(p.iterdir(), key=lambda x: x.name.lower()):
            suffix = "/" if child.is_dir() else ""
            items.append(child.name + suffix)

        return ToolResult(status="ok", output="\n".join(items) if items else "(vazio)")
    except Exception as exc:  # noqa: BLE001
        return ToolResult(status="error", error=str(exc))


def _fs_read_text(args: dict[str, Any]) -> ToolResult:
    try:
        p = _safe_rel_path(str(args.get("path", "")))
        max_chars = int(args.get("max_chars", 8000) or 8000)
        if not p.exists() or not p.is_file():
            return ToolResult(status="error", error="arquivo não existe")

        text = p.read_text(encoding="utf-8", errors="replace")
        if len(text) > max_chars:
            text = text[:max_chars] + "\n... [truncado]"

        return ToolResult(status="ok", output=text)
    except Exception as exc:  # noqa: BLE001
        return ToolResult(status="error", error=str(exc))


def _fs_delete(args: dict[str, Any]) -> ToolResult:
    """Apaga arquivo ou pasta.

    Importante:
    - O HITL acontece antes da execução (no core), mas mantemos guardrails aqui também.
    - Não permitimos deletar '.' (workspace) por padrão.
    """

    try:
        p = _safe_rel_path(str(args.get("path", "")))
        if str(p) in {".", "./"}:
            return ToolResult(status="error", error="não é permitido apagar o workspace (.)")

        if not p.exists():
            return ToolResult(status="ok", output="(nada para apagar)")

        if p.is_dir():
            for child in sorted(p.rglob("*"), reverse=True):
                if child.is_file() or child.is_symlink():
                    child.unlink(missing_ok=True)
                elif child.is_dir():
                    child.rmdir()
            p.rmdir()
        else:
            p.unlink(missing_ok=True)

        return ToolResult(status="ok", output=f"deleted {p}")
    except Exception as exc:  # noqa: BLE001
        return ToolResult(status="error", error=str(exc))


def _fs_mkdir(args: dict[str, Any]) -> ToolResult:
    try:
        p = _safe_rel_path(str(args.get("path", "")))
        p.mkdir(parents=True, exist_ok=True)
        return ToolResult(status="ok", output=f"created dir {p}")
    except Exception as exc:  # noqa: BLE001
        return ToolResult(status="error", error=str(exc))


def _win_known_folder(name: str) -> Path:
    """Resolve Windows Known Folders reliably (supports OneDrive redirection)."""

    if not sys.platform.startswith("win"):
        raise RuntimeError("known_folder só é suportado no Windows")

    known = (name or "").strip().lower()

    # GUIDs from Windows Known Folder IDs
    folder_ids = {
        "desktop": "{B4BFCC3A-DB2C-424C-B029-7FE99A87C641}",
        "documents": "{FDD39AD0-238F-46AF-ADB4-6C85480369C7}",
        "downloads": "{374DE290-123F-4565-9164-39C4925E467B}",
    }
    if known not in folder_ids:
        raise ValueError("known_folder inválido (use: desktop, downloads, documents)")

    guid_str = folder_ids[known]

    class GUID(ctypes.Structure):
        _fields_ = [
            ("Data1", wintypes.DWORD),
            ("Data2", wintypes.WORD),
            ("Data3", wintypes.WORD),
            ("Data4", wintypes.BYTE * 8),
        ]

    import uuid

    u = uuid.UUID(guid_str)
    guid = GUID(
        u.fields[0],
        u.fields[1],
        u.fields[2],
        (wintypes.BYTE * 8)(*u.bytes[8:]),
    )

    p_path = wintypes.LPWSTR()
    SHGetKnownFolderPath = ctypes.windll.shell32.SHGetKnownFolderPath
    SHGetKnownFolderPath.argtypes = [ctypes.POINTER(GUID), wintypes.DWORD, wintypes.HANDLE, ctypes.POINTER(wintypes.LPWSTR)]
    SHGetKnownFolderPath.restype = wintypes.HRESULT

    hr = SHGetKnownFolderPath(ctypes.byref(guid), 0, 0, ctypes.byref(p_path))
    if hr != 0:
        raise RuntimeError(f"SHGetKnownFolderPath falhou (hr={hr})")

    try:
        return Path(p_path.value)
    finally:
        ctypes.windll.ole32.CoTaskMemFree(p_path)


def _safe_rel_subpath(raw: str) -> Path:
    """Relative subpath without drive/root/traversal. Used under known folders."""
    s = (raw or "").strip().strip('"').strip("'").replace("\\", "/")
    if not s:
        raise ValueError("name vazio")
    if s.startswith("/") or ":" in s:
        raise ValueError("name deve ser relativo")
    if s.startswith("~") or "/~" in s or "~" in s.split("/"):
        raise ValueError("name não pode usar '~'")
    p = Path(s)
    if any(part == ".." for part in p.parts):
        raise ValueError("name não pode conter '..'")
    return p


def _safe_abs_windows_path(raw: str) -> Path:
    s = (raw or "").strip().strip('"').strip("'").replace("/", "\\")
    if not s:
        raise ValueError("path vazio")
    if not sys.platform.startswith("win"):
        raise RuntimeError("os.mkdir (path absoluto) só é suportado no Windows")
    p = Path(s)
    if not p.is_absolute() or ":" not in s[:3]:
        raise ValueError("path deve ser absoluto (ex: D:\\Pasta)")
    if any(part == ".." for part in p.parts):
        raise ValueError("path não pode conter '..'")

    # Não permitir criar diretamente na raiz do drive (ex: D:\)
    if p == Path(p.anchor):
        raise ValueError("path inválido (não use a raiz do drive)")

    low = str(p).lower()
    # Bloqueios básicos de áreas sensíveis (não é uma lista exaustiva)
    blocked_prefixes = [
        "c:\\windows",
        "c:\\program files",
        "c:\\program files (x86)",
    ]
    if any(low.startswith(pref) for pref in blocked_prefixes):
        raise PermissionError("path não permitido (diretório do sistema)")

    return p


def _os_mkdir(args: dict[str, Any]) -> ToolResult:
    """Creates directories outside workspace with explicit guardrails."""

    try:
        known_folder = str(args.get("known_folder", "") or "").strip().lower()
        name = str(args.get("name", "") or "").strip()
        raw_path = str(args.get("path", "") or "").strip()

        target: Path

        # Option A: known_folder + name
        if known_folder:
            base = _win_known_folder(known_folder)
            sub = _safe_rel_subpath(name)
            target = (base / sub).resolve()
        else:
            # Option B: string path with optional prefix desktop:/...
            if raw_path.lower().startswith(("desktop:", "downloads:", "documents:")):
                prefix, rest = raw_path.split(":", 1)
                base = _win_known_folder(prefix)
                sub = _safe_rel_subpath(rest)
                target = (base / sub).resolve()
            else:
                target = _safe_abs_windows_path(raw_path)

        target.mkdir(parents=True, exist_ok=True)
        return ToolResult(status="ok", output=f"created dir {target}")
    except Exception as exc:  # noqa: BLE001
        return ToolResult(status="error", error=str(exc))


def _fs_copy(args: dict[str, Any]) -> ToolResult:
    """Copia arquivo ou pasta.

    Args:
    - src: path relativo (obrigatório)
    - dst: path relativo (obrigatório)
    - overwrite: bool (default False)
    """

    try:
        src = _safe_rel_path(str(args.get("src", "")))
        dst = _safe_rel_path(str(args.get("dst", "")))
        overwrite = bool(args.get("overwrite", False))

        if not src.exists():
            return ToolResult(status="error", error="src não existe")

        if dst.exists() and not overwrite:
            return ToolResult(status="error", error="dst já existe (use overwrite=true)")

        if src.is_dir():
            if dst.exists() and overwrite:
                # Remove destino antes de copiar.
                if dst.is_dir():
                    shutil.rmtree(dst)
                else:
                    dst.unlink(missing_ok=True)
            shutil.copytree(src, dst)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            if dst.exists() and overwrite:
                dst.unlink(missing_ok=True)
            shutil.copy2(src, dst)

        return ToolResult(status="ok", output=f"copied {src} -> {dst}")
    except Exception as exc:  # noqa: BLE001
        return ToolResult(status="error", error=str(exc))


def _fs_move(args: dict[str, Any]) -> ToolResult:
    """Move/renomeia arquivo ou pasta.

    Args:
    - src: path relativo (obrigatório)
    - dst: path relativo (obrigatório)
    - overwrite: bool (default False)
    """

    try:
        src = _safe_rel_path(str(args.get("src", "")))
        dst = _safe_rel_path(str(args.get("dst", "")))
        overwrite = bool(args.get("overwrite", False))

        if not src.exists():
            return ToolResult(status="error", error="src não existe")

        if dst.exists() and not overwrite:
            return ToolResult(status="error", error="dst já existe (use overwrite=true)")

        if dst.exists() and overwrite:
            if dst.is_dir():
                shutil.rmtree(dst)
            else:
                dst.unlink(missing_ok=True)

        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        return ToolResult(status="ok", output=f"moved {src} -> {dst}")
    except Exception as exc:  # noqa: BLE001
        return ToolResult(status="error", error=str(exc))
