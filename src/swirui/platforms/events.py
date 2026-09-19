"""Typed platform events shared by native backends and the SwirUI runtime."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class PlatformEventKind(StrEnum):
    """Operating-system events normalized for the framework runtime."""

    CLOSE = "close"
    RESIZE = "resize"
    DPI_CHANGED = "dpi_changed"
    DISPLAY_CHANGED = "display_changed"
    FOCUS = "focus"
    POINTER_MOVE = "pointer_move"
    POINTER_DOWN = "pointer_down"
    POINTER_UP = "pointer_up"
    POINTER_SCROLL = "pointer_scroll"
    KEY_DOWN = "key_down"
    KEY_UP = "key_up"
    TEXT_INPUT = "text_input"


class PointerButton(StrEnum):
    LEFT = "left"
    RIGHT = "right"
    MIDDLE = "middle"


@dataclass(frozen=True, slots=True)
class NativeWindowHandle:
    """Opaque native window identifier owned by a platform backend."""

    value: int

    def __post_init__(self) -> None:
        if self.value <= 0:
            raise ValueError("Native window handles must be positive integers.")


@dataclass(frozen=True, slots=True)
class PlatformEvent:
    """Normalized native event consumed by :class:`swirui.App`.

    Pointer coordinates are physical pixels at the platform boundary. Scroll
    deltas are logical-DIP viewport offsets: positive x scrolls content right
    and positive y scrolls content down. Keeping deltas in DIPs preserves
    high-resolution wheel/trackpad motion without coupling it to monitor scale.

    Keyboard modifier flags are captured at native dispatch time so framework
    default actions such as Shift+Tab traversal remain backend-neutral and do
    not need to query operating-system state later in the event pipeline.
    """

    kind: PlatformEventKind
    window: NativeWindowHandle
    width: int | None = None
    height: int | None = None
    scale: float | None = None
    x: float | None = None
    y: float | None = None
    delta_x: float = 0.0
    delta_y: float = 0.0
    button: PointerButton | None = None
    key_code: int | None = None
    text: str | None = None
    focused: bool | None = None
    shift: bool = False
    ctrl: bool = False
    alt: bool = False
    meta: bool = False
