"""UI Automation (Windows) via `uiautomation`.

Objetivo:
- Alternativa ao PyAutoGUI "cego" quando o alvo é um app Windows com UIA.
- Encontra e interage com controles pelo "DOM" do Windows (árvore UIA).

Segurança:
- Ainda é automação com efeitos colaterais => HIGH (passa por HITL conforme config).
- Import lazy: se `uiautomation` não estiver instalado, as tools retornam erro claro.

Observações:
- Implementação best-effort e genérica. Apps baseados em canvas/web (ex: navegador) podem não expor controles úteis.
"""

from __future__ import annotations

import json
import sys
import time
from collections import deque
from typing import Any, Iterable

from omniscia.core.tools import ToolRegistry, ToolSpec
from omniscia.core.types import ToolResult


def register_ui_automation_tools(registry: ToolRegistry) -> None:
    registry.register(
        ToolSpec(
            name="ui.inspect",
            description=(
                "Inspeciona uma janela/controle via UIA e retorna resumo (sem clicar). "
                "Args: window_title_contains?, window_class?, max_depth?"
            ),
            risk="LOW",
            fn=_ui_inspect,
        )
    )

    registry.register(
        ToolSpec(
            name="ui.click",
            description=(
                "Encontra um controle via UIA e clica. "
                "Args: window_title_contains?, window_class?, control_name_contains, control_type?, max_depth?, timeout_s?"
            ),
            risk="HIGH",
            fn=_ui_click,
        )
    )

    registry.register(
        ToolSpec(
            name="ui.set_text",
            description=(
                "Encontra um controle (tipicamente Edit) via UIA e define texto. "
                "Args: window_title_contains?, window_class?, control_name_contains, text, max_depth?, timeout_s?"
            ),
            risk="HIGH",
            fn=_ui_set_text,
        )
    )

    registry.register(
        ToolSpec(
            name="ui.send_keys",
            description=(
                "Envia teclas via UIA para o app (best-effort). "
                "Args: keys, window_title_contains?, window_class?"
            ),
            risk="HIGH",
            fn=_ui_send_keys,
        )
    )


def _require_uia():
    if not sys.platform.startswith("win"):
        return None, "UIA só é suportado no Windows"
    try:
        import uiautomation as auto  # type: ignore

        return auto, None
    except Exception as exc:  # noqa: BLE001
        return None, f"uiautomation indisponível: {exc}"


def _control_summary(c) -> dict[str, Any]:  # noqa: ANN001
    try:
        rect = getattr(c, "BoundingRectangle", None)
        r = None
        if rect is not None:
            r = {
                "left": int(getattr(rect, "left", 0)),
                "top": int(getattr(rect, "top", 0)),
                "right": int(getattr(rect, "right", 0)),
                "bottom": int(getattr(rect, "bottom", 0)),
            }
        return {
            "name": str(getattr(c, "Name", "") or ""),
            "class": str(getattr(c, "ClassName", "") or ""),
            "type": str(getattr(c, "ControlTypeName", "") or ""),
            "rect": r,
        }
    except Exception:
        return {"name": "", "class": "", "type": "", "rect": None}


def _iter_descendants(root, *, max_depth: int) -> Iterable[tuple[int, Any]]:  # noqa: ANN001
    q: deque[tuple[int, Any]] = deque()
    q.append((0, root))
    while q:
        depth, node = q.popleft()
        yield depth, node
        if depth >= max_depth:
            continue
        try:
            children = list(node.GetChildren())  # type: ignore[attr-defined]
        except Exception:
            children = []
        for ch in children:
            q.append((depth + 1, ch))


def _find_window(auto, title_contains: str | None, class_name: str | None, *, timeout_s: float) -> Any | None:  # noqa: ANN001
    title_cf = (title_contains or "").strip().casefold()
    cls_cf = (class_name or "").strip().casefold()

    root = auto.GetRootControl()
    deadline = time.time() + float(timeout_s)
    while time.time() < deadline:
        try:
            windows = list(root.GetChildren())
        except Exception:
            windows = []

        best = None
        best_score = -1
        for w in windows:
            s = _control_summary(w)
            name_cf = (s.get("name") or "").casefold()
            class_cf = (s.get("class") or "").casefold()

            if title_cf and title_cf not in name_cf:
                continue
            if cls_cf and cls_cf != class_cf:
                continue

            score = 0
            if title_cf:
                score += len(title_cf)
            if cls_cf:
                score += 10
            if len(name_cf) > 0:
                score += 1

            if score > best_score:
                best = w
                best_score = score

        if best is not None:
            return best
        time.sleep(0.10)

    return None


def _find_control_in_window(
    auto,
    win,
    *,
    control_name_contains: str,
    control_type: str | None,
    max_depth: int,
) -> Any | None:  # noqa: ANN001
    needle = (control_name_contains or "").strip().casefold()
    tneedle = (control_type or "").strip().casefold()
    if not needle:
        return None

    best = None
    best_score = -1
    for depth, node in _iter_descendants(win, max_depth=max_depth):
        s = _control_summary(node)
        name_cf = (s.get("name") or "").casefold()
        typ_cf = (s.get("type") or "").casefold()
        if needle not in name_cf:
            continue
        if tneedle and tneedle != typ_cf:
            continue
        score = 100 - depth
        score += min(50, len(name_cf))
        if score > best_score:
            best = node
            best_score = score

    return best


def _ui_inspect(args: dict[str, Any]) -> ToolResult:
    auto, err = _require_uia()
    if auto is None:
        return ToolResult(status="error", error=err)

    window_title_contains = str(args.get("window_title_contains", "") or "").strip() or None
    window_class = str(args.get("window_class", "") or "").strip() or None
    max_depth = int(args.get("max_depth", 3) or 3)
    max_depth = max(1, min(12, max_depth))

    win = _find_window(auto, window_title_contains, window_class, timeout_s=2.5)
    if win is None:
        return ToolResult(status="error", error="janela não encontrada via UIA")

    # Summarize first N descendants.
    nodes: list[dict[str, Any]] = []
    for depth, node in _iter_descendants(win, max_depth=max_depth):
        s = _control_summary(node)
        s["depth"] = int(depth)
        nodes.append(s)
        if len(nodes) >= 60:
            break

    payload = {
        "window": _control_summary(win),
        "nodes": nodes,
    }
    return ToolResult(status="ok", output=json.dumps(payload, ensure_ascii=False, indent=2)[:2000])


def _ui_click(args: dict[str, Any]) -> ToolResult:
    auto, err = _require_uia()
    if auto is None:
        return ToolResult(status="error", error=err)

    window_title_contains = str(args.get("window_title_contains", "") or "").strip() or None
    window_class = str(args.get("window_class", "") or "").strip() or None
    control_name_contains = str(args.get("control_name_contains", "") or "").strip()
    control_type = str(args.get("control_type", "") or "").strip() or None
    timeout_s = float(args.get("timeout_s", 3.0) or 3.0)
    max_depth = int(args.get("max_depth", 8) or 8)
    max_depth = max(1, min(24, max_depth))

    if not control_name_contains:
        return ToolResult(status="error", error="informe control_name_contains")

    win = _find_window(auto, window_title_contains, window_class, timeout_s=timeout_s)
    if win is None:
        return ToolResult(status="error", error="janela não encontrada via UIA")

    try:
        win.SetFocus()  # type: ignore[attr-defined]
    except Exception:
        pass

    ctl = _find_control_in_window(
        auto,
        win,
        control_name_contains=control_name_contains,
        control_type=control_type,
        max_depth=max_depth,
    )
    if ctl is None:
        return ToolResult(status="error", error="controle não encontrado")

    try:
        ctl.SetFocus()  # type: ignore[attr-defined]
    except Exception:
        pass

    try:
        ctl.Click()  # type: ignore[attr-defined]
    except Exception as exc:  # noqa: BLE001
        return ToolResult(status="error", error=f"falha ao clicar via UIA: {exc}")

    return ToolResult(status="ok", output=json.dumps({"clicked": _control_summary(ctl)}, ensure_ascii=False))


def _ui_set_text(args: dict[str, Any]) -> ToolResult:
    auto, err = _require_uia()
    if auto is None:
        return ToolResult(status="error", error=err)

    window_title_contains = str(args.get("window_title_contains", "") or "").strip() or None
    window_class = str(args.get("window_class", "") or "").strip() or None
    control_name_contains = str(args.get("control_name_contains", "") or "").strip()
    text = str(args.get("text", "") or "")
    timeout_s = float(args.get("timeout_s", 3.0) or 3.0)
    max_depth = int(args.get("max_depth", 10) or 10)
    max_depth = max(1, min(24, max_depth))

    if not control_name_contains:
        return ToolResult(status="error", error="informe control_name_contains")

    win = _find_window(auto, window_title_contains, window_class, timeout_s=timeout_s)
    if win is None:
        return ToolResult(status="error", error="janela não encontrada via UIA")

    try:
        win.SetFocus()  # type: ignore[attr-defined]
    except Exception:
        pass

    ctl = _find_control_in_window(
        auto,
        win,
        control_name_contains=control_name_contains,
        control_type=None,
        max_depth=max_depth,
    )
    if ctl is None:
        return ToolResult(status="error", error="controle não encontrado")

    try:
        ctl.SetFocus()  # type: ignore[attr-defined]
    except Exception:
        pass

    # Prefer SetValue if present; fallback to SendKeys.
    try:
        if hasattr(ctl, "SetValue"):
            ctl.SetValue(text)  # type: ignore[attr-defined]
        else:
            auto.SendKeys("{Ctrl}a{Del}")
            auto.SendKeys(text)
    except Exception as exc:  # noqa: BLE001
        return ToolResult(status="error", error=f"falha ao set_text via UIA: {exc}")

    return ToolResult(status="ok", output=json.dumps({"set_text": _control_summary(ctl)}, ensure_ascii=False))


def _ui_send_keys(args: dict[str, Any]) -> ToolResult:
    auto, err = _require_uia()
    if auto is None:
        return ToolResult(status="error", error=err)

    keys = str(args.get("keys", "") or "")
    window_title_contains = str(args.get("window_title_contains", "") or "").strip() or None
    window_class = str(args.get("window_class", "") or "").strip() or None

    if not keys:
        return ToolResult(status="error", error="informe keys")

    if window_title_contains or window_class:
        win = _find_window(auto, window_title_contains, window_class, timeout_s=2.5)
        if win is None:
            return ToolResult(status="error", error="janela não encontrada via UIA")
        try:
            win.SetFocus()  # type: ignore[attr-defined]
        except Exception:
            pass

    try:
        auto.SendKeys(keys)
    except Exception as exc:  # noqa: BLE001
        return ToolResult(status="error", error=f"falha ao enviar teclas via UIA: {exc}")

    return ToolResult(status="ok", output="sent keys")
