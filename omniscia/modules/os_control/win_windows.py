"""Utilitários Windows para localizar/focar janelas.

Objetivo:
- Permitir automação independente de monitor/minimizado/foco.
- Expor retângulo da janela para cliques/recortes de OCR.

Notas:
- Best-effort: Win32 tem limitações (ex: SetForegroundWindow pode falhar em alguns cenários).
- Sempre retorna None quando não suportado.
"""

from __future__ import annotations

import sys
import time
from typing import Callable


def focus_window_by_title_contains(
    title_contains: str,
    *,
    timeout_s: float = 3.0,
    visible_only: bool = True,
) -> dict[str, int] | None:
    """Focus/restore a window whose title contains the given substring.

    Returns a dict with keys: left/top/right/bottom.
    """

    if not sys.platform.startswith("win"):
        return None

    needle = (title_contains or "").strip()
    if not needle:
        return None

    try:
        import ctypes
        from ctypes import wintypes
    except Exception:
        return None

    user32 = ctypes.windll.user32

    # Some Python/ctypes builds don't expose wintypes.WNDENUMPROC.
    # Define the callback type explicitly for EnumWindows.
    WNDENUMPROC = getattr(
        wintypes,
        "WNDENUMPROC",
        ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM),
    )

    EnumWindows = user32.EnumWindows
    EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]
    EnumWindows.restype = wintypes.BOOL

    GetWindowTextW = user32.GetWindowTextW
    GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    GetWindowTextW.restype = ctypes.c_int

    IsWindowVisible = user32.IsWindowVisible
    IsWindowVisible.argtypes = [wintypes.HWND]
    IsWindowVisible.restype = wintypes.BOOL

    ShowWindow = user32.ShowWindow
    ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    ShowWindow.restype = wintypes.BOOL

    SetForegroundWindow = user32.SetForegroundWindow
    SetForegroundWindow.argtypes = [wintypes.HWND]
    SetForegroundWindow.restype = wintypes.BOOL

    GetWindowRect = user32.GetWindowRect
    GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    GetWindowRect.restype = wintypes.BOOL

    SW_RESTORE = 9

    def _get_title(hwnd: int) -> str:
        buf = ctypes.create_unicode_buffer(512)
        try:
            GetWindowTextW(hwnd, buf, 512)
            return (buf.value or "").strip()
        except Exception:
            return ""

    found_hwnd: int | None = None
    best_title: str = ""
    needle_cf = needle.casefold()

    @WNDENUMPROC
    def _enum_proc(hwnd, lparam):  # noqa: ANN001
        nonlocal found_hwnd, best_title
        try:
            if visible_only and not IsWindowVisible(hwnd):
                return True
            title = _get_title(int(hwnd))
            if not title:
                return True
            if needle_cf in title.casefold():
                # Prefer longer titles (often includes context like server/channel).
                if found_hwnd is None or len(title) > len(best_title):
                    found_hwnd = int(hwnd)
                    best_title = title
        except Exception:
            return True
        return True

    deadline = time.time() + float(timeout_s)
    while time.time() < deadline and found_hwnd is None:
        try:
            EnumWindows(_enum_proc, 0)
        except Exception:
            break
        if found_hwnd is None:
            time.sleep(0.1)

    if found_hwnd is None:
        return None

    try:
        ShowWindow(found_hwnd, SW_RESTORE)
        SetForegroundWindow(found_hwnd)
        time.sleep(0.2)
        rect = wintypes.RECT()
        if not GetWindowRect(found_hwnd, ctypes.byref(rect)):
            return None
        return {
            "left": int(rect.left),
            "top": int(rect.top),
            "right": int(rect.right),
            "bottom": int(rect.bottom),
        }
    except Exception:
        return None


def with_focused_window(
    title_contains: str,
    fn: Callable[[dict[str, int]], None],
    *,
    timeout_s: float = 3.0,
) -> bool:
    rect = focus_window_by_title_contains(title_contains, timeout_s=timeout_s)
    if not rect:
        return False
    fn(rect)
    return True
