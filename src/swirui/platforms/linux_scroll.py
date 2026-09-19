"""X11 wheel input layered on the direct native Linux backend."""

from __future__ import annotations

from .events import NativeWindowHandle, PlatformEvent, PlatformEventKind
from .linux import (
    _ButtonPress,
    _ControlMask,
    _Mod1Mask,
    _Mod4Mask,
    _ShiftMask,
    _XEvent,
)
from .linux import LinuxX11PlatformBackend as _BaseLinuxX11PlatformBackend

_WHEEL_STEP_DIP = 48.0
_SCROLL_BUTTON_DELTAS: dict[int, tuple[float, float]] = {
    4: (0.0, -_WHEEL_STEP_DIP),
    5: (0.0, _WHEEL_STEP_DIP),
    6: (-_WHEEL_STEP_DIP, 0.0),
    7: (_WHEEL_STEP_DIP, 0.0),
}


class LinuxX11PlatformBackend(_BaseLinuxX11PlatformBackend):
    """Direct X11 backend with normalized vertical/horizontal wheel events."""

    def _normalize_event(self, event: _XEvent) -> tuple[PlatformEvent, ...]:
        if event.type == _ButtonPress:
            delta = _SCROLL_BUTTON_DELTAS.get(int(event.xbutton.button))
            if delta is not None:
                handle = NativeWindowHandle(int(event.xbutton.window))
                if handle not in self._windows:
                    return ()
                state = int(event.xbutton.state)
                return (
                    PlatformEvent(
                        PlatformEventKind.POINTER_SCROLL,
                        handle,
                        x=float(event.xbutton.x),
                        y=float(event.xbutton.y),
                        delta_x=delta[0],
                        delta_y=delta[1],
                        shift=bool(state & _ShiftMask),
                        ctrl=bool(state & _ControlMask),
                        alt=bool(state & _Mod1Mask),
                        meta=bool(state & _Mod4Mask),
                    ),
                )
        return super()._normalize_event(event)
