"""Autoplay do Chrome Dino (T-Rex) via screenshot + PyAutoGUI.

Objetivo:
- Atender pedidos do tipo "Void, joga o T-Rex" com uma automação simples.

Limitações (intencionais):
- Heurística: detecta obstáculos por pixels escuros em uma região à frente do dinossauro.
- Não é perfeito; depende de o jogo estar visível e com bom contraste.

Segurança:
- Esta tool pressiona teclas e pode clicar para focar a janela; deve ser usada com HITL.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from omniscia.core.tools import ToolRegistry, ToolSpec
from omniscia.core.types import ToolResult


def register_game_tools(registry: ToolRegistry) -> None:
    registry.register(
        ToolSpec(
            name="game.trex_autoplay",
            description=(
                "Joga automaticamente o jogo do dinossauro (T-Rex) pressionando space. "
                "Args: duration_s?, title_contains?, settle_ms?"
            ),
            risk="HIGH",
            fn=_trex_autoplay,
        )
    )


def _require_pyautogui():
    try:
        import pyautogui

        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.0
        return pyautogui, None
    except Exception as exc:  # noqa: BLE001
        return None, f"pyautogui indisponível: {exc}"


def _require_vision():
    try:
        import mss
        from PIL import Image

        return mss, Image, None
    except Exception as exc:  # noqa: BLE001
        return None, None, f"deps ausentes (mss/pillow): {exc}"


@dataclass(frozen=True)
class DinoCalib:
    dino_x: int
    baseline_y: int


def _grab_screen_gray(mss_mod, pil_image_mod):
    with mss_mod.mss() as sct:
        monitor = sct.monitors[1]
        shot = sct.grab(monitor)
        img = pil_image_mod.frombytes("RGB", shot.size, shot.rgb)
    return img.convert("L")


def _find_dino(gray) -> DinoCalib | None:
    """Tenta localizar o dinossauro.

    Heurística:
    - Procura pixels escuros na metade inferior e no primeiro terço horizontal.
    - Usa o menor x encontrado como dino_x.
    - Usa o maior y encontrado como baseline (linha do chão aproximada).
    """

    w, h = gray.size
    x0 = 0
    x1 = int(w * 0.33)
    y0 = int(h * 0.35)
    y1 = int(h * 0.85)

    px = gray.load()
    dark_thr = 120

    min_x = None
    max_y = None

    # Step para performance
    for y in range(y0, y1, 2):
        for x in range(x0, x1, 2):
            if px[x, y] < dark_thr:
                if min_x is None or x < min_x:
                    min_x = x
                if max_y is None or y > max_y:
                    max_y = y

    if min_x is None or max_y is None:
        return None

    # Dino costuma ficar um pouco acima do chão; baseline um pouco abaixo.
    return DinoCalib(dino_x=int(min_x), baseline_y=int(max_y))


def _count_dark_in_rect(gray, *, x0: int, y0: int, x1: int, y1: int) -> int:
    w, h = gray.size
    x0 = max(0, min(w - 1, int(x0)))
    x1 = max(0, min(w, int(x1)))
    y0 = max(0, min(h - 1, int(y0)))
    y1 = max(0, min(h, int(y1)))
    if x1 <= x0 or y1 <= y0:
        return 0

    px = gray.load()
    dark_thr = 120
    n = 0

    # Step para performance
    for y in range(y0, y1, 2):
        for x in range(x0, x1, 2):
            if px[x, y] < dark_thr:
                n += 1
    return n


def _trex_autoplay(args: dict[str, Any]) -> ToolResult:
    pyautogui, err = _require_pyautogui()
    if pyautogui is None:
        return ToolResult(status="error", error=err)

    mss_mod, pil_image_mod, verr = _require_vision()
    if mss_mod is None:
        return ToolResult(status="error", error=verr)

    duration_s = float(args.get("duration_s", 30.0) or 30.0)
    if duration_s < 3.0:
        duration_s = 3.0
    if duration_s > 180.0:
        duration_s = 180.0

    title_contains = str(args.get("title_contains", "") or "").strip()
    settle_ms = int(args.get("settle_ms", 450) or 450)

    # Best-effort: foca a janela se título foi dado.
    if title_contains:
        try:
            from omniscia.modules.os_control.win_windows import focus_window_by_title_contains

            rect = focus_window_by_title_contains(title_contains, timeout_s=2.5)
            if rect:
                # Clique no centro para garantir foco do canvas.
                cx = int((rect["left"] + rect["right"]) // 2)
                cy = int((rect["top"] + rect["bottom"]) // 2)
                pyautogui.click(x=cx, y=cy, button="left")
        except Exception:
            # segue sem foco explícito
            pass

    time.sleep(max(0.0, settle_ms / 1000.0))

    # Start game
    pyautogui.press("space")
    time.sleep(0.15)

    gray = _grab_screen_gray(mss_mod, pil_image_mod)
    calib = _find_dino(gray)
    if calib is None:
        return ToolResult(
            status="error",
            error=(
                "Não consegui localizar o dinossauro na tela. "
                "Deixe o jogo visível (fundo claro) e tente novamente; "
                "se possível maximize a janela do jogo e mantenha o cursor fora do canvas."
            ),
        )

    jumps = 0
    frames = 0
    start = time.time()

    # Regiões (tweaks simples)
    ahead_x0 = calib.dino_x + 60
    ahead_x1 = calib.dino_x + 170
    y0 = calib.baseline_y - 45
    y1 = calib.baseline_y + 15

    # Threshold de detecção: ajustado para stride=2
    trigger_dark_pixels = 35

    while True:
        now = time.time()
        if now - start >= duration_s:
            break

        gray = _grab_screen_gray(mss_mod, pil_image_mod)
        dark = _count_dark_in_rect(gray, x0=ahead_x0, y0=y0, x1=ahead_x1, y1=y1)
        if dark >= trigger_dark_pixels:
            pyautogui.press("space")
            jumps += 1
            # pequeno cooldown para evitar double-jump
            time.sleep(0.08)
        else:
            time.sleep(0.02)

        frames += 1

    return ToolResult(
        status="ok",
        output=f"trex autoplay done: duration_s={duration_s:.1f} jumps={jumps} frames={frames}",
    )
