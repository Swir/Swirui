"""Cocoa scroll-wheel and trackpad input for the direct native macOS backend."""

from __future__ import annotations

import ctypes
import math

from .events import NativeWindowHandle, PlatformEvent, PlatformEventKind
from .macos import MacOSCocoaPlatformBackend as _BaseMacOSCocoaPlatformBackend

_NSEventTypeScrollWheel = 22
_NON_PRECISE_SCROLL_STEP_DIP = 48.0


def _normalize_scroll_deltas(
    delta_x: float,
    delta_y: float,
    *,
    precise: bool,
) -> tuple[float, float]:
    """Convert AppKit wheel deltas to SwirUI logical-DIP content offsets.

    AppKit reports precise trackpad deltas in logical points, while traditional
    wheel events are line-like units. SwirUI keeps precise motion untouched and
    maps one non-precise wheel unit to the same 48-DIP step used by Win32/X11.
    Cocoa's positive vertical direction is wheel-up, opposite SwirUI's positive
    content-down convention, so only the vertical axis is inverted.
    """

    raw_x = float(delta_x)
    raw_y = float(delta_y)
    if not math.isfinite(raw_x) or not math.isfinite(raw_y):
        return (0.0, 0.0)
    scale = 1.0 if precise else _NON_PRECISE_SCROLL_STEP_DIP
    return (raw_x * scale, -raw_y * scale)


class MacOSCocoaPlatformBackend(_BaseMacOSCocoaPlatformBackend):
    """Direct Cocoa backend with precise wheel/trackpad normalization."""

    def _normalize_event(self, event: int) -> tuple[PlatformEvent, ...]:
        event_type = int(self._send(event, "type", ctypes.c_ulong) or 0)
        if event_type != _NSEventTypeScrollWheel:
            return super()._normalize_event(event)

        window = int(self._send(event, "window") or 0)
        if not window:
            return ()
        handle = NativeWindowHandle(window)
        if handle not in self._windows:
            return ()

        precise = bool(
            self._send(event, "hasPreciseScrollingDeltas", ctypes.c_bool)
        )
        raw_x = float(
            self._send(event, "scrollingDeltaX", ctypes.c_double) or 0.0
        )
        raw_y = float(
            self._send(event, "scrollingDeltaY", ctypes.c_double) or 0.0
        )
        delta_x, delta_y = _normalize_scroll_deltas(
            raw_x,
            raw_y,
            precise=precise,
        )
        if delta_x == 0.0 and delta_y == 0.0:
            return ()

        x, y = self._event_pointer_pixels(event, window)
        shift, ctrl, alt, meta = self._modifiers(event)
        return (
            PlatformEvent(
                PlatformEventKind.POINTER_SCROLL,
                handle,
                x=x,
                y=y,
                delta_x=delta_x,
                delta_y=delta_y,
                shift=shift,
                ctrl=ctrl,
                alt=alt,
                meta=meta,
            ),
        )
