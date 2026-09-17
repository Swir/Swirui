"""Hardened Win32 platform backend for SwirUI.

This module layers DPI-aware client-area sizing and minimum-track handling on
SwirUI's established direct Win32 implementation. Public window geometry stays
in logical DIPs at the framework layer; :class:`NativeWindowSpec` and
``resize_window`` reach the backend as desired *client-area* physical pixels.
The wrapper keeps decorated Win32 outer bounds from stealing pixels from the GPU
surface while preserving the existing event, monitor and DPI implementation.
"""

from __future__ import annotations

import ctypes
from typing import Any

from ._windows_legacy import (
    _CW_USEDEFAULT,
    _SWP_NOACTIVATE,
    _SWP_NOMOVE,
    _SWP_NOZORDER,
    _WM_DPICHANGED,
    _WM_KEYDOWN,
    _WM_KEYUP,
    _WM_SIZE,
    _WS_OVERLAPPEDWINDOW,
    _Point,
    _Rect,
)
from ._windows_legacy import (
    Win32PlatformBackend as _LegacyWin32PlatformBackend,
)
from .base import NativeWindowSpec
from .events import NativeWindowHandle, PlatformEvent, PlatformEventKind

_WM_GETMINMAXINFO = 0x0024
_VK_SHIFT = 0x10
_VK_CONTROL = 0x11
_VK_MENU = 0x12
_VK_LWIN = 0x5B
_VK_RWIN = 0x5C


class _MinMaxInfo(ctypes.Structure):
    _fields_ = [
        ("ptReserved", _Point),
        ("ptMaxSize", _Point),
        ("ptMaxPosition", _Point),
        ("ptMinTrackSize", _Point),
        ("ptMaxTrackSize", _Point),
    ]


class Win32PlatformBackend(_LegacyWin32PlatformBackend):
    """Direct Win32 backend with exact DPI-aware client-area geometry.

    ``CreateWindowExW`` and ``SetWindowPos`` size the decorated outer window, not
    its renderable client area. SwirUI surfaces, however, are defined by client
    pixels. This subclass converts requested client extents to outer extents with
    ``AdjustWindowRectExForDpi`` (falling back to ``AdjustWindowRectEx``), keeps
    the logical client size stable across ``WM_DPICHANGED``, and enforces logical
    minimum sizes through ``WM_GETMINMAXINFO``.
    """

    def __init__(self) -> None:
        super().__init__()
        self._logical_client_sizes: dict[NativeWindowHandle, tuple[float, float]] = {}
        self._logical_min_client_sizes: dict[NativeWindowHandle, tuple[float, float]] = {}
        self._dpi_resizing: set[NativeWindowHandle] = set()
        self._configure_client_area_signatures()

    def _configure_client_area_signatures(self) -> None:
        self._user32.GetClientRect.argtypes = [ctypes.c_void_p, ctypes.POINTER(_Rect)]
        self._user32.GetClientRect.restype = ctypes.c_bool
        self._user32.AdjustWindowRectEx.argtypes = [
            ctypes.POINTER(_Rect),
            ctypes.c_ulong,
            ctypes.c_bool,
            ctypes.c_ulong,
        ]
        self._user32.AdjustWindowRectEx.restype = ctypes.c_bool
        self._user32.GetKeyState.argtypes = [ctypes.c_int]
        self._user32.GetKeyState.restype = ctypes.c_short

        try:
            adjust_for_dpi: Any = self._user32.AdjustWindowRectExForDpi
        except AttributeError:
            adjust_for_dpi = None
        if adjust_for_dpi is not None:
            adjust_for_dpi.argtypes = [
                ctypes.POINTER(_Rect),
                ctypes.c_ulong,
                ctypes.c_bool,
                ctypes.c_ulong,
                ctypes.c_uint,
            ]
            adjust_for_dpi.restype = ctypes.c_bool

    def create_window(self, spec: NativeWindowSpec) -> NativeWindowHandle:
        """Create a decorated HWND whose client area matches ``spec`` exactly."""

        self._require_initialized()
        dpi = self._system_dpi_value()
        outer_width, outer_height = self._outer_size_for_client(spec.width, spec.height, dpi)
        hwnd = self._user32.CreateWindowExW(
            0,
            self._class_name,
            spec.title,
            _WS_OVERLAPPEDWINDOW,
            _CW_USEDEFAULT,
            _CW_USEDEFAULT,
            outer_width,
            outer_height,
            None,
            None,
            self._instance,
            None,
        )
        if not hwnd:
            raise OSError(self._last_error(), "CreateWindowExW failed for SwirUI.")

        handle = NativeWindowHandle(int(hwnd))
        self._windows.add(handle)
        scale = max(self.window_scale(handle), 1e-9)
        self._logical_client_sizes[handle] = (spec.width / scale, spec.height / scale)
        self._logical_min_client_sizes[handle] = (
            spec.min_width / scale,
            spec.min_height / scale,
        )

        try:
            # Correct once using the HWND's actual monitor DPI. This matters when
            # Windows places a CW_USEDEFAULT window on a monitor whose DPI differs
            # from the process/system DPI used for the initial outer rectangle.
            self._resize_client_area(handle, spec.width, spec.height)
        except Exception:
            self._logical_client_sizes.pop(handle, None)
            self._logical_min_client_sizes.pop(handle, None)
            self._windows.discard(handle)
            self._user32.DestroyWindow(ctypes.c_void_p(handle.value))
            raise
        return handle

    def client_size(self, handle: NativeWindowHandle) -> tuple[int, int]:
        """Return the current renderable Win32 client area in physical pixels."""

        self._require_window(handle)
        rect = _Rect()
        if not self._user32.GetClientRect(ctypes.c_void_p(handle.value), ctypes.byref(rect)):
            raise OSError(self._last_error(), "GetClientRect failed for SwirUI.")
        return (max(0, int(rect.right - rect.left)), max(0, int(rect.bottom - rect.top)))

    def resize_window(self, handle: NativeWindowHandle, width: int, height: int) -> None:
        """Resize the renderable client area to exact physical-pixel dimensions."""

        self._require_window(handle)
        if width <= 0 or height <= 0:
            raise ValueError("Win32 client dimensions must be positive.")
        scale = max(self.window_scale(handle), 1e-9)
        self._logical_client_sizes[handle] = (width / scale, height / scale)
        self._resize_client_area(handle, width, height)

    def destroy_window(self, handle: NativeWindowHandle) -> None:
        self._logical_client_sizes.pop(handle, None)
        self._logical_min_client_sizes.pop(handle, None)
        self._dpi_resizing.discard(handle)
        super().destroy_window(handle)

    def shutdown(self) -> None:
        self._logical_client_sizes.clear()
        self._logical_min_client_sizes.clear()
        self._dpi_resizing.clear()
        super().shutdown()

    def _system_dpi_value(self) -> int:
        try:
            get_dpi: Any = self._user32.GetDpiForSystem
        except AttributeError:
            get_dpi = None
        if get_dpi is not None:
            dpi = int(get_dpi())
            if dpi > 0:
                return dpi
        return max(96, round(self._system_scale() * 96.0))

    def _window_dpi_value(self, handle: NativeWindowHandle) -> int:
        try:
            get_dpi: Any = self._user32.GetDpiForWindow
        except AttributeError:
            get_dpi = None
        if get_dpi is not None:
            dpi = int(get_dpi(ctypes.c_void_p(handle.value)))
            if dpi > 0:
                return dpi
        return max(96, round(self.window_scale(handle) * 96.0))

    def _outer_size_for_client(self, width: int, height: int, dpi: int) -> tuple[int, int]:
        rect = _Rect(0, 0, int(width), int(height))
        adjusted = False
        try:
            adjust_for_dpi: Any = self._user32.AdjustWindowRectExForDpi
        except AttributeError:
            adjust_for_dpi = None
        if adjust_for_dpi is not None:
            adjusted = bool(
                adjust_for_dpi(
                    ctypes.byref(rect),
                    _WS_OVERLAPPEDWINDOW,
                    False,
                    0,
                    max(1, int(dpi)),
                )
            )
        if not adjusted:
            adjusted = bool(
                self._user32.AdjustWindowRectEx(
                    ctypes.byref(rect),
                    _WS_OVERLAPPEDWINDOW,
                    False,
                    0,
                )
            )
        if not adjusted:
            raise OSError(self._last_error(), "AdjustWindowRectEx failed for SwirUI.")
        return (max(1, int(rect.right - rect.left)), max(1, int(rect.bottom - rect.top)))

    def _resize_client_area(
        self,
        handle: NativeWindowHandle,
        width: int,
        height: int,
        *,
        dpi: int | None = None,
        x: int | None = None,
        y: int | None = None,
    ) -> None:
        target = (int(width), int(height))
        if x is None and y is None and self.client_size(handle) == target:
            return
        effective_dpi = self._window_dpi_value(handle) if dpi is None else max(1, int(dpi))
        outer_width, outer_height = self._outer_size_for_client(
            target[0], target[1], effective_dpi
        )
        flags = _SWP_NOZORDER | _SWP_NOACTIVATE
        if x is None or y is None:
            flags |= _SWP_NOMOVE
            x_value = 0
            y_value = 0
        else:
            x_value = int(x)
            y_value = int(y)
        if not self._user32.SetWindowPos(
            ctypes.c_void_p(handle.value),
            None,
            x_value,
            y_value,
            outer_width,
            outer_height,
            flags,
        ):
            raise OSError(self._last_error(), "SetWindowPos failed for SwirUI client resize.")

    def _apply_min_track_size(self, handle: NativeWindowHandle, lparam: int) -> None:
        logical_min = self._logical_min_client_sizes.get(handle)
        if logical_min is None or not lparam:
            return
        dpi = self._window_dpi_value(handle)
        scale = dpi / 96.0
        min_client_width = max(1, round(logical_min[0] * scale))
        min_client_height = max(1, round(logical_min[1] * scale))
        outer_width, outer_height = self._outer_size_for_client(
            min_client_width, min_client_height, dpi
        )
        info = ctypes.cast(
            ctypes.c_void_p(lparam), ctypes.POINTER(_MinMaxInfo)
        ).contents
        info.ptMinTrackSize.x = max(int(info.ptMinTrackSize.x), outer_width)
        info.ptMinTrackSize.y = max(int(info.ptMinTrackSize.y), outer_height)

    def _key_is_down(self, key_code: int) -> bool:
        return bool(int(self._user32.GetKeyState(key_code)) & 0x8000)

    def _keyboard_event(
        self,
        kind: PlatformEventKind,
        handle: NativeWindowHandle,
        key_code: int,
    ) -> PlatformEvent:
        return PlatformEvent(
            kind,
            handle,
            key_code=key_code,
            shift=self._key_is_down(_VK_SHIFT),
            ctrl=self._key_is_down(_VK_CONTROL),
            alt=self._key_is_down(_VK_MENU),
            meta=self._key_is_down(_VK_LWIN) or self._key_is_down(_VK_RWIN),
        )

    def _wndproc(self, hwnd: int | None, message: int, wparam: int, lparam: int) -> int:
        handle = NativeWindowHandle(int(hwnd)) if hwnd else None

        if handle is not None and message in (_WM_KEYDOWN, _WM_KEYUP):
            kind = (
                PlatformEventKind.KEY_DOWN
                if message == _WM_KEYDOWN
                else PlatformEventKind.KEY_UP
            )
            self._events.append(self._keyboard_event(kind, handle, int(wparam)))
            return int(
                self._user32.DefWindowProcW(
                    ctypes.c_void_p(hwnd),
                    message,
                    wparam,
                    lparam,
                )
            )

        if handle is not None and message == _WM_DPICHANGED:
            logical_size = self._logical_client_sizes.get(handle)
            if logical_size is None:
                return super()._wndproc(hwnd, message, wparam, lparam)

            dpi_x = int(wparam) & 0xFFFF
            scale = dpi_x / 96.0 if dpi_x > 0 else self.window_scale(handle)
            target_width = max(1, round(logical_size[0] * scale))
            target_height = max(1, round(logical_size[1] * scale))
            x: int | None = None
            y: int | None = None
            if lparam:
                suggested = ctypes.cast(
                    ctypes.c_void_p(lparam), ctypes.POINTER(_Rect)
                ).contents
                x = int(suggested.left)
                y = int(suggested.top)

            self._dpi_resizing.add(handle)
            try:
                self._resize_client_area(
                    handle,
                    target_width,
                    target_height,
                    dpi=dpi_x if dpi_x > 0 else None,
                    x=x,
                    y=y,
                )
            finally:
                self._dpi_resizing.discard(handle)

            self._events.append(
                PlatformEvent(PlatformEventKind.DPI_CHANGED, handle, scale=scale)
            )
            self._events.append(PlatformEvent(PlatformEventKind.DISPLAY_CHANGED, handle))
            return 0

        result = super()._wndproc(hwnd, message, wparam, lparam)

        if handle is not None and message == _WM_GETMINMAXINFO:
            self._apply_min_track_size(handle, lparam)
        elif (
            handle is not None
            and message == _WM_SIZE
            and handle in self._logical_client_sizes
            and handle not in self._dpi_resizing
        ):
            width = int(lparam) & 0xFFFF
            height = (int(lparam) >> 16) & 0xFFFF
            if width > 0 and height > 0:
                scale = max(self.window_scale(handle), 1e-9)
                self._logical_client_sizes[handle] = (width / scale, height / scale)

        return result
