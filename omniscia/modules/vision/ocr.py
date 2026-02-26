"""OCR local (Tesseract via pytesseract).

Rationale:
- OCR é um "superpoder" barato para interfaces: permite ler botões, labels, erros.
- Mantemos OCR local e opcional (não envia imagens para a internet).

Pré-requisitos:
- `pip install pytesseract pillow`
- Instalar o binário do Tesseract no Windows e garantir no PATH.
  (Opcional) configurar `OMNI_TESSERACT_CMD` apontando para tesseract.exe.

Guardrails:
- Aceita apenas paths relativos para arquivos.
- Pode tirar screenshot na hora e OCR em memória.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import json

from omniscia.core.config import Settings
from omniscia.core.tools import ToolRegistry, ToolSpec
from omniscia.core.types import ToolResult
from omniscia.modules.os_control.win_windows import focus_window_by_title_contains


@dataclass(frozen=True)
class OcrConfig:
    tesseract_cmd: str | None = None


def register_ocr_tools(registry: ToolRegistry, settings: Settings) -> None:
    registry.register(
        ToolSpec(
            name="screen.ocr",
            description="Faz OCR de screenshot atual ou de um PNG (path relativo)",
            risk="MEDIUM",
            fn=lambda args: _screen_ocr(args, settings=settings),
        )
    )

    registry.register(
        ToolSpec(
            name="screen.find_text",
            description=(
                "Encontra texto via OCR e retorna caixas (x,y,w,h). "
                "Útil para automação guiada por tela (read-only)."
            ),
            risk="MEDIUM",
            fn=lambda args: _screen_find_text(args, settings=settings),
        )
    )

    registry.register(
        ToolSpec(
            name="screen.click_text",
            description=(
                "Procura um texto via OCR e clica no melhor match (x/y/w/h). "
                "Requer pyautogui + tesseract."
            ),
            risk="HIGH",
            fn=lambda args: _screen_click_text(args, settings=settings),
        )
    )


def _configure_tesseract(cfg: OcrConfig) -> None:
    import pytesseract

    if cfg.tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = cfg.tesseract_cmd


def _safe_rel_png(path: str) -> Path:
    p = (path or "").strip().replace("\\", "/")
    if not p:
        raise ValueError("path vazio")
    if p.startswith("/") or ":" in p:
        raise ValueError("path deve ser relativo")
    if ".." in p.split("/"):
        raise ValueError("path não pode conter '..'")
    if not p.lower().endswith(".png"):
        raise ValueError("arquivo deve terminar com .png")
    return Path(p)


def _screen_ocr(args: dict[str, Any], *, settings: Settings) -> ToolResult:
    """OCR de screenshot atual ou de um arquivo.

    Args aceitos:
    - path: PNG relativo (opcional). Se ausente, tira screenshot e faz OCR.
    - lang: idioma do Tesseract (default: por+eng). Requer pacotes de idioma.
    - max_chars: truncar saída para evitar flood no terminal.
    """

    try:
        import pytesseract
        from PIL import Image
    except Exception as exc:  # noqa: BLE001
        return ToolResult(status="error", error=f"deps ausentes (pytesseract/pillow): {exc}")

    cfg = OcrConfig(tesseract_cmd=getattr(settings, "tesseract_cmd", None))
    _configure_tesseract(cfg)

    lang = str(args.get("lang", "por+eng") or "por+eng")
    max_chars = int(args.get("max_chars", 6000) or 6000)

    try:
        raw_path = args.get("path") or args.get("image_path")
        if raw_path:
            p = _safe_rel_png(str(raw_path))
            if not p.exists():
                return ToolResult(status="error", error="arquivo não existe")
            img = Image.open(p)
        else:
            # Screenshot em memória
            import mss

            with mss.mss() as sct:
                monitor = sct.monitors[1]
                shot = sct.grab(monitor)
                img = Image.frombytes("RGB", shot.size, shot.rgb)

        # Pré-processamento simples: grayscale melhora OCR em muitas telas.
        img = img.convert("L")

        text = pytesseract.image_to_string(img, lang=lang)
        text = (text or "").strip()
        if len(text) > max_chars:
            text = text[:max_chars] + "\n... [truncado]"

        return ToolResult(status="ok", output=text if text else "(sem texto detectado)")

    except pytesseract.TesseractNotFoundError:
        return ToolResult(
            status="error",
            error=(
                "Tesseract não encontrado. Instale o Tesseract no Windows e/ou configure OMNI_TESSERACT_CMD."
            ),
        )
    except Exception as exc:  # noqa: BLE001
        return ToolResult(status="error", error=str(exc))


def _screen_find_text(args: dict[str, Any], *, settings: Settings) -> ToolResult:
    """Procura por um texto específico e retorna caixas.

    Args aceitos:
    - query: texto a procurar (obrigatório)
    - path: PNG relativo (opcional). Se ausente, tira screenshot e faz OCR.
    - window_title: substring do título de uma janela (opcional, Windows). Se presente, foca a janela e recorta OCR nela.
    - lang: idioma do Tesseract (default: por+eng)
    - max_results: limite de caixas retornadas (default: 10)
    - min_conf: confiança mínima (0-100) (default: 55)

    Output:
    - JSON com lista de matches: {text, conf, x, y, w, h}
    """

    query = str(args.get("query", "") or "").strip()
    if not query:
        return ToolResult(status="error", error="query vazio")

    try:
        import pytesseract
        from PIL import Image
    except Exception as exc:  # noqa: BLE001
        return ToolResult(status="error", error=f"deps ausentes (pytesseract/pillow): {exc}")

    cfg = OcrConfig(tesseract_cmd=getattr(settings, "tesseract_cmd", None))
    _configure_tesseract(cfg)

    lang = str(args.get("lang", "por+eng") or "por+eng")
    max_results = int(args.get("max_results", 10) or 10)
    min_conf = int(args.get("min_conf", 55) or 55)

    q_norm = query.casefold()

    window_title = str(args.get("window_title", "") or "").strip()

    try:
        raw_path = args.get("path") or args.get("image_path")
        offset_x = 0
        offset_y = 0

        if raw_path:
            p = _safe_rel_png(str(raw_path))
            if not p.exists():
                return ToolResult(status="error", error="arquivo não existe")
            img = Image.open(p)
        else:
            import mss

            with mss.mss() as sct:
                # Para suportar multi-monitor e janelas em outros monitores,
                # usamos o monitor virtual (monitors[0]) quando window_title for usado.
                monitor = sct.monitors[0] if window_title else sct.monitors[1]
                shot = sct.grab(monitor)
                img = Image.frombytes("RGB", shot.size, shot.rgb)
                offset_x = int(getattr(shot, "left", 0) or 0)
                offset_y = int(getattr(shot, "top", 0) or 0)

                if window_title:
                    rect = focus_window_by_title_contains(window_title, timeout_s=2.5)
                    if not rect:
                        return ToolResult(status="error", error="janela não encontrada para window_title")

                    # Ajuste para coordenadas da imagem do monitor virtual.
                    left = int(rect["left"] - offset_x)
                    top = int(rect["top"] - offset_y)
                    right = int(rect["right"] - offset_x)
                    bottom = int(rect["bottom"] - offset_y)
                    if right <= left or bottom <= top:
                        return ToolResult(status="error", error="rect inválido")
                    # Crop e define offset para devolver caixas em coordenadas globais.
                    img = img.crop((left, top, right, bottom))
                    offset_x = int(rect["left"])
                    offset_y = int(rect["top"])

        # Grayscale ajuda OCR.
        img = img.convert("L")

        data = pytesseract.image_to_data(img, lang=lang, output_type=pytesseract.Output.DICT)

        n = len(data.get("text", []) or [])
        results: list[dict[str, Any]] = []
        for i in range(n):
            raw_text = str((data.get("text") or [""])[i] or "").strip()
            if not raw_text:
                continue

            try:
                conf = int(float((data.get("conf") or ["-1"])[i] or -1))
            except Exception:
                conf = -1

            if conf < min_conf:
                continue

            if q_norm not in raw_text.casefold():
                continue

            left = int((data.get("left") or [0])[i] or 0) + int(offset_x)
            top = int((data.get("top") or [0])[i] or 0) + int(offset_y)
            width = int((data.get("width") or [0])[i] or 0)
            height = int((data.get("height") or [0])[i] or 0)

            results.append(
                {
                    "text": raw_text,
                    "conf": conf,
                    "x": left,
                    "y": top,
                    "w": width,
                    "h": height,
                }
            )
            if len(results) >= max_results:
                break

        # Ordena por conf desc, depois por posição.
        results = sorted(results, key=lambda r: (-int(r.get("conf", 0)), int(r.get("y", 0)), int(r.get("x", 0))))
        return ToolResult(status="ok", output=json.dumps({"query": query, "matches": results}, ensure_ascii=False))

    except pytesseract.TesseractNotFoundError:
        return ToolResult(
            status="error",
            error=(
                "Tesseract não encontrado. Instale o Tesseract no Windows e/ou configure OMNI_TESSERACT_CMD."
            ),
        )
    except Exception as exc:  # noqa: BLE001
        return ToolResult(status="error", error=str(exc))


def _require_pyautogui():
    try:
        import pyautogui

        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.05
        return pyautogui, None
    except Exception as exc:  # noqa: BLE001
        return None, f"pyautogui indisponível: {exc}"


def _screen_click_text(args: dict[str, Any], *, settings: Settings) -> ToolResult:
    """Find text via OCR and click the best match.

    Args:
    - query: texto a procurar (obrigatório)
    - path/image_path: PNG relativo (opcional). Se ausente, usa screenshot atual.
    - lang: idioma (default por+eng)
    - min_conf: default 60

    Note:
    - Esta tool tem side-effect (clique), então deve passar pelo HITL.
    """

    query = str(args.get("query", "") or "").strip()
    if not query:
        return ToolResult(status="error", error="query vazio")

    pyautogui, err = _require_pyautogui()
    if pyautogui is None:
        return ToolResult(status="error", error=err)

    # Reuse find_text logic and then click center of best match.
    min_conf = int(args.get("min_conf", 60) or 60)

    res = _screen_find_text(
        {
            "query": query,
            "path": args.get("path"),
            "image_path": args.get("image_path"),
            "window_title": args.get("window_title"),
            "lang": args.get("lang", "por+eng"),
            "max_results": 5,
            "min_conf": min_conf,
        },
        settings=settings,
    )
    if res.status != "ok" or not res.output:
        return ToolResult(status="error", error=res.error or "falha no OCR")

    try:
        payload = json.loads(res.output)
        matches = payload.get("matches") or []
        if not matches:
            return ToolResult(status="error", error="nenhum match encontrado")

        best = matches[0]
        x = int(best.get("x"))
        y = int(best.get("y"))
        w = int(best.get("w"))
        h = int(best.get("h"))
        if w <= 0 or h <= 0:
            return ToolResult(status="error", error="match inválido (w/h)")

        cx = x + (w // 2)
        cy = y + (h // 2)
        screen_w, screen_h = pyautogui.size()
        if cx < 0 or cy < 0 or cx >= int(screen_w) or cy >= int(screen_h):
            return ToolResult(status="error", error="centro fora da tela")

        pyautogui.click(x=cx, y=cy, button="left")
        return ToolResult(
            status="ok",
            output=json.dumps(
                {"clicked": {"x": cx, "y": cy}, "match": best},
                ensure_ascii=False,
            ),
        )
    except Exception as exc:  # noqa: BLE001
        return ToolResult(status="error", error=str(exc))
