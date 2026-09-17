"""Direct X11 platform backend for Linux.

The backend intentionally depends only on ``ctypes`` and the system X11 client
library. SwirUI keeps the public platform contract backend-neutral while this
module translates X11 windows and events into the same normalized event stream
used by the Win32 backend.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import locale
from dataclasses import replace

from .base import DisplayInfo, NativeWindowSpec
from .events import NativeWindowHandle, PlatformEvent, PlatformEventKind, PointerButton

_KeyPress = 2
_KeyRelease = 3
_ButtonPress = 4
_ButtonRelease = 5
_MotionNotify = 6
_FocusIn = 9
_FocusOut = 10
_DestroyNotify = 17
_ConfigureNotify = 22
_ClientMessage = 33

_KeyPressMask = 1 << 0
_KeyReleaseMask = 1 << 1
_ButtonPressMask = 1 << 2
_ButtonReleaseMask = 1 << 3
_PointerMotionMask = 1 << 6
_StructureNotifyMask = 1 << 17
_FocusChangeMask = 1 << 21
_EVENT_MASK = (
    _KeyPressMask
    | _KeyReleaseMask
    | _ButtonPressMask
    | _ButtonReleaseMask
    | _PointerMotionMask
    | _StructureNotifyMask
    | _FocusChangeMask
)

_ShiftMask = 1 << 0
_ControlMask = 1 << 2
_Mod1Mask = 1 << 3
_Mod4Mask = 1 << 6

_XK_Tab = 0xFF09
_XK_ISO_Left_Tab = 0xFE20


class _XAnyEvent(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_int),
        ("serial", ctypes.c_ulong),
        ("send_event", ctypes.c_int),
        ("display", ctypes.c_void_p),
        ("window", ctypes.c_ulong),
    ]


class _XKeyEvent(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_int),
        ("serial", ctypes.c_ulong),
        ("send_event", ctypes.c_int),
        ("display", ctypes.c_void_p),
        ("window", ctypes.c_ulong),
        ("root", ctypes.c_ulong),
        ("subwindow", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("x", ctypes.c_int),
        ("y", ctypes.c_int),
        ("x_root", ctypes.c_int),
        ("y_root", ctypes.c_int),
        ("state", ctypes.c_uint),
        ("keycode", ctypes.c_uint),
        ("same_screen", ctypes.c_int),
    ]


class _XButtonEvent(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_int),
        ("serial", ctypes.c_ulong),
        ("send_event", ctypes.c_int),
        ("display", ctypes.c_void_p),
        ("window", ctypes.c_ulong),
        ("root", ctypes.c_ulong),
        ("subwindow", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("x", ctypes.c_int),
        ("y", ctypes.c_int),
        ("x_root", ctypes.c_int),
        ("y_root", ctypes.c_int),
        ("state", ctypes.c_uint),
        ("button", ctypes.c_uint),
        ("same_screen", ctypes.c_int),
    ]


class _XMotionEvent(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_int),
        ("serial", ctypes.c_ulong),
        ("send_event", ctypes.c_int),
        ("display", ctypes.c_void_p),
        ("window", ctypes.c_ulong),
        ("root", ctypes.c_ulong),
        ("subwindow", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("x", ctypes.c_int),
        ("y", ctypes.c_int),
        ("x_root", ctypes.c_int),
        ("y_root", ctypes.c_int),
        ("state", ctypes.c_uint),
        ("is_hint", ctypes.c_char),
        ("same_screen", ctypes.c_int),
    ]


class _XFocusChangeEvent(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_int),
        ("serial", ctypes.c_ulong),
        ("send_event", ctypes.c_int),
        ("display", ctypes.c_void_p),
        ("window", ctypes.c_ulong),
        ("mode", ctypes.c_int),
        ("detail", ctypes.c_int),
    ]


class _XConfigureEvent(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_int),
        ("serial", ctypes.c_ulong),
        ("send_event", ctypes.c_int),
        ("display", ctypes.c_void_p),
        ("event", ctypes.c_ulong),
        ("window", ctypes.c_ulong),
        ("x", ctypes.c_int),
        ("y", ctypes.c_int),
        ("width", ctypes.c_int),
        ("height", ctypes.c_int),
        ("border_width", ctypes.c_int),
        ("above", ctypes.c_ulong),
        ("override_redirect", ctypes.c_int),
    ]


class _XDestroyWindowEvent(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_int),
        ("serial", ctypes.c_ulong),
        ("send_event", ctypes.c_int),
        ("display", ctypes.c_void_p),
        ("event", ctypes.c_ulong),
        ("window", ctypes.c_ulong),
    ]


class _XClientMessageData(ctypes.Union):
    _fields_ = [
        ("b", ctypes.c_char * 20),
        ("s", ctypes.c_short * 10),
        ("l", ctypes.c_long * 5),
    ]


class _XClientMessageEvent(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_int),
        ("serial", ctypes.c_ulong),
        ("send_event", ctypes.c_int),
        ("display", ctypes.c_void_p),
        ("window", ctypes.c_ulong),
        ("message_type", ctypes.c_ulong),
        ("format", ctypes.c_int),
        ("data", _XClientMessageData),
    ]


class _XEvent(ctypes.Union):
    _fields_ = [
        ("type", ctypes.c_int),
        ("xany", _XAnyEvent),
        ("xkey", _XKeyEvent),
        ("xbutton", _XButtonEvent),
        ("xmotion", _XMotionEvent),
        ("xfocus", _XFocusChangeEvent),
        ("xconfigure", _XConfigureEvent),
        ("xdestroywindow", _XDestroyWindowEvent),
        ("xclient", _XClientMessageEvent),
        ("pad", ctypes.c_long * 24),
    ]


class LinuxX11PlatformBackend:
    """Direct X11 backend used when Linux exposes an X11 display."""

    name = "x11"

    def __init__(self) -> None:
        library = ctypes.util.find_library("X11") or "libX11.so.6"
        self._x11 = ctypes.CDLL(library)
        self._display: ctypes.c_void_p | None = None
        self._screen = 0
        self._root = 0
        self._wm_delete_window = 0
        self._windows: dict[NativeWindowHandle, NativeWindowSpec] = {}
        self._display_info: DisplayInfo | None = None
        self._encoding = locale.getpreferredencoding(False) or "utf-8"
        self._configure_signatures()

    def _configure_signatures(self) -> None:
        self._x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
        self._x11.XOpenDisplay.restype = ctypes.c_void_p
        self._x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
        self._x11.XCloseDisplay.restype = ctypes.c_int
        self._x11.XDefaultScreen.argtypes = [ctypes.c_void_p]
        self._x11.XDefaultScreen.restype = ctypes.c_int
        self._x11.XRootWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self._x11.XRootWindow.restype = ctypes.c_ulong
        self._x11.XDisplayWidth.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self._x11.XDisplayWidth.restype = ctypes.c_int
        self._x11.XDisplayHeight.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self._x11.XDisplayHeight.restype = ctypes.c_int
        self._x11.XCreateSimpleWindow.argtypes = [
            ctypes.c_void_p,
            ctypes.c_ulong,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_uint,
            ctypes.c_uint,
            ctypes.c_uint,
            ctypes.c_ulong,
            ctypes.c_ulong,
        ]
        self._x11.XCreateSimpleWindow.restype = ctypes.c_ulong
        self._x11.XSelectInput.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_long]
        self._x11.XSelectInput.restype = ctypes.c_int
        self._x11.XStoreName.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_char_p]
        self._x11.XStoreName.restype = ctypes.c_int
        self._x11.XInternAtom.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
        self._x11.XInternAtom.restype = ctypes.c_ulong
        self._x11.XSetWMProtocols.argtypes = [
            ctypes.c_void_p,
            ctypes.c_ulong,
            ctypes.POINTER(ctypes.c_ulong),
            ctypes.c_int,
        ]
        self._x11.XSetWMProtocols.restype = ctypes.c_int
        self._x11.XMapWindow.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        self._x11.XMapWindow.restype = ctypes.c_int
        self._x11.XUnmapWindow.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        self._x11.XUnmapWindow.restype = ctypes.c_int
        self._x11.XDestroyWindow.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        self._x11.XDestroyWindow.restype = ctypes.c_int
        self._x11.XResizeWindow.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_uint, ctypes.c_uint]
        self._x11.XResizeWindow.restype = ctypes.c_int
        self._x11.XPending.argtypes = [ctypes.c_void_p]
        self._x11.XPending.restype = ctypes.c_int
        self._x11.XNextEvent.argtypes = [ctypes.c_void_p, ctypes.POINTER(_XEvent)]
        self._x11.XNextEvent.restype = ctypes.c_int
        self._x11.XLookupKeysym.argtypes = [ctypes.POINTER(_XKeyEvent), ctypes.c_int]
        self._x11.XLookupKeysym.restype = ctypes.c_ulong
        self._x11.XLookupString.argtypes = [
            ctypes.POINTER(_XKeyEvent),
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_ulong),
            ctypes.c_void_p,
        ]
        self._x11.XLookupString.restype = ctypes.c_int
        self._x11.XFlush.argtypes = [ctypes.c_void_p]
        self._x11.XFlush.restype = ctypes.c_int
        self._x11.XSync.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self._x11.XSync.restype = ctypes.c_int

    def initialize(self) -> None:
        if self._display is not None:
            return
        raw_display = self._x11.XOpenDisplay(None)
        if not raw_display:
            raise RuntimeError("SwirUI could not open the X11 display.")
        self._display = ctypes.c_void_p(raw_display)
        self._screen = int(self._x11.XDefaultScreen(self._display))
        self._root = int(self._x11.XRootWindow(self._display, self._screen))
        self._wm_delete_window = int(
            self._x11.XInternAtom(self._display, b"WM_DELETE_WINDOW", 0)
        )
        width = int(self._x11.XDisplayWidth(self._display, self._screen))
        height = int(self._x11.XDisplayHeight(self._display, self._screen))
        self._display_info = DisplayInfo(
            name=f"X11 screen {self._screen}",
            width=width,
            height=height,
            primary=True,
        )

    def displays(self) -> tuple[DisplayInfo, ...]:
        self._require_initialized()
        assert self._display_info is not None
        return (self._display_info,)

    def create_window(self, spec: NativeWindowSpec) -> NativeWindowHandle:
        display = self._require_initialized()
        window_id = int(
            self._x11.XCreateSimpleWindow(
                display,
                self._root,
                0,
                0,
                spec.width,
                spec.height,
                0,
                0,
                0,
            )
        )
        if window_id <= 0:
            raise RuntimeError("XCreateSimpleWindow failed for SwirUI.")
        handle = NativeWindowHandle(window_id)
        self._windows[handle] = spec
        self._x11.XSelectInput(display, window_id, _EVENT_MASK)
        self._x11.XStoreName(display, window_id, spec.title.encode("utf-8"))
        protocol = ctypes.c_ulong(self._wm_delete_window)
        self._x11.XSetWMProtocols(display, window_id, ctypes.byref(protocol), 1)
        self._flush()
        return handle

    def window_scale(self, handle: NativeWindowHandle) -> float:
        self._require_window(handle)
        return 1.0

    def window_display(self, handle: NativeWindowHandle) -> DisplayInfo | None:
        self._require_window(handle)
        return self._display_info

    def show_window(self, handle: NativeWindowHandle) -> None:
        display = self._require_window(handle)
        self._x11.XMapWindow(display, handle.value)
        self._flush()

    def hide_window(self, handle: NativeWindowHandle) -> None:
        display = self._require_window(handle)
        self._x11.XUnmapWindow(display, handle.value)
        self._flush()

    def destroy_window(self, handle: NativeWindowHandle) -> None:
        display = self._require_window(handle)
        self._x11.XDestroyWindow(display, handle.value)
        del self._windows[handle]
        self._flush()

    def set_window_title(self, handle: NativeWindowHandle, title: str) -> None:
        display = self._require_window(handle)
        self._x11.XStoreName(display, handle.value, title.encode("utf-8"))
        self._windows[handle] = replace(self._windows[handle], title=title)
        self._flush()

    def resize_window(self, handle: NativeWindowHandle, width: int, height: int) -> None:
        if width <= 0 or height <= 0:
            raise ValueError("X11 window dimensions must be positive.")
        display = self._require_window(handle)
        self._x11.XResizeWindow(display, handle.value, width, height)
        self._windows[handle] = replace(self._windows[handle], width=width, height=height)
        self._flush()

    def poll_events(self) -> tuple[PlatformEvent, ...]:
        display = self._require_initialized()
        normalized: list[PlatformEvent] = []
        while self._x11.XPending(display) > 0:
            event = _XEvent()
            self._x11.XNextEvent(display, ctypes.byref(event))
            normalized.extend(self._normalize_event(event))
        return tuple(normalized)

    def shutdown(self) -> None:
        if self._display is None:
            return
        for handle in tuple(self._windows):
            self._x11.XDestroyWindow(self._display, handle.value)
        self._windows.clear()
        self._x11.XSync(self._display, 0)
        self._x11.XCloseDisplay(self._display)
        self._display = None
        self._display_info = None
        self._root = 0
        self._wm_delete_window = 0

    def _normalize_event(self, event: _XEvent) -> tuple[PlatformEvent, ...]:
        handle = NativeWindowHandle(int(event.xany.window))
        if handle not in self._windows:
            return ()

        if event.type == _ConfigureNotify:
            return (
                PlatformEvent(
                    PlatformEventKind.RESIZE,
                    handle,
                    width=max(1, int(event.xconfigure.width)),
                    height=max(1, int(event.xconfigure.height)),
                ),
            )
        if event.type in (_FocusIn, _FocusOut):
            return (
                PlatformEvent(
                    PlatformEventKind.FOCUS,
                    handle,
                    focused=event.type == _FocusIn,
                ),
            )
        if event.type == _MotionNotify:
            return (
                PlatformEvent(
                    PlatformEventKind.POINTER_MOVE,
                    handle,
                    x=float(event.xmotion.x),
                    y=float(event.xmotion.y),
                ),
            )
        if event.type in (_ButtonPress, _ButtonRelease):
            button = self._pointer_button(int(event.xbutton.button))
            if button is None:
                return ()
            kind = (
                PlatformEventKind.POINTER_DOWN
                if event.type == _ButtonPress
                else PlatformEventKind.POINTER_UP
            )
            return (
                PlatformEvent(
                    kind,
                    handle,
                    x=float(event.xbutton.x),
                    y=float(event.xbutton.y),
                    button=button,
                ),
            )
        if event.type in (_KeyPress, _KeyRelease):
            keyboard = self._keyboard_event(event)
            if event.type == _KeyRelease:
                return (keyboard,)
            text = self._text_input_event(event)
            return (keyboard,) if text is None else (keyboard, text)
        if event.type == _ClientMessage:
            if int(event.xclient.data.l[0]) == self._wm_delete_window:
                return (PlatformEvent(PlatformEventKind.CLOSE, handle),)
        if event.type == _DestroyNotify:
            return (PlatformEvent(PlatformEventKind.CLOSE, handle),)
        return ()

    def _keyboard_event(self, event: _XEvent) -> PlatformEvent:
        keysym = int(self._x11.XLookupKeysym(ctypes.byref(event.xkey), 0))
        state = int(event.xkey.state)
        kind = (
            PlatformEventKind.KEY_DOWN
            if event.type == _KeyPress
            else PlatformEventKind.KEY_UP
        )
        return PlatformEvent(
            kind,
            NativeWindowHandle(int(event.xkey.window)),
            key_code=self._normalize_key_code(keysym),
            shift=bool(state & _ShiftMask),
            ctrl=bool(state & _ControlMask),
            alt=bool(state & _Mod1Mask),
            meta=bool(state & _Mod4Mask),
        )

    def _text_input_event(self, event: _XEvent) -> PlatformEvent | None:
        buffer = ctypes.create_string_buffer(64)
        keysym = ctypes.c_ulong()
        length = int(
            self._x11.XLookupString(
                ctypes.byref(event.xkey),
                buffer,
                len(buffer) - 1,
                ctypes.byref(keysym),
                None,
            )
        )
        if length <= 0:
            return None
        text = bytes(buffer.raw[:length]).decode(self._encoding, errors="ignore")
        if not text or not any(character.isprintable() for character in text):
            return None
        return PlatformEvent(
            PlatformEventKind.TEXT_INPUT,
            NativeWindowHandle(int(event.xkey.window)),
            text=text,
            shift=bool(int(event.xkey.state) & _ShiftMask),
            ctrl=bool(int(event.xkey.state) & _ControlMask),
            alt=bool(int(event.xkey.state) & _Mod1Mask),
            meta=bool(int(event.xkey.state) & _Mod4Mask),
        )

    @staticmethod
    def _normalize_key_code(keysym: int) -> int:
        if keysym in (_XK_Tab, _XK_ISO_Left_Tab):
            return 0x09
        return keysym

    @staticmethod
    def _pointer_button(button: int) -> PointerButton | None:
        return {
            1: PointerButton.LEFT,
            2: PointerButton.MIDDLE,
            3: PointerButton.RIGHT,
        }.get(button)

    def _flush(self) -> None:
        display = self._require_initialized()
        self._x11.XFlush(display)

    def _require_initialized(self) -> ctypes.c_void_p:
        if self._display is None:
            raise RuntimeError("Platform backend is not initialized.")
        return self._display

    def _require_window(self, handle: NativeWindowHandle) -> ctypes.c_void_p:
        display = self._require_initialized()
        if handle not in self._windows:
            raise ValueError("Unknown native window handle.")
        return display
