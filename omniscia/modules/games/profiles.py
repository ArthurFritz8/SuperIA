"""Framework genérico de autoplayer via perfis.

Motivação
- "Qualquer jogo" não é realista com uma única heurística.
- Este módulo cria um mecanismo único e extensível via *profiles*:
  - ações -> teclas (space, up, click)
  - detectores -> regiões da tela + regra (ex.: pixels escuros)

Segurança
- GUI/teclado: risco HIGH; deve passar por HITL.
- Bloqueios de ToS/anti-cheat são feitos no router (intenção do usuário).

Armazenamento
- profiles ficam em data/games/profiles.json (workspace-local).
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from omniscia.core.tools import ToolRegistry, ToolSpec
from omniscia.core.types import ToolResult


_PROFILES_PATH = Path("data/games/profiles.json")


def register_game_profile_tools(registry: ToolRegistry) -> None:
    registry.register(
        ToolSpec(
            name="game.list_profiles",
            description="Lista perfis de jogo disponíveis (data/games/profiles.json)",
            risk="LOW",
            fn=_list_profiles,
        )
    )

    registry.register(
        ToolSpec(
            name="game.save_profile",
            description=(
                "Salva/atualiza um perfil de jogo. Args: name, profile (dict). "
                "Escreve em data/games/profiles.json"
            ),
            risk="HIGH",
            fn=_save_profile,
        )
    )

    registry.register(
        ToolSpec(
            name="game.autoplay",
            description=(
                "Executa um autoplayer baseado em profile ou template. "
                "Args: profile?, template?, duration_s?, title_contains?, settle_ms?"
            ),
            risk="HIGH",
            fn=_autoplay,
        )
    )

    registry.register(
        ToolSpec(
            name="game.calibrate_runner_from_mouse",
            description=(
                "Cria/atualiza um profile runner usando a posição atual do mouse como referência do personagem. "
                "Args: name?, jump_key?, ahead_dx0?, ahead_dx1?, dy0?, dy1?"
            ),
            risk="HIGH",
            fn=_calibrate_runner_from_mouse,
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


def _load_profiles() -> dict[str, Any]:
    if not _PROFILES_PATH.exists():
        _PROFILES_PATH.parent.mkdir(parents=True, exist_ok=True)
        _PROFILES_PATH.write_text('{"profiles": {}}\n', encoding="utf-8")
    try:
        data = json.loads(_PROFILES_PATH.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        data = {"profiles": {}}
    if not isinstance(data, dict):
        data = {"profiles": {}}
    if "profiles" not in data or not isinstance(data.get("profiles"), dict):
        data["profiles"] = {}
    return data


def _write_profiles(data: dict[str, Any]) -> None:
    _PROFILES_PATH.parent.mkdir(parents=True, exist_ok=True)
    _PROFILES_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _list_profiles(args: dict[str, Any]) -> ToolResult:
    data = _load_profiles()
    profiles = data.get("profiles", {})
    if not profiles:
        return ToolResult(status="ok", output="(sem perfis)\nUse game.save_profile para criar um.")
    names = sorted(str(k) for k in profiles.keys())
    return ToolResult(status="ok", output="perfis:\n- " + "\n- ".join(names))


def _save_profile(args: dict[str, Any]) -> ToolResult:
    name = str(args.get("name", "") or "").strip().lower()
    profile = args.get("profile")

    if not name or len(name) > 60:
        return ToolResult(status="error", error="name inválido")
    if not isinstance(profile, dict):
        return ToolResult(status="error", error="profile deve ser um dict")

    # validação mínima
    detectors = profile.get("detectors")
    if detectors is not None and not isinstance(detectors, list):
        return ToolResult(status="error", error="profile.detectors deve ser uma lista")

    actions = profile.get("actions")
    if actions is not None and not isinstance(actions, dict):
        return ToolResult(status="error", error="profile.actions deve ser um dict")

    data = _load_profiles()
    data.setdefault("profiles", {})
    data["profiles"][name] = profile
    _write_profiles(data)
    return ToolResult(status="ok", output=f"saved profile: {name}")


@dataclass(frozen=True)
class _Detector:
    rect: tuple[int, int, int, int]
    min_count: int
    threshold: int
    action: str
    cooldown_ms: int


def _grab_gray(mss_mod, pil_image_mod, bbox: tuple[int, int, int, int] | None):
    with mss_mod.mss() as sct:
        if bbox is None:
            monitor = sct.monitors[1]
            shot = sct.grab(monitor)
            img = pil_image_mod.frombytes("RGB", shot.size, shot.rgb)
            return img.convert("L"), (0, 0)
        left, top, width, height = bbox
        mon = {"left": int(left), "top": int(top), "width": int(width), "height": int(height)}
        shot = sct.grab(mon)
        img = pil_image_mod.frombytes("RGB", shot.size, shot.rgb)
        return img.convert("L"), (int(left), int(top))


def _count_dark(gray, rect: tuple[int, int, int, int], *, origin: tuple[int, int]) -> int:
    ox, oy = origin
    x0, y0, x1, y1 = rect
    x0 -= ox
    x1 -= ox
    y0 -= oy
    y1 -= oy

    w, h = gray.size
    x0 = max(0, min(w - 1, int(x0)))
    x1 = max(0, min(w, int(x1)))
    y0 = max(0, min(h - 1, int(y0)))
    y1 = max(0, min(h, int(y1)))
    if x1 <= x0 or y1 <= y0:
        return 0

    px = gray.load()
    n = 0
    # stride
    for y in range(y0, y1, 2):
        for x in range(x0, x1, 2):
            if px[x, y] < 120:
                n += 1
    return n


def _parse_profile(profile: dict[str, Any]) -> tuple[dict[str, str], list[_Detector], str | None]:
    actions = profile.get("actions") or {}
    if not isinstance(actions, dict):
        actions = {}
    action_keys: dict[str, str] = {}
    for k, v in actions.items():
        ks = str(k).strip().lower()
        vs = str(v).strip().lower()
        if ks and vs and len(vs) <= 20:
            action_keys[ks] = vs

    start_action = profile.get("start_action")
    if start_action is not None:
        start_action = str(start_action).strip().lower() or None

    detectors_raw = profile.get("detectors") or []
    detectors: list[_Detector] = []
    if isinstance(detectors_raw, list):
        for d in detectors_raw:
            if not isinstance(d, dict):
                continue
            rect = d.get("rect")
            if not (isinstance(rect, (list, tuple)) and len(rect) == 4):
                continue
            try:
                x0, y0, x1, y1 = (int(rect[0]), int(rect[1]), int(rect[2]), int(rect[3]))
            except Exception:
                continue
            if x1 <= x0 or y1 <= y0:
                continue

            action = str(d.get("action", "") or "").strip().lower()
            if not action:
                continue

            min_count = int(d.get("min_count", 35) or 35)
            threshold = int(d.get("threshold", 120) or 120)
            cooldown_ms = int(d.get("cooldown_ms", 80) or 80)
            min_count = max(1, min(5000, min_count))
            threshold = max(1, min(254, threshold))
            cooldown_ms = max(0, min(5000, cooldown_ms))

            detectors.append(
                _Detector(
                    rect=(x0, y0, x1, y1),
                    min_count=min_count,
                    threshold=threshold,
                    action=action,
                    cooldown_ms=cooldown_ms,
                )
            )

    return action_keys, detectors, start_action


def _default_template_runner() -> dict[str, Any]:
    # Template genérico para jogos estilo runner.
    # Precisa calibrar rect via game.save_profile para ficar bom.
    return {
        "actions": {"jump": "space"},
        "start_action": "jump",
        "detectors": [],
    }


def _calibrate_runner_from_mouse(args: dict[str, Any]) -> ToolResult:
    """Calibração rápida para jogos estilo runner.

    Uso esperado:
    - Usuário coloca o mouse em cima do personagem (ou bem perto dele).
    - Executa esta tool.
    - Ela cria um detector "dark_pixels" à frente e salva em data/games/profiles.json.
    """

    pyautogui, err = _require_pyautogui()
    if pyautogui is None:
        return ToolResult(status="error", error=err)

    name = str(args.get("name", "runner") or "runner").strip().lower()
    if not name or len(name) > 60:
        return ToolResult(status="error", error="name inválido")

    jump_key = str(args.get("jump_key", "space") or "space").strip().lower()
    if not jump_key or len(jump_key) > 20:
        return ToolResult(status="error", error="jump_key inválida")

    # offsets padrão (bons para T-Rex e runners similares)
    ahead_dx0 = int(args.get("ahead_dx0", 60) or 60)
    ahead_dx1 = int(args.get("ahead_dx1", 170) or 170)
    dy0 = int(args.get("dy0", -45) or -45)
    dy1 = int(args.get("dy1", 15) or 15)

    # limites
    ahead_dx0 = max(10, min(600, ahead_dx0))
    ahead_dx1 = max(ahead_dx0 + 10, min(900, ahead_dx1))
    dy0 = max(-400, min(0, dy0))
    dy1 = max(0, min(400, dy1))

    x, y = pyautogui.position()
    # Interpretamos (x,y) como o "ponto de referência" do personagem.
    # O detector usa uma faixa à frente e um pouco abaixo/acima.
    rect = [int(x + ahead_dx0), int(y + dy0), int(x + ahead_dx1), int(y + dy1)]

    profile = {
        "actions": {"jump": jump_key},
        "start_action": "jump",
        "detectors": [
            {
                "rect": rect,
                "min_count": 35,
                "threshold": 120,
                "action": "jump",
                "cooldown_ms": 80,
            }
        ],
    }

    data = _load_profiles()
    data.setdefault("profiles", {})
    data["profiles"][name] = profile
    _write_profiles(data)
    return ToolResult(status="ok", output=f"calibrated runner profile '{name}' at mouse=({x},{y}) rect={rect}")


def _autoplay(args: dict[str, Any]) -> ToolResult:
    pyautogui, err = _require_pyautogui()
    if pyautogui is None:
        return ToolResult(status="error", error=err)

    mss_mod, pil_image_mod, verr = _require_vision()
    if mss_mod is None:
        return ToolResult(status="error", error=verr)

    duration_s = float(args.get("duration_s", 30.0) or 30.0)
    duration_s = max(3.0, min(180.0, duration_s))
    title_contains = str(args.get("title_contains", "") or "").strip()
    settle_ms = int(args.get("settle_ms", 450) or 450)

    profile_name = str(args.get("profile", "") or "").strip().lower()
    template = str(args.get("template", "") or "").strip().lower()

    profile: dict[str, Any] | None = None
    if profile_name:
        data = _load_profiles()
        p = (data.get("profiles") or {}).get(profile_name)
        if isinstance(p, dict):
            profile = p

    if profile is None:
        if template == "runner" or (not template and not profile_name):
            profile = _default_template_runner()
        else:
            profile = None

    if profile is None:
        data = _load_profiles()
        names = sorted((data.get("profiles") or {}).keys())
        return ToolResult(
            status="error",
            error=(
                "Perfil não encontrado e nenhum template válido. "
                f"profiles={names}. Use game.list_profiles ou game.save_profile."
            ),
        )

    # Best-effort focus
    if title_contains:
        try:
            from omniscia.modules.os_control.win_windows import focus_window_by_title_contains

            rect = focus_window_by_title_contains(title_contains, timeout_s=2.5)
            if rect:
                cx = int((rect["left"] + rect["right"]) // 2)
                cy = int((rect["top"] + rect["bottom"] ) // 2)
                pyautogui.click(x=cx, y=cy, button="left")
        except Exception:
            pass

    time.sleep(max(0.0, settle_ms / 1000.0))

    action_keys, detectors, start_action = _parse_profile(profile)

    def _press_action(action: str) -> bool:
        key = action_keys.get(action)
        if not key:
            return False
        pyautogui.press(key)
        return True

    # Start action if configured
    if start_action:
        _press_action(start_action)
        time.sleep(0.12)

    # If no detectors, we can't react; return guidance quickly.
    if not detectors:
        return ToolResult(
            status="error",
            error=(
                "Template/profile sem detectores. Para funcionar em 'qualquer jogo', "
                "crie um profile com detectors (rect + min_count + action)."
            ),
        )

    # Bounding box to capture only necessary region
    min_x0 = min(d.rect[0] for d in detectors)
    min_y0 = min(d.rect[1] for d in detectors)
    max_x1 = max(d.rect[2] for d in detectors)
    max_y1 = max(d.rect[3] for d in detectors)
    bbox = (min_x0, min_y0, max_x1 - min_x0, max_y1 - min_y0)

    last_action_at: dict[str, float] = {}
    frames = 0
    actions = 0
    start = time.time()

    while True:
        now = time.time()
        if now - start >= duration_s:
            break

        gray, origin = _grab_gray(mss_mod, pil_image_mod, bbox)
        px = gray.load()  # noqa: F841

        for det in detectors:
            last = last_action_at.get(det.action, 0.0)
            if det.cooldown_ms and (now - last) < (det.cooldown_ms / 1000.0):
                continue

            # NOTE: threshold ainda fixo em 120 por simplicidade do MVP.
            # Usamos det.threshold como campo futuro.
            dark = _count_dark(gray, det.rect, origin=origin)
            if dark >= det.min_count:
                if _press_action(det.action):
                    actions += 1
                    last_action_at[det.action] = now
                    time.sleep(0.02)

        frames += 1
        time.sleep(0.015)

    return ToolResult(status="ok", output=f"autoplay done: duration_s={duration_s:.1f} frames={frames} actions={actions}")
