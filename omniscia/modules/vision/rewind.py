"""Rewind multimodal (buffer circular de screenshots em RAM).

Objetivo:
- Manter um buffer dos últimos N segundos de tela para permitir "rewind".
- Tudo local (mss + Pillow); não envia imagem para a internet.

Opt-in:
- Exige OMNI_REWIND_ENABLED=true.

Guardrails:
- Exporta frames apenas para path relativo (ou known folders no Windows).
- Armazena PNG comprimido em memória para reduzir uso de RAM.
"""

from __future__ import annotations

import io
import json
import math
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from omniscia.core.config import Settings
from omniscia.core.tools import ToolRegistry, ToolSpec
from omniscia.core.types import ToolResult


@dataclass(frozen=True)
class RewindFrame:
    ts: float
    width: int
    height: int
    png_bytes: bytes


class RewindRecorder:
    def __init__(self, *, max_seconds: int = 60, interval_s: float = 1.0, monitor_index: int = 1) -> None:
        if max_seconds < 1:
            max_seconds = 1
        if interval_s <= 0:
            interval_s = 1.0

        self._max_seconds = int(max_seconds)
        self._interval_s = float(interval_s)
        self._monitor_index = int(monitor_index)

        maxlen = int(math.ceil(self._max_seconds / self._interval_s)) + 2
        if maxlen < 3:
            maxlen = 3
        if maxlen > 2000:
            maxlen = 2000

        self._frames: deque[RewindFrame] = deque(maxlen=maxlen)
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_error: str | None = None

    @property
    def running(self) -> bool:
        t = self._thread
        return bool(t and t.is_alive())

    def start(self) -> None:
        if self.running:
            return
        self._stop.clear()
        t = threading.Thread(target=self._loop, name="rewind-recorder", daemon=True)
        self._thread = t
        t.start()

    def stop(self) -> None:
        self._stop.set()

    def status(self) -> dict[str, Any]:
        with self._lock:
            n = len(self._frames)
            if n >= 2:
                span = float(self._frames[-1].ts - self._frames[0].ts)
            else:
                span = 0.0
            return {
                "running": self.running,
                "frames": n,
                "span_s": span,
                "interval_s": self._interval_s,
                "max_seconds": self._max_seconds,
                "last_error": self._last_error,
            }

    def _capture_png(self) -> RewindFrame:
        try:
            import mss
            from PIL import Image
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"deps ausentes (mss/pillow): {exc}")

        with mss.mss() as sct:
            monitors = getattr(sct, "monitors", None) or []
            idx = self._monitor_index
            if not isinstance(idx, int) or idx < 1 or idx >= len(monitors):
                idx = 1
            monitor = monitors[idx]
            shot = sct.grab(monitor)
            img = Image.frombytes("RGB", shot.size, shot.rgb)

        bio = io.BytesIO()
        img.save(bio, format="PNG")
        b = bio.getvalue()
        return RewindFrame(ts=time.time(), width=int(img.size[0]), height=int(img.size[1]), png_bytes=b)

    def _loop(self) -> None:
        while not self._stop.is_set():
            t0 = time.time()
            try:
                frame = self._capture_png()
                with self._lock:
                    self._frames.append(frame)
                    self._last_error = None
            except Exception as exc:  # noqa: BLE001
                with self._lock:
                    self._last_error = str(exc)

            dt = time.time() - t0
            sleep_s = max(0.01, self._interval_s - dt)
            self._stop.wait(timeout=sleep_s)

    def get_frame(self, *, seconds_ago: float) -> RewindFrame | None:
        if seconds_ago < 0:
            seconds_ago = 0.0
        target_ts = time.time() - float(seconds_ago)

        with self._lock:
            if not self._frames:
                return None

            # Busca do mais novo para o mais velho.
            best: RewindFrame | None = None
            for fr in reversed(self._frames):
                if fr.ts <= target_ts:
                    best = fr
                    break
            if best is None:
                # Se pediram mais antigo do que temos, devolve o frame mais antigo.
                best = self._frames[0]
            return best


_global_lock = threading.Lock()
_global_recorder: RewindRecorder | None = None


def get_global_recorder(*, settings: Settings) -> RewindRecorder:
    global _global_recorder
    with _global_lock:
        if _global_recorder is None:
            max_seconds = int(getattr(settings, "rewind_seconds", 60) or 60)
            interval_s = float(getattr(settings, "rewind_interval_s", 1.0) or 1.0)
            _global_recorder = RewindRecorder(max_seconds=max_seconds, interval_s=interval_s, monitor_index=1)
        return _global_recorder


def register_rewind_tools(registry: ToolRegistry, settings: Settings) -> None:
    registry.register(
        ToolSpec(
            name="screen.rewind_status",
            description="Mostra status do rewind (buffer de screenshots em RAM).",
            risk="LOW",
            fn=lambda args: _screen_rewind_status(args, settings=settings),
        )
    )

    registry.register(
        ToolSpec(
            name="screen.rewind_start",
            description="Inicia o gravador de rewind (opt-in).",
            risk="MEDIUM",
            fn=lambda args: _screen_rewind_start(args, settings=settings),
        )
    )

    registry.register(
        ToolSpec(
            name="screen.rewind_stop",
            description="Para o gravador de rewind.",
            risk="LOW",
            fn=lambda args: _screen_rewind_stop(args, settings=settings),
        )
    )

    registry.register(
        ToolSpec(
            name="screen.rewind_save",
            description=(
                "Salva um frame do rewind (N segundos atrás) como PNG. "
                "Args: seconds_ago (float), path (relativo ou desktop:/downloads:/documents:/ no Windows)."
            ),
            risk="HIGH",
            fn=lambda args: _screen_rewind_save(args, settings=settings),
        )
    )

    registry.register(
        ToolSpec(
            name="screen.rewind_ocr",
            description=(
                "Faz OCR de um frame do rewind (N segundos atrás). "
                "Args: seconds_ago (float), lang, max_chars."
            ),
            risk="MEDIUM",
            fn=lambda args: _screen_rewind_ocr(args, settings=settings),
        )
    )


def _ensure_enabled(settings: Settings) -> tuple[bool, str | None]:
    if not bool(getattr(settings, "rewind_enabled", False)):
        return False, "rewind desabilitado (OMNI_REWIND_ENABLED=false)"
    return True, None


def _screen_rewind_status(args: dict[str, Any], *, settings: Settings) -> ToolResult:
    enabled, err = _ensure_enabled(settings)
    rec = get_global_recorder(settings=settings)
    st = rec.status()
    st["enabled"] = enabled
    if not enabled:
        st["note"] = err
    return ToolResult(status="ok", output=json.dumps(st, ensure_ascii=False))


def _screen_rewind_start(args: dict[str, Any], *, settings: Settings) -> ToolResult:
    enabled, err = _ensure_enabled(settings)
    if not enabled:
        return ToolResult(status="error", error=str(err))

    rec = get_global_recorder(settings=settings)
    rec.start()
    return ToolResult(status="ok", output="rewind recorder started")


def _screen_rewind_stop(args: dict[str, Any], *, settings: Settings) -> ToolResult:
    rec = get_global_recorder(settings=settings)
    rec.stop()
    return ToolResult(status="ok", output="rewind recorder stop requested")


def _resolve_output_path(path_str: str) -> tuple[Path, str] | tuple[None, str]:
    p = (path_str or "").strip().replace("\\", "/")
    if not p:
        return None, "path vazio"

    low = p.lower()
    is_known = low.startswith(("desktop:", "downloads:", "documents:"))

    if not low.endswith(".png"):
        return None, "path deve terminar com .png"

    if is_known:
        if not sys.platform.startswith("win"):
            return None, "known folders só são suportados no Windows"
        from omniscia.modules.os_control.filesystem import resolve_known_folder_prefixed_path

        out = resolve_known_folder_prefixed_path(p)
        return out, p

    if p.startswith("/") or ":" in p or ".." in p.split("/"):
        return None, "path inválido (use path relativo)"

    return Path(p), p


def _screen_rewind_save(args: dict[str, Any], *, settings: Settings) -> ToolResult:
    enabled, err = _ensure_enabled(settings)
    if not enabled:
        return ToolResult(status="error", error=str(err))

    seconds_ago = float(args.get("seconds_ago", 5.0) or 5.0)
    raw_path = str(args.get("path", "") or "").strip()
    path_str = raw_path or "data/screenshots/rewind.png"

    rec = get_global_recorder(settings=settings)
    if not rec.running:
        rec.start()
        # Dá uma janela rápida pra capturar pelo menos 1 frame.
        time.sleep(min(0.2, float(getattr(settings, "rewind_interval_s", 1.0) or 1.0)))

    fr = rec.get_frame(seconds_ago=seconds_ago)
    if fr is None:
        return ToolResult(status="error", error="rewind vazio (nenhum frame capturado ainda)")

    out, label_or_err = _resolve_output_path(path_str)
    if out is None:
        return ToolResult(status="error", error=str(label_or_err))

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(fr.png_bytes)

    msg = f"saved rewind frame ({seconds_ago:.1f}s ago): {label_or_err}"
    return ToolResult(status="ok", output=msg)


def _screen_rewind_ocr(args: dict[str, Any], *, settings: Settings) -> ToolResult:
    enabled, err = _ensure_enabled(settings)
    if not enabled:
        return ToolResult(status="error", error=str(err))

    seconds_ago = float(args.get("seconds_ago", 5.0) or 5.0)
    lang = str(args.get("lang", "por+eng") or "por+eng")
    max_chars = int(args.get("max_chars", 6000) or 6000)

    try:
        import pytesseract
        from PIL import Image
    except Exception as exc:  # noqa: BLE001
        return ToolResult(status="error", error=f"deps ausentes (pytesseract/pillow): {exc}")

    # Config tesseract (se setado)
    tcmd = getattr(settings, "tesseract_cmd", None)
    if tcmd:
        pytesseract.pytesseract.tesseract_cmd = tcmd

    rec = get_global_recorder(settings=settings)
    if not rec.running:
        rec.start()
        time.sleep(min(0.2, float(getattr(settings, "rewind_interval_s", 1.0) or 1.0)))

    fr = rec.get_frame(seconds_ago=seconds_ago)
    if fr is None:
        return ToolResult(status="error", error="rewind vazio (nenhum frame capturado ainda)")

    try:
        img = Image.open(io.BytesIO(fr.png_bytes))
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
