"""Direct Cocoa/AppKit platform backend for macOS.

SwirUI intentionally keeps the native platform layer dependency-light.  This
backend talks to Objective-C/AppKit through ``ctypes`` and the system Objective-C
runtime instead of requiring PyObjC, while exposing the same backend-neutral
window and event contract used by Win32 and X11.
"""

from __future__ import annotations

import ctypes
import platform
from dataclasses import dataclass, replace
from typing import Any

from .base import DisplayInfo, NativeWindowSpec
from .events import NativeWindowHandle, PlatformEvent, PlatformEventKind, PointerButton


class _NSPoint(ctypes.Structure):
    _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double)]


class _NSSize(ctypes.Structure):
    _fields_ = [("width", ctypes.c_double), ("height", ctypes.c_double)]


class _NSRect(ctypes.Structure):
    _fields_ = [("origin", _NSPoint), ("size", _NSSize)]


_CGPoint = _NSPoint
_CGSize = _NSSize
_CGRect = _NSRect

_NSWindowStyleMaskTitled = 1 << 0
_NSWindowStyleMaskClosable = 1 << 1
_NSWindowStyleMaskMiniaturizable = 1 << 2
_NSWindowStyleMaskResizable = 1 << 3
_NSBackingStoreBuffered = 2
_NSApplicationActivationPolicyRegular = 0
_NSUIntegerMax = ctypes.c_ulong(-1).value

_NSEventTypeLeftMouseDown = 1
_NSEventTypeLeftMouseUp = 2
_NSEventTypeRightMouseDown = 3
_NSEventTypeRightMouseUp = 4
_NSEventTypeMouseMoved = 5
_NSEventTypeLeftMouseDragged = 6
_NSEventTypeRightMouseDragged = 7
_NSEventTypeKeyDown = 10
_NSEventTypeKeyUp = 11
_NSEventTypeOtherMouseDown = 25
_NSEventTypeOtherMouseUp = 26
_NSEventTypeOtherMouseDragged = 27

_NSEventModifierFlagShift = 1 << 17
_NSEventModifierFlagControl = 1 << 18
_NSEventModifierFlagOption = 1 << 19
_NSEventModifierFlagCommand = 1 << 20

_MAC_KEYCODE_TAB = 48
_FRAME_EPSILON = 0.5


@dataclass(slots=True)
class _WindowState:
    spec: NativeWindowSpec
    visible: bool = False
    hidden_explicitly: bool = False
    focused: bool = False
    content_width: int = 0
    content_height: int = 0


class MacOSCocoaPlatformBackend:
    """Native macOS backend implemented directly on Cocoa/AppKit."""

    name = "cocoa"

    def __init__(self) -> None:
        self._objc = ctypes.CDLL("/usr/lib/libobjc.A.dylib")
        self._appkit = ctypes.CDLL(
            "/System/Library/Frameworks/AppKit.framework/AppKit"
        )
        self._core_graphics = ctypes.CDLL(
            "/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics"
        )
        self._core_foundation = ctypes.CDLL(
            "/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation"
        )
        self._configure_runtime()
        self._selectors: dict[str, int] = {}
        self._application = 0
        self._autorelease_pool = 0
        self._run_loop_mode = 0
        self._distant_past = 0
        self._windows: dict[NativeWindowHandle, _WindowState] = {}
        self._display_by_id: dict[int, DisplayInfo] = {}
        self._display_order: tuple[int, ...] = ()

    def _configure_runtime(self) -> None:
        self._objc.objc_getClass.argtypes = [ctypes.c_char_p]
        self._objc.objc_getClass.restype = ctypes.c_void_p
        self._objc.sel_registerName.argtypes = [ctypes.c_char_p]
        self._objc.sel_registerName.restype = ctypes.c_void_p

        self._core_graphics.CGGetActiveDisplayList.argtypes = [
            ctypes.c_uint32,
            ctypes.POINTER(ctypes.c_uint32),
            ctypes.POINTER(ctypes.c_uint32),
        ]
        self._core_graphics.CGGetActiveDisplayList.restype = ctypes.c_int32
        self._core_graphics.CGMainDisplayID.argtypes = []
        self._core_graphics.CGMainDisplayID.restype = ctypes.c_uint32
        self._core_graphics.CGDisplayBounds.argtypes = [ctypes.c_uint32]
        self._core_graphics.CGDisplayBounds.restype = _CGRect
        self._core_graphics.CGDisplayPixelsWide.argtypes = [ctypes.c_uint32]
        self._core_graphics.CGDisplayPixelsWide.restype = ctypes.c_size_t
        self._core_graphics.CGDisplayPixelsHigh.argtypes = [ctypes.c_uint32]
        self._core_graphics.CGDisplayPixelsHigh.restype = ctypes.c_size_t
        self._core_graphics.CGDisplayCopyDisplayMode.argtypes = [ctypes.c_uint32]
        self._core_graphics.CGDisplayCopyDisplayMode.restype = ctypes.c_void_p
        self._core_graphics.CGDisplayModeGetRefreshRate.argtypes = [ctypes.c_void_p]
        self._core_graphics.CGDisplayModeGetRefreshRate.restype = ctypes.c_double
        self._core_foundation.CFRelease.argtypes = [ctypes.c_void_p]
        self._core_foundation.CFRelease.restype = None

    def initialize(self) -> None:
        if self._application:
            return

        pool_class = self._class("NSAutoreleasePool")
        self._autorelease_pool = int(
            self._send(self._send(pool_class, "alloc"), "init") or 0
        )
        app_class = self._class("NSApplication")
        self._application = int(self._send(app_class, "sharedApplication") or 0)
        if not self._application:
            raise RuntimeError("SwirUI could not initialize NSApplication.")

        self._send(
            self._application,
            "setActivationPolicy:",
            None,
            (ctypes.c_long,),
            _NSApplicationActivationPolicyRegular,
        )
        self._send(self._application, "finishLaunching", None)
        self._run_loop_mode = self._ns_string("kCFRunLoopDefaultMode")
        date_class = self._class("NSDate")
        self._distant_past = int(self._send(date_class, "distantPast") or 0)
        self._refresh_displays()

    def displays(self) -> tuple[DisplayInfo, ...]:
        self._require_initialized()
        return tuple(self._display_by_id[display_id] for display_id in self._display_order)

    def create_window(self, spec: NativeWindowSpec) -> NativeWindowHandle:
        self._require_initialized()
        window_class = self._class("NSWindow")
        allocated = self._send(window_class, "alloc")
        rect = _NSRect(_NSPoint(0.0, 0.0), _NSSize(float(spec.width), float(spec.height)))
        style = (
            _NSWindowStyleMaskTitled
            | _NSWindowStyleMaskClosable
            | _NSWindowStyleMaskMiniaturizable
            | _NSWindowStyleMaskResizable
        )
        window = int(
            self._send(
                allocated,
                "initWithContentRect:styleMask:backing:defer:",
                ctypes.c_void_p,
                (_NSRect, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_bool),
                rect,
                style,
                _NSBackingStoreBuffered,
                False,
            )
            or 0
        )
        if not window:
            raise RuntimeError("SwirUI could not create an NSWindow.")

        self._send(window, "setReleasedWhenClosed:", None, (ctypes.c_bool,), False)
        self._send(
            window,
            "setMinSize:",
            None,
            (_NSSize,),
            _NSSize(float(spec.min_width), float(spec.min_height)),
        )
        self._send(
            window,
            "setTitle:",
            None,
            (ctypes.c_void_p,),
            self._ns_string(spec.title),
        )
        self._send(window, "setAcceptsMouseMovedEvents:", None, (ctypes.c_bool,), True)

        handle = NativeWindowHandle(window)
        self._windows[handle] = _WindowState(
            spec=spec,
            content_width=spec.width,
            content_height=spec.height,
        )
        return handle

    def window_scale(self, handle: NativeWindowHandle) -> float:
        self._require_window(handle)
        value = float(self._send(handle.value, "backingScaleFactor", ctypes.c_double) or 1.0)
        return max(0.01, value)

    def window_display(self, handle: NativeWindowHandle) -> DisplayInfo | None:
        self._require_window(handle)
        screen = int(self._send(handle.value, "screen") or 0)
        if screen:
            description = int(self._send(screen, "deviceDescription") or 0)
            if description:
                key = self._ns_string("NSScreenNumber")
                number = int(
                    self._send(
                        description,
                        "objectForKey:",
                        ctypes.c_void_p,
                        (ctypes.c_void_p,),
                        key,
                    )
                    or 0
                )
                if number:
                    display_id = int(
                        self._send(number, "unsignedIntValue", ctypes.c_uint32) or 0
                    )
                    display = self._display_by_id.get(display_id)
                    if display is not None:
                        return display
        return self.displays()[0] if self._display_order else None

    def show_window(self, handle: NativeWindowHandle) -> None:
        state = self._require_window(handle)
        self._send(
            handle.value,
            "makeKeyAndOrderFront:",
            None,
            (ctypes.c_void_p,),
            None,
        )
        self._send(
            self._application,
            "activateIgnoringOtherApps:",
            None,
            (ctypes.c_bool,),
            True,
        )
        state.visible = True
        state.hidden_explicitly = False

    def hide_window(self, handle: NativeWindowHandle) -> None:
        state = self._require_window(handle)
        self._send(handle.value, "orderOut:", None, (ctypes.c_void_p,), None)
        state.visible = False
        state.hidden_explicitly = True

    def destroy_window(self, handle: NativeWindowHandle) -> None:
        self._require_window(handle)
        self._send(handle.value, "close", None)
        self._send(handle.value, "release", None)
        del self._windows[handle]

    def set_window_title(self, handle: NativeWindowHandle, title: str) -> None:
        state = self._require_window(handle)
        self._send(
            handle.value,
            "setTitle:",
            None,
            (ctypes.c_void_p,),
            self._ns_string(title),
        )
        state.spec = replace(state.spec, title=title)

    def resize_window(self, handle: NativeWindowHandle, width: int, height: int) -> None:
        if width <= 0 or height <= 0:
            raise ValueError("Cocoa window dimensions must be positive.")
        state = self._require_window(handle)
        self._send(
            handle.value,
            "setContentSize:",
            None,
            (_NSSize,),
            _NSSize(float(width), float(height)),
        )
        state.spec = replace(state.spec, width=width, height=height)

    def poll_events(self) -> tuple[PlatformEvent, ...]:
        self._require_initialized()
        normalized: list[PlatformEvent] = []
        for _ in range(256):
            event = int(
                self._send(
                    self._application,
                    "nextEventMatchingMask:untilDate:inMode:dequeue:",
                    ctypes.c_void_p,
                    (ctypes.c_ulong, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_bool),
                    _NSUIntegerMax,
                    self._distant_past,
                    self._run_loop_mode,
                    True,
                )
                or 0
            )
            if not event:
                break
            normalized.extend(self._normalize_event(event))
            self._send(
                self._application,
                "sendEvent:",
                None,
                (ctypes.c_void_p,),
                event,
            )

        normalized.extend(self._poll_window_state())
        return tuple(normalized)

    def shutdown(self) -> None:
        if not self._application:
            return
        for handle in tuple(self._windows):
            self.destroy_window(handle)
        self._display_by_id.clear()
        self._display_order = ()
        self._run_loop_mode = 0
        self._distant_past = 0
        self._application = 0
        if self._autorelease_pool:
            self._send(self._autorelease_pool, "drain", None)
            self._autorelease_pool = 0

    def _refresh_displays(self) -> None:
        count = ctypes.c_uint32()
        error = int(self._core_graphics.CGGetActiveDisplayList(0, None, ctypes.byref(count)))
        if error != 0 or count.value == 0:
            raise RuntimeError("SwirUI could not enumerate active macOS displays.")

        display_ids = (ctypes.c_uint32 * count.value)()
        error = int(
            self._core_graphics.CGGetActiveDisplayList(
                count.value,
                display_ids,
                ctypes.byref(count),
            )
        )
        if error != 0:
            raise RuntimeError("SwirUI could not enumerate active macOS displays.")

        main_display = int(self._core_graphics.CGMainDisplayID())
        by_id: dict[int, DisplayInfo] = {}
        order: list[int] = []
        for raw_id in display_ids[: count.value]:
            display_id = int(raw_id)
            bounds = self._core_graphics.CGDisplayBounds(display_id)
            pixel_width = int(self._core_graphics.CGDisplayPixelsWide(display_id))
            pixel_height = int(self._core_graphics.CGDisplayPixelsHigh(display_id))
            logical_width = max(1, int(round(bounds.size.width)))
            logical_height = max(1, int(round(bounds.size.height)))
            scale = pixel_width / bounds.size.width if bounds.size.width > 0.0 else 1.0
            mode = self._core_graphics.CGDisplayCopyDisplayMode(display_id)
            refresh = 60.0
            if mode:
                try:
                    reported = float(self._core_graphics.CGDisplayModeGetRefreshRate(mode))
                    if reported > 0.0:
                        refresh = reported
                finally:
                    self._core_foundation.CFRelease(mode)
            by_id[display_id] = DisplayInfo(
                name=f"macOS display {display_id}",
                width=logical_width,
                height=logical_height,
                scale=max(0.01, scale),
                primary=display_id == main_display,
                x=int(round(bounds.origin.x)),
                y=int(round(bounds.origin.y)),
                work_x=int(round(bounds.origin.x)),
                work_y=int(round(bounds.origin.y)),
                work_width=logical_width,
                work_height=logical_height,
                refresh_rate_hz=refresh,
            )
            order.append(display_id)

        order.sort(key=lambda item: (not by_id[item].primary, by_id[item].x, by_id[item].y))
        self._display_by_id = by_id
        self._display_order = tuple(order)

    def _normalize_event(self, event: int) -> tuple[PlatformEvent, ...]:
        window = int(self._send(event, "window") or 0)
        if not window:
            return ()
        handle = NativeWindowHandle(window)
        state = self._windows.get(handle)
        if state is None:
            return ()

        event_type = int(self._send(event, "type", ctypes.c_ulong) or 0)
        if event_type in {
            _NSEventTypeMouseMoved,
            _NSEventTypeLeftMouseDragged,
            _NSEventTypeRightMouseDragged,
            _NSEventTypeOtherMouseDragged,
        }:
            point = self._send_struct(event, "locationInWindow", _NSPoint)
            return (
                PlatformEvent(
                    PlatformEventKind.POINTER_MOVE,
                    handle,
                    x=float(point.x),
                    y=max(0.0, float(state.content_height) - float(point.y)),
                ),
            )

        if event_type in {
            _NSEventTypeLeftMouseDown,
            _NSEventTypeLeftMouseUp,
            _NSEventTypeRightMouseDown,
            _NSEventTypeRightMouseUp,
            _NSEventTypeOtherMouseDown,
            _NSEventTypeOtherMouseUp,
        }:
            button = self._pointer_button(event_type, event)
            if button is None:
                return ()
            point = self._send_struct(event, "locationInWindow", _NSPoint)
            kind = (
                PlatformEventKind.POINTER_DOWN
                if event_type
                in {
                    _NSEventTypeLeftMouseDown,
                    _NSEventTypeRightMouseDown,
                    _NSEventTypeOtherMouseDown,
                }
                else PlatformEventKind.POINTER_UP
            )
            return (
                PlatformEvent(
                    kind,
                    handle,
                    x=float(point.x),
                    y=max(0.0, float(state.content_height) - float(point.y)),
                    button=button,
                ),
            )

        if event_type in {_NSEventTypeKeyDown, _NSEventTypeKeyUp}:
            modifiers = self._modifiers(event)
            key_code = int(self._send(event, "keyCode", ctypes.c_ushort) or 0)
            keyboard = PlatformEvent(
                PlatformEventKind.KEY_DOWN
                if event_type == _NSEventTypeKeyDown
                else PlatformEventKind.KEY_UP,
                handle,
                key_code=self._normalize_key_code(key_code),
                **modifiers,
            )
            if event_type == _NSEventTypeKeyUp:
                return (keyboard,)
            text = self._event_text(event)
            if not text:
                return (keyboard,)
            return (
                keyboard,
                PlatformEvent(
                    PlatformEventKind.TEXT_INPUT,
                    handle,
                    text=text,
                    **modifiers,
                ),
            )
        return ()

    def _poll_window_state(self) -> list[PlatformEvent]:
        events: list[PlatformEvent] = []
        for handle, state in tuple(self._windows.items()):
            content_view = int(self._send(handle.value, "contentView") or 0)
            if content_view:
                frame = self._send_struct(content_view, "frame", _NSRect)
                width = max(1, int(round(frame.size.width)))
                height = max(1, int(round(frame.size.height)))
                if width != state.content_width or height != state.content_height:
                    state.content_width = width
                    state.content_height = height
                    state.spec = replace(state.spec, width=width, height=height)
                    events.append(
                        PlatformEvent(
                            PlatformEventKind.RESIZE,
                            handle,
                            width=width,
                            height=height,
                        )
                    )

            focused = bool(self._send(handle.value, "isKeyWindow", ctypes.c_bool))
            if focused != state.focused:
                state.focused = focused
                events.append(
                    PlatformEvent(
                        PlatformEventKind.FOCUS,
                        handle,
                        focused=focused,
                    )
                )

            visible = bool(self._send(handle.value, "isVisible", ctypes.c_bool))
            if state.visible and not visible and not state.hidden_explicitly:
                state.visible = False
                events.append(PlatformEvent(PlatformEventKind.CLOSE, handle))
            elif visible:
                state.visible = True
        return events

    def _pointer_button(self, event_type: int, event: int) -> PointerButton | None:
        if event_type in {_NSEventTypeLeftMouseDown, _NSEventTypeLeftMouseUp}:
            return PointerButton.LEFT
        if event_type in {_NSEventTypeRightMouseDown, _NSEventTypeRightMouseUp}:
            return PointerButton.RIGHT
        button_number = int(self._send(event, "buttonNumber", ctypes.c_long) or 0)
        return PointerButton.MIDDLE if button_number == 2 else None

    def _modifiers(self, event: int) -> dict[str, bool]:
        flags = int(self._send(event, "modifierFlags", ctypes.c_ulong) or 0)
        return {
            "shift": bool(flags & _NSEventModifierFlagShift),
            "ctrl": bool(flags & _NSEventModifierFlagControl),
            "alt": bool(flags & _NSEventModifierFlagOption),
            "meta": bool(flags & _NSEventModifierFlagCommand),
        }

    def _event_text(self, event: int) -> str | None:
        characters = int(self._send(event, "characters") or 0)
        if not characters:
            return None
        raw = self._send(characters, "UTF8String", ctypes.c_char_p)
        if not raw:
            return None
        text = raw.decode("utf-8", errors="ignore")
        if not text or not any(character.isprintable() for character in text):
            return None
        return text

    @staticmethod
    def _normalize_key_code(key_code: int) -> int:
        return 0x09 if key_code == _MAC_KEYCODE_TAB else key_code

    def _ns_string(self, value: str) -> int:
        string_class = self._class("NSString")
        result = self._send(
            string_class,
            "stringWithUTF8String:",
            ctypes.c_void_p,
            (ctypes.c_char_p,),
            value.encode("utf-8"),
        )
        return int(result or 0)

    def _class(self, name: str) -> int:
        value = int(self._objc.objc_getClass(name.encode("ascii")) or 0)
        if not value:
            raise RuntimeError(f"Objective-C class {name!r} is unavailable.")
        return value

    def _selector(self, name: str) -> int:
        selector = self._selectors.get(name)
        if selector is None:
            selector = int(self._objc.sel_registerName(name.encode("ascii")) or 0)
            if not selector:
                raise RuntimeError(f"Objective-C selector {name!r} is unavailable.")
            self._selectors[name] = selector
        return selector

    def _send(
        self,
        receiver: int | ctypes.c_void_p | None,
        selector: str,
        restype: Any = ctypes.c_void_p,
        argtypes: tuple[Any, ...] = (),
        *args: Any,
    ) -> Any:
        receiver_value = int(receiver.value) if isinstance(receiver, ctypes.c_void_p) else int(receiver or 0)
        if not receiver_value:
            return None if restype is ctypes.c_void_p else 0
        address = ctypes.cast(self._objc.objc_msgSend, ctypes.c_void_p).value
        if not address:
            raise RuntimeError("objc_msgSend is unavailable.")
        prototype = ctypes.CFUNCTYPE(restype, ctypes.c_void_p, ctypes.c_void_p, *argtypes)
        function = prototype(address)
        return function(
            ctypes.c_void_p(receiver_value),
            ctypes.c_void_p(self._selector(selector)),
            *args,
        )

    def _send_struct(
        self,
        receiver: int,
        selector: str,
        result_type: type[ctypes.Structure],
    ) -> Any:
        receiver_ptr = ctypes.c_void_p(receiver)
        selector_ptr = ctypes.c_void_p(self._selector(selector))
        if platform.machine().lower() in {"x86_64", "amd64"} and ctypes.sizeof(result_type) > 16:
            stret = getattr(self._objc, "objc_msgSend_stret")
            address = ctypes.cast(stret, ctypes.c_void_p).value
            prototype = ctypes.CFUNCTYPE(
                None,
                ctypes.POINTER(result_type),
                ctypes.c_void_p,
                ctypes.c_void_p,
            )
            result = result_type()
            prototype(address)(ctypes.byref(result), receiver_ptr, selector_ptr)
            return result
        address = ctypes.cast(self._objc.objc_msgSend, ctypes.c_void_p).value
        prototype = ctypes.CFUNCTYPE(result_type, ctypes.c_void_p, ctypes.c_void_p)
        return prototype(address)(receiver_ptr, selector_ptr)

    def _require_initialized(self) -> None:
        if not self._application:
            raise RuntimeError("Platform backend is not initialized.")

    def _require_window(self, handle: NativeWindowHandle) -> _WindowState:
        self._require_initialized()
        try:
            return self._windows[handle]
        except KeyError as exc:
            raise ValueError("Unknown native window handle.") from exc
