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

from omniscia.core.config import Settings
from omniscia.core.tools import ToolRegistry, ToolSpec
from omniscia.core.types import ToolResult


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
        if args.get("path"):
            p = _safe_rel_png(str(args.get("path")))
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
