"""Platform backend contracts for native operating-system integration."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, replace
from typing import Protocol, runtime_checkable

from .events import NativeWindowHandle, PlatformEvent


@dataclass(frozen=True, slots=True)
class DisplayInfo:
    name: str
    width: int
    height: int
    scale: float = 1.0
    primary: bool = False


@dataclass(frozen=True, slots=True)
class NativeWindowSpec:
    """Backend-neutral description used to create a native window."""

    title: str
    width: int
    height: int
    min_width: int = 320
    min_height: int = 240

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("Native window dimensions must be positive.")
        if self.min_width <= 0 or self.min_height <= 0:
            raise ValueError("Native minimum dimensions must be positive.")


@runtime_checkable
class PlatformBackend(Protocol):
    """Contract implemented by Windows, Linux and macOS backends."""

    @property
    def name(self) -> str: ...

    def initialize(self) -> None: ...

    def displays(self) -> tuple[DisplayInfo, ...]: ...

    def create_window(self, spec: NativeWindowSpec) -> NativeWindowHandle: ...

    def show_window(self, handle: NativeWindowHandle) -> None: ...

    def hide_window(self, handle: NativeWindowHandle) -> None: ...

    def destroy_window(self, handle: NativeWindowHandle) -> None: ...

    def set_window_title(self, handle: NativeWindowHandle, title: str) -> None: ...

    def resize_window(self, handle: NativeWindowHandle, width: int, height: int) -> None: ...

    def poll_events(self) -> tuple[PlatformEvent, ...]: ...

    def shutdown(self) -> None: ...


class NullPlatformBackend:
    """Headless backend used by tests, CI and unsupported native targets."""

    name = "headless"

    def __init__(self) -> None:
        self.initialized = False
        self._next_handle = 1
        self._windows: dict[NativeWindowHandle, NativeWindowSpec] = {}
        self._visible: set[NativeWindowHandle] = set()
        self._events: deque[PlatformEvent] = deque()

    def initialize(self) -> None:
        self.initialized = True

    def displays(self) -> tuple[DisplayInfo, ...]:
        return ()

    def create_window(self, spec: NativeWindowSpec) -> NativeWindowHandle:
        self._require_initialized()
        handle = NativeWindowHandle(self._next_handle)
        self._next_handle += 1
        self._windows[handle] = spec
        return handle

    def show_window(self, handle: NativeWindowHandle) -> None:
        self._require_window(handle)
        self._visible.add(handle)

    def hide_window(self, handle: NativeWindowHandle) -> None:
        self._require_window(handle)
        self._visible.discard(handle)

    def destroy_window(self, handle: NativeWindowHandle) -> None:
        self._require_window(handle)
        self._visible.discard(handle)
        del self._windows[handle]

    def set_window_title(self, handle: NativeWindowHandle, title: str) -> None:
        spec = self._require_window(handle)
        self._windows[handle] = replace(spec, title=title)

    def resize_window(self, handle: NativeWindowHandle, width: int, height: int) -> None:
        spec = self._require_window(handle)
        self._windows[handle] = replace(spec, width=width, height=height)

    def poll_events(self) -> tuple[PlatformEvent, ...]:
        events = tuple(self._events)
        self._events.clear()
        return events

    def post_event(self, event: PlatformEvent) -> None:
        """Inject an event into the headless queue for deterministic tests."""

        self._require_window(event.window)
        self._events.append(event)

    def shutdown(self) -> None:
        self._visible.clear()
        self._windows.clear()
        self._events.clear()
        self.initialized = False

    def _require_initialized(self) -> None:
        if not self.initialized:
            raise RuntimeError("Platform backend is not initialized.")

    def _require_window(self, handle: NativeWindowHandle) -> NativeWindowSpec:
        try:
            return self._windows[handle]
        except KeyError as exc:
            raise ValueError("Unknown native window handle.") from exc
