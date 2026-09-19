"""High-resolution Win32 wheel input layered on the hardened native backend."""

from __future__ import annotations

import ctypes

from ._windows_legacy import _Point, _signed_word
from .events import NativeWindowHandle, PlatformEvent, PlatformEventKind
from .windows import Win32PlatformBackend as _BaseWin32PlatformBackend

_WM_MOUSEWHEEL = 0x020A
_WM_MOUSEHWHEEL = 0x020E
_WHEEL_DELTA = 120.0
_WHEEL_STEP_DIP = 48.0


class Win32PlatformBackend(_BaseWin32PlatformBackend):
    """Win32 backend with backend-neutral wheel/precision-scroll events."""

    def __init__(self) -> None:
        super().__init__()
        self._user32.ScreenToClient.argtypes = [ctypes.c_void_p, ctypes.POINTER(_Point)]
        self._user32.ScreenToClient.restype = ctypes.c_bool

    def _wndproc(self, hwnd: int | None, message: int, wparam: int, lparam: int) -> int:
        handle = NativeWindowHandle(int(hwnd)) if hwnd else None
        if (
            handle is not None
            and handle in self._windows
            and message in (_WM_MOUSEWHEEL, _WM_MOUSEHWHEEL)
        ):
            point = _Point(
                _signed_word(int(lparam) & 0xFFFF),
                _signed_word((int(lparam) >> 16) & 0xFFFF),
            )
            if not self._user32.ScreenToClient(
                ctypes.c_void_p(handle.value),
                ctypes.byref(point),
            ):
                return super()._wndproc(hwnd, message, wparam, lparam)

            raw_delta = _signed_word((int(wparam) >> 16) & 0xFFFF)
            dip_delta = (raw_delta / _WHEEL_DELTA) * _WHEEL_STEP_DIP
            delta_x = dip_delta if message == _WM_MOUSEHWHEEL else 0.0
            delta_y = -dip_delta if message == _WM_MOUSEWHEEL else 0.0
            self._events.append(
                PlatformEvent(
                    PlatformEventKind.POINTER_SCROLL,
                    handle,
                    x=float(point.x),
                    y=float(point.y),
                    delta_x=delta_x,
                    delta_y=delta_y,
                    shift=self._key_is_down(0x10),
                    ctrl=self._key_is_down(0x11),
                    alt=self._key_is_down(0x12),
                    meta=self._key_is_down(0x5B) or self._key_is_down(0x5C),
                )
            )
            return 0

        return super()._wndproc(hwnd, message, wparam, lparam)
