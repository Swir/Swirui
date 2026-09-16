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
    """Normalized native event consumed by :class:`swirui.App`."""

    kind: PlatformEventKind
    window: NativeWindowHandle
    width: int | None = None
    height: int | None = None
    scale: float | None = None
    x: float | None = None
    y: float | None = None
    button: PointerButton | None = None
    key_code: int | None = None
    text: str | None = None
    focused: bool | None = None
