"""Direct Win32 platform backend for SwirUI.

The backend talks to user32/kernel32 through :mod:`ctypes` and deliberately has
no dependency on Tk, Qt, SDL or another GUI toolkit.
"""

from __future__ import annotations

import ctypes
import sys
from collections import deque
from typing import Any

from .base import DisplayInfo, NativeWindowSpec
from .events import NativeWindowHandle, PlatformEvent, PlatformEventKind, PointerButton

_CS_HREDRAW = 0x0002
_CS_VREDRAW = 0x0001
_WS_OVERLAPPEDWINDOW = 0x00CF0000
_CW_USEDEFAULT = -2147483648
_SW_HIDE = 0
_SW_SHOW = 5
_PM_REMOVE = 0x0001
_SWP_NOMOVE = 0x0002
_SWP_NOZORDER = 0x0004
_SWP_NOACTIVATE = 0x0010

_WM_SIZE = 0x0005
_WM_SETFOCUS = 0x0007
_WM_KILLFOCUS = 0x0008
_WM_CLOSE = 0x0010
_WM_KEYDOWN = 0x0100
_WM_KEYUP = 0x0101
_WM_CHAR = 0x0102
_WM_MOUSEMOVE = 0x0200
_WM_LBUTTONDOWN = 0x0201
_WM_LBUTTONUP = 0x0202
_WM_RBUTTONDOWN = 0x0204
_WM_RBUTTONUP = 0x0205
_WM_MBUTTONDOWN = 0x0207
_WM_MBUTTONUP = 0x0208

_SM_CXSCREEN = 0
_SM_CYSCREEN = 1
_ERROR_CLASS_ALREADY_EXISTS = 1410


class _Point(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class _Msg(ctypes.Structure):
    _fields_ = [
        ("hwnd", ctypes.c_void_p),
        ("message", ctypes.c_uint),
        ("wParam", ctypes.c_size_t),
        ("lParam", ctypes.c_ssize_t),
        ("time", ctypes.c_uint),
        ("pt", _Point),
        ("lPrivate", ctypes.c_uint),
    ]


class _WndClass(ctypes.Structure):
    _fields_ = [
        ("style", ctypes.c_uint),
        ("lpfnWndProc", ctypes.c_void_p),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", ctypes.c_void_p),
        ("hIcon", ctypes.c_void_p),
        ("hCursor", ctypes.c_void_p),
        ("hbrBackground", ctypes.c_void_p),
        ("lpszMenuName", ctypes.c_wchar_p),
        ("lpszClassName", ctypes.c_wchar_p),
    ]


def _signed_word(value: int) -> int:
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


class Win32PlatformBackend:
    """Native Windows backend backed directly by Win32 APIs."""

    name = "win32"

    _initialized: bool
    _class_name: str
    _instance: int | None

    def __init__(self) -> None:
        if sys.platform != "win32":
            raise RuntimeError("Win32PlatformBackend can only run on Windows.")

        self._initialized = False
        self._class_name = "SwirUI.NativeWindow"
        self._events: deque[PlatformEvent] = deque()
        self._windows: set[NativeWindowHandle] = set()

        win_dll: Any = ctypes.__dict__["WinDLL"]
        self._user32: Any = win_dll("user32", use_last_error=True)
        self._kernel32: Any = win_dll("kernel32", use_last_error=True)
        self._configure_signatures()

        self._instance = self._kernel32.GetModuleHandleW(None)
        if not self._instance:
            raise OSError(self._last_error(), "GetModuleHandleW failed for SwirUI.")

        callback_factory: Any = ctypes.__dict__.get("WINFUNCTYPE", ctypes.CFUNCTYPE)
        self._wndproc_type: Any = callback_factory(
            ctypes.c_ssize_t,
            ctypes.c_void_p,
            ctypes.c_uint,
            ctypes.c_size_t,
            ctypes.c_ssize_t,
        )
        self._wndproc_callback: Any = self._wndproc_type(self._wndproc)

    def _configure_signatures(self) -> None:
        self._kernel32.GetModuleHandleW.argtypes = [ctypes.c_wchar_p]
        self._kernel32.GetModuleHandleW.restype = ctypes.c_void_p

        self._user32.RegisterClassW.argtypes = [ctypes.POINTER(_WndClass)]
        self._user32.RegisterClassW.restype = ctypes.c_ushort
        self._user32.CreateWindowExW.argtypes = [
            ctypes.c_ulong,
            ctypes.c_wchar_p,
            ctypes.c_wchar_p,
            ctypes.c_ulong,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_void_p,
        ]
        self._user32.CreateWindowExW.restype = ctypes.c_void_p
        self._user32.DefWindowProcW.argtypes = [
            ctypes.c_void_p,
            ctypes.c_uint,
            ctypes.c_size_t,
            ctypes.c_ssize_t,
        ]
        self._user32.DefWindowProcW.restype = ctypes.c_ssize_t
        self._user32.ShowWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self._user32.ShowWindow.restype = ctypes.c_bool
        self._user32.UpdateWindow.argtypes = [ctypes.c_void_p]
        self._user32.UpdateWindow.restype = ctypes.c_bool
        self._user32.DestroyWindow.argtypes = [ctypes.c_void_p]
        self._user32.DestroyWindow.restype = ctypes.c_bool
        self._user32.SetWindowTextW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p]
        self._user32.SetWindowTextW.restype = ctypes.c_bool
        self._user32.SetWindowPos.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_uint,
        ]
        self._user32.SetWindowPos.restype = ctypes.c_bool
        self._user32.PeekMessageW.argtypes = [
            ctypes.POINTER(_Msg),
            ctypes.c_void_p,
            ctypes.c_uint,
            ctypes.c_uint,
            ctypes.c_uint,
        ]
        self._user32.PeekMessageW.restype = ctypes.c_bool
        self._user32.TranslateMessage.argtypes = [ctypes.POINTER(_Msg)]
        self._user32.TranslateMessage.restype = ctypes.c_bool
        self._user32.DispatchMessageW.argtypes = [ctypes.POINTER(_Msg)]
        self._user32.DispatchMessageW.restype = ctypes.c_ssize_t
        self._user32.GetSystemMetrics.argtypes = [ctypes.c_int]
        self._user32.GetSystemMetrics.restype = ctypes.c_int

    def initialize(self) -> None:
        if self._initialized:
            return

        window_class = _WndClass()
        window_class.style = _CS_HREDRAW | _CS_VREDRAW
        window_class.lpfnWndProc = ctypes.cast(self._wndproc_callback, ctypes.c_void_p).value
        window_class.hInstance = self._instance
        window_class.lpszClassName = self._class_name

        atom = self._user32.RegisterClassW(ctypes.byref(window_class))
        if not atom:
            error = self._last_error()
            if error != _ERROR_CLASS_ALREADY_EXISTS:
                raise OSError(error, "RegisterClassW failed for SwirUI.")

        self._initialized = True

    def displays(self) -> tuple[DisplayInfo, ...]:
        self._require_initialized()
        width = int(self._user32.GetSystemMetrics(_SM_CXSCREEN))
        height = int(self._user32.GetSystemMetrics(_SM_CYSCREEN))
        scale = 1.0

        try:
            get_dpi: Any = self._user32.GetDpiForSystem
        except AttributeError:
            get_dpi = None

        if get_dpi is not None:
            get_dpi.argtypes = []
            get_dpi.restype = ctypes.c_uint
            dpi = int(get_dpi())
            if dpi > 0:
                scale = dpi / 96.0

        return (DisplayInfo("Primary display", width, height, scale=scale, primary=True),)

    def create_window(self, spec: NativeWindowSpec) -> NativeWindowHandle:
        self._require_initialized()
        hwnd = self._user32.CreateWindowExW(
            0,
            self._class_name,
            spec.title,
            _WS_OVERLAPPEDWINDOW,
            _CW_USEDEFAULT,
            _CW_USEDEFAULT,
            spec.width,
            spec.height,
            None,
            None,
            self._instance,
            None,
        )
        if not hwnd:
            raise OSError(self._last_error(), "CreateWindowExW failed for SwirUI.")

        handle = NativeWindowHandle(int(hwnd))
        self._windows.add(handle)
        return handle

    def show_window(self, handle: NativeWindowHandle) -> None:
        self._require_window(handle)
        hwnd = ctypes.c_void_p(handle.value)
        self._user32.ShowWindow(hwnd, _SW_SHOW)
        self._user32.UpdateWindow(hwnd)

    def hide_window(self, handle: NativeWindowHandle) -> None:
        self._require_window(handle)
        self._user32.ShowWindow(ctypes.c_void_p(handle.value), _SW_HIDE)

    def destroy_window(self, handle: NativeWindowHandle) -> None:
        self._require_window(handle)
        self._user32.DestroyWindow(ctypes.c_void_p(handle.value))
        self._windows.discard(handle)

    def set_window_title(self, handle: NativeWindowHandle, title: str) -> None:
        self._require_window(handle)
        self._user32.SetWindowTextW(ctypes.c_void_p(handle.value), title)

    def resize_window(self, handle: NativeWindowHandle, width: int, height: int) -> None:
        self._require_window(handle)
        self._user32.SetWindowPos(
            ctypes.c_void_p(handle.value),
            None,
            0,
            0,
            width,
            height,
            _SWP_NOMOVE | _SWP_NOZORDER | _SWP_NOACTIVATE,
        )

    def poll_events(self) -> tuple[PlatformEvent, ...]:
        self._require_initialized()
        message = _Msg()
        while self._user32.PeekMessageW(ctypes.byref(message), None, 0, 0, _PM_REMOVE):
            self._user32.TranslateMessage(ctypes.byref(message))
            self._user32.DispatchMessageW(ctypes.byref(message))

        events = tuple(self._events)
        self._events.clear()
        return events

    def shutdown(self) -> None:
        for handle in tuple(self._windows):
            self._user32.DestroyWindow(ctypes.c_void_p(handle.value))
        self._windows.clear()
        self._events.clear()
        self._initialized = False

    def _wndproc(self, hwnd: int | None, message: int, wparam: int, lparam: int) -> int:
        if hwnd:
            handle = NativeWindowHandle(int(hwnd))
            if message == _WM_CLOSE:
                self._events.append(PlatformEvent(PlatformEventKind.CLOSE, handle))
                return 0
            if message == _WM_SIZE:
                self._events.append(
                    PlatformEvent(
                        PlatformEventKind.RESIZE,
                        handle,
                        width=int(lparam) & 0xFFFF,
                        height=(int(lparam) >> 16) & 0xFFFF,
                    )
                )
            elif message == _WM_SETFOCUS:
                self._events.append(PlatformEvent(PlatformEventKind.FOCUS, handle, focused=True))
            elif message == _WM_KILLFOCUS:
                self._events.append(PlatformEvent(PlatformEventKind.FOCUS, handle, focused=False))
            elif message == _WM_MOUSEMOVE:
                self._events.append(self._pointer_event(PlatformEventKind.POINTER_MOVE, handle, lparam))
            elif message in (_WM_LBUTTONDOWN, _WM_RBUTTONDOWN, _WM_MBUTTONDOWN):
                self._events.append(
                    self._pointer_event(
                        PlatformEventKind.POINTER_DOWN,
                        handle,
                        lparam,
                        self._pointer_button(message),
                    )
                )
            elif message in (_WM_LBUTTONUP, _WM_RBUTTONUP, _WM_MBUTTONUP):
                self._events.append(
                    self._pointer_event(
                        PlatformEventKind.POINTER_UP,
                        handle,
                        lparam,
                        self._pointer_button(message),
                    )
                )
            elif message == _WM_KEYDOWN:
                self._events.append(
                    PlatformEvent(PlatformEventKind.KEY_DOWN, handle, key_code=int(wparam))
                )
            elif message == _WM_KEYUP:
                self._events.append(
                    PlatformEvent(PlatformEventKind.KEY_UP, handle, key_code=int(wparam))
                )
            elif message == _WM_CHAR:
                text = chr(int(wparam)) if int(wparam) <= 0x10FFFF else ""
                if text:
                    self._events.append(PlatformEvent(PlatformEventKind.TEXT_INPUT, handle, text=text))

        return int(
            self._user32.DefWindowProcW(
                ctypes.c_void_p(hwnd) if hwnd else None,
                message,
                wparam,
                lparam,
            )
        )

    @staticmethod
    def _pointer_event(
        kind: PlatformEventKind,
        handle: NativeWindowHandle,
        lparam: int,
        button: PointerButton | None = None,
    ) -> PlatformEvent:
        return PlatformEvent(
            kind,
            handle,
            x=float(_signed_word(int(lparam))),
            y=float(_signed_word(int(lparam) >> 16)),
            button=button,
        )

    @staticmethod
    def _pointer_button(message: int) -> PointerButton:
        if message in (_WM_LBUTTONDOWN, _WM_LBUTTONUP):
            return PointerButton.LEFT
        if message in (_WM_RBUTTONDOWN, _WM_RBUTTONUP):
            return PointerButton.RIGHT
        return PointerButton.MIDDLE

    @staticmethod
    def _last_error() -> int:
        get_last_error: Any = ctypes.__dict__["get_last_error"]
        return int(get_last_error())

    def _require_initialized(self) -> None:
        if not self._initialized:
            raise RuntimeError("Win32 platform backend is not initialized.")

    def _require_window(self, handle: NativeWindowHandle) -> None:
        self._require_initialized()
        if handle not in self._windows:
            raise ValueError("Unknown Win32 native window handle.")
