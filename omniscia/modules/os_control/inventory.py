"""Inventário do sistema (Windows).

Objetivo:
- Dar ao agente visibilidade do que está rodando (processos) e instalado (registro),
  sem depender de automação de tela.

Segurança:
- Somente leitura (LOW).
- Saída limitada por max_results.
"""

from __future__ import annotations

import csv
import json
import sys
import subprocess
from typing import Any

from omniscia.core.tools import ToolRegistry, ToolSpec
from omniscia.core.types import ToolResult


def register_inventory_tools(registry: ToolRegistry) -> None:
    registry.register(
        ToolSpec(
            name="os.list_processes",
            description=(
                "Lista processos rodando (Windows). Args: query?, max_results?. "
                "Retorna {image_name,pid,session_name,mem_kb}."
            ),
            risk="LOW",
            fn=_os_list_processes,
        )
    )

    registry.register(
        ToolSpec(
            name="os.list_installed_apps",
            description=(
                "Lista apps instalados via Registro do Windows (Uninstall keys). "
                "Args: query?, max_results?. Retorna {name,version,publisher}."
            ),
            risk="LOW",
            fn=_os_list_installed_apps,
        )
    )


def _os_list_processes(args: dict[str, Any]) -> ToolResult:
    if not sys.platform.startswith("win"):
        payload = {"processes": [], "count": 0, "note": "os.list_processes só tem resultado no Windows"}
        return ToolResult(status="ok", output=json.dumps(payload, ensure_ascii=False))

    query = str(args.get("query", "") or "").strip().casefold() or None
    max_results = int(args.get("max_results", 300) or 300)
    if max_results < 1:
        max_results = 1
    if max_results > 2000:
        max_results = 2000

    try:
        # CSV output is easier to parse reliably.
        res = subprocess.run(
            ["tasklist", "/fo", "csv", "/nh"],
            capture_output=True,
            text=True,
            timeout=6,
            check=False,
        )
    except Exception as exc:  # noqa: BLE001
        return ToolResult(status="error", error=f"falha executando tasklist: {exc}")

    text = (res.stdout or "").strip()
    if not text:
        payload = {"processes": [], "count": 0, "note": "tasklist sem saída"}
        return ToolResult(status="ok", output=json.dumps(payload, ensure_ascii=False))

    out: list[dict[str, Any]] = []
    try:
        reader = csv.reader(text.splitlines())
        for row in reader:
            if len(out) >= max_results:
                break
            if not row:
                continue
            # Typical: "Image Name","PID","Session Name","Session#","Mem Usage"
            image = (row[0] or "").strip().strip('"')
            pid_s = (row[1] or "").strip().strip('"') if len(row) > 1 else ""
            sess = (row[2] or "").strip().strip('"') if len(row) > 2 else ""
            mem = (row[4] or "").strip().strip('"') if len(row) > 4 else ""

            if query and query not in image.casefold():
                continue

            pid = 0
            try:
                pid = int(pid_s)
            except Exception:
                pid = 0

            mem_kb = None
            # e.g. "12,340 K"
            mem_norm = mem.replace(",", "").replace("K", "").replace("k", "").strip()
            if mem_norm:
                try:
                    mem_kb = int(mem_norm)
                except Exception:
                    mem_kb = None

            out.append(
                {
                    "image_name": image,
                    "pid": pid,
                    "session_name": sess,
                    "mem_kb": mem_kb,
                }
            )
    except Exception as exc:  # noqa: BLE001
        return ToolResult(status="error", error=f"falha parseando tasklist: {exc}")

    payload = {"query": query, "count": len(out), "processes": out}
    return ToolResult(status="ok", output=json.dumps(payload, ensure_ascii=False))


def _iter_uninstall_entries():
    import winreg

    roots = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall"),
    ]

    for hive, path in roots:
        try:
            with winreg.OpenKey(hive, path) as root:
                i = 0
                while True:
                    try:
                        sub = winreg.EnumKey(root, i)
                    except OSError:
                        break
                    i += 1
                    try:
                        with winreg.OpenKey(root, sub) as k:
                            yield k
                    except Exception:
                        continue
        except Exception:
            continue


def _reg_get_str(k, name: str) -> str:
    import winreg

    try:
        val, typ = winreg.QueryValueEx(k, name)
        if typ in (winreg.REG_SZ, winreg.REG_EXPAND_SZ):
            return str(val or "").strip()
        return str(val or "").strip()
    except Exception:
        return ""


def _os_list_installed_apps(args: dict[str, Any]) -> ToolResult:
    if not sys.platform.startswith("win"):
        payload = {"apps": [], "count": 0, "note": "os.list_installed_apps só tem resultado no Windows"}
        return ToolResult(status="ok", output=json.dumps(payload, ensure_ascii=False))

    query = str(args.get("query", "") or "").strip().casefold() or None
    max_results = int(args.get("max_results", 800) or 800)
    if max_results < 1:
        max_results = 1
    if max_results > 10000:
        max_results = 10000

    try:
        apps: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str]] = set()

        for k in _iter_uninstall_entries():
            name = _reg_get_str(k, "DisplayName")
            if not name:
                continue
            version = _reg_get_str(k, "DisplayVersion")
            publisher = _reg_get_str(k, "Publisher")

            if query and query not in name.casefold() and query not in publisher.casefold():
                continue

            key = (name.casefold(), version.casefold(), publisher.casefold())
            if key in seen:
                continue
            seen.add(key)

            apps.append({"name": name, "version": version or None, "publisher": publisher or None})
            if len(apps) >= max_results:
                break

        apps.sort(key=lambda a: (str(a.get("name") or "").casefold(), str(a.get("publisher") or "").casefold()))
        payload = {"query": query, "count": len(apps), "apps": apps}
        return ToolResult(status="ok", output=json.dumps(payload, ensure_ascii=False))
    except Exception as exc:  # noqa: BLE001
        return ToolResult(status="error", error=str(exc))
