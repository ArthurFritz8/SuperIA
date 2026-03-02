"""Screenshot local (mss + Pillow).

Rationale:
- Screenshot é a base para visão computacional e para "ver" interfaces.
- `mss` é rápido e funciona bem no Windows.

Guardrails:
- Salva apenas em path relativo
- Por padrão, sobrescreve um único arquivo: data/screenshots/latest.png
- Não envia imagem para a internet (isso será parte de um módulo VLM separado)
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
import sys

from omniscia.core.tools import ToolRegistry, ToolSpec
from omniscia.core.types import ToolResult


def register_vision_tools(registry: ToolRegistry) -> None:
    registry.register(
        ToolSpec(
            name="screen.screenshot",
            description=(
                "Tira screenshot da tela principal e salva PNG (path relativo). "
                "Por padrão sobrescreve data/screenshots/latest.png."
            ),
            risk="MEDIUM",
            fn=_screen_screenshot,
        )
    )


def _screen_screenshot(args: dict[str, Any]) -> ToolResult:
    try:
        import mss
        from PIL import Image
    except Exception as exc:  # noqa: BLE001
        return ToolResult(status="error", error=f"deps ausentes (mss/pillow): {exc}")

    # path relativo (workspace) por padrão; opcionalmente suporta known folders no Windows.
    # IMPORTANTE: por padrão sobrescrevemos um único arquivo para evitar acumular prints.
    raw_path = str(args.get("path", "")).strip().replace("\\", "/")
    if raw_path:
        path_str = raw_path
    else:
        path_str = "data/screenshots/latest.png"

    low = path_str.lower()
    is_known = low.startswith(("desktop:", "downloads:", "documents:"))

    if not low.endswith(".png"):
        return ToolResult(status="error", error="path deve terminar com .png")

    if is_known:
        if not sys.platform.startswith("win"):
            return ToolResult(status="error", error="known folders só são suportados no Windows")
        from omniscia.modules.os_control.filesystem import resolve_known_folder_prefixed_path

        out = resolve_known_folder_prefixed_path(path_str)
        # Preserve a normalized prefix form in the output (helps other tools).
        saved_label = path_str
    else:
        if path_str.startswith("/") or ":" in path_str:
            return ToolResult(status="error", error="path inválido (use path relativo)")
        out = Path(path_str)
        saved_label = path_str
    out.parent.mkdir(parents=True, exist_ok=True)

    try:
        out.parent.mkdir(parents=True, exist_ok=True)

        with mss.mss() as sct:
            monitor = sct.monitors[1]  # 1 = tela principal
            shot = sct.grab(monitor)
            img = Image.frombytes("RGB", shot.size, shot.rgb)
            img.save(out, format="PNG")
        if raw_path:
            msg = f"saved screenshot: {saved_label}"
        else:
            msg = f"saved screenshot (overwrote): {saved_label}"
        return ToolResult(status="ok", output=msg)
    except Exception as exc:  # noqa: BLE001
        return ToolResult(status="error", error=str(exc))
