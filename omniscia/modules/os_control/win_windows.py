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


def get_foreground_window_hwnd() -> int | None:
    """Return current foreground window HWND (Windows only)."""

    if not sys.platform.startswith("win"):
        return None

    try:
        import ctypes
        from ctypes import wintypes
    except Exception:
        return None

    user32 = ctypes.windll.user32
    GetForegroundWindow = user32.GetForegroundWindow
    GetForegroundWindow.argtypes = []
    GetForegroundWindow.restype = wintypes.HWND

    try:
        hwnd = int(GetForegroundWindow())
        return hwnd if hwnd else None
    except Exception:
        return None


def get_foreground_window_title() -> str | None:
    """Return the title of the foreground window (Windows only)."""

    if not sys.platform.startswith("win"):
        return None

    hwnd = get_foreground_window_hwnd()
    if not hwnd:
        return None

    try:
        import ctypes
        from ctypes import wintypes
    except Exception:
        return None

    user32 = ctypes.windll.user32
    GetWindowTextW = user32.GetWindowTextW
    GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    GetWindowTextW.restype = ctypes.c_int

    try:
        buf = ctypes.create_unicode_buffer(512)
        GetWindowTextW(hwnd, buf, 512)
        title = (buf.value or "").strip()
        return title
    except Exception:
        return None


def find_window_hwnd_by_title_contains(
    title_contains: str,
    *,
    timeout_s: float = 3.0,
    visible_only: bool = True,
) -> int | None:
    """Find a window handle whose title contains the given substring."""

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

    return found_hwnd


def close_window_by_title_contains(
    title_contains: str,
    *,
    timeout_s: float = 3.0,
    visible_only: bool = True,
) -> bool:
    """Request a window close via WM_CLOSE.

    Returns True if a matching window was found and WM_CLOSE was posted.
    """

    if not sys.platform.startswith("win"):
        return False

    hwnd = find_window_hwnd_by_title_contains(
        title_contains,
        timeout_s=timeout_s,
        visible_only=visible_only,
    )
    if hwnd is None:
        return False

    try:
        import ctypes
        from ctypes import wintypes
    except Exception:
        return False

    user32 = ctypes.windll.user32

    ShowWindow = user32.ShowWindow
    ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    ShowWindow.restype = wintypes.BOOL

    PostMessageW = user32.PostMessageW
    PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    PostMessageW.restype = wintypes.BOOL

    SW_RESTORE = 9
    WM_CLOSE = 0x0010

    try:
        ShowWindow(hwnd, SW_RESTORE)
        PostMessageW(hwnd, WM_CLOSE, 0, 0)
        return True
    except Exception:
        return False


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


def focus_window_by_class_name(
    class_name: str,
    *,
    timeout_s: float = 3.0,
    visible_only: bool = True,
) -> dict[str, int] | None:
    """Focus/restore a top-level window by Win32 class name.

    Useful when titles are localized/dynamic (ex: Microsoft Word uses class 'OpusApp').
    Returns a dict with keys: left/top/right/bottom.
    """

    if not sys.platform.startswith("win"):
        return None

    needle = (class_name or "").strip()
    if not needle:
        return None

    try:
        import ctypes
        from ctypes import wintypes
    except Exception:
        return None

    user32 = ctypes.windll.user32

    WNDENUMPROC = getattr(
        wintypes,
        "WNDENUMPROC",
        ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM),
    )

    EnumWindows = user32.EnumWindows
    EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]
    EnumWindows.restype = wintypes.BOOL

    IsWindowVisible = user32.IsWindowVisible
    IsWindowVisible.argtypes = [wintypes.HWND]
    IsWindowVisible.restype = wintypes.BOOL

    GetClassNameW = user32.GetClassNameW
    GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    GetClassNameW.restype = ctypes.c_int

    GetWindowTextW = user32.GetWindowTextW
    GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    GetWindowTextW.restype = ctypes.c_int

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

    def _get_class(hwnd: int) -> str:
        buf = ctypes.create_unicode_buffer(256)
        try:
            n = int(GetClassNameW(hwnd, buf, 256))
            return (buf.value or "").strip() if n > 0 else ""
        except Exception:
            return ""

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
            cls = _get_class(int(hwnd))
            if not cls or cls.casefold() != needle_cf:
                return True
            title = _get_title(int(hwnd))
            # Prefer windows that actually have a title (top-level app windows).
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
