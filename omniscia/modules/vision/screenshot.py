"""Screenshot local (mss + Pillow).

Rationale:
- Screenshot é a base para visão computacional e para "ver" interfaces.
- `mss` é rápido e funciona bem no Windows.

Guardrails:
- Salva apenas em path relativo (por padrão em data/screenshots/)
- Não envia imagem para a internet (isso será parte de um módulo VLM separado)
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from omniscia.core.tools import ToolRegistry, ToolSpec
from omniscia.core.types import ToolResult


def register_vision_tools(registry: ToolRegistry) -> None:
    registry.register(
        ToolSpec(
            name="screen.screenshot",
            description="Tira screenshot da tela principal e salva PNG (path relativo)",
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

    # path relativo; default com timestamp.
    raw_path = str(args.get("path", "")).strip().replace("\\", "/")
    if raw_path:
        path = raw_path
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = f"data/screenshots/screen_{ts}.png"

    if path.startswith("/") or ":" in path:
        return ToolResult(status="error", error="path inválido (use path relativo)")
    if not path.lower().endswith(".png"):
        return ToolResult(status="error", error="path deve terminar com .png")

    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)

    try:
        with mss.mss() as sct:
            monitor = sct.monitors[1]  # 1 = tela principal
            shot = sct.grab(monitor)
            img = Image.frombytes("RGB", shot.size, shot.rgb)
            img.save(out, format="PNG")
        return ToolResult(status="ok", output=f"saved screenshot: {path}")
    except Exception as exc:  # noqa: BLE001
        return ToolResult(status="error", error=str(exc))
