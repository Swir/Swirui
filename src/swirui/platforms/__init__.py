"""Operating-system backend contracts and event primitives."""

from .base import DisplayInfo, NativeWindowSpec, NullPlatformBackend, PlatformBackend
from .events import NativeWindowHandle, PlatformEvent, PlatformEventKind, PointerButton
from .factory import create_platform_backend

__all__ = [
    "DisplayInfo",
    "NativeWindowHandle",
    "NativeWindowSpec",
    "NullPlatformBackend",
    "PlatformBackend",
    "PlatformEvent",
    "PlatformEventKind",
    "PointerButton",
    "create_platform_backend",
]
