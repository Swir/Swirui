"""Window model for SwirUI."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .core import Component, EventEmitter
from .platforms import NativeWindowHandle, PlatformBackend, PlatformEvent, PlatformEventKind

if TYPE_CHECKING:
    from .rendering.scene import Scene, SceneNode


_POINTER_EVENTS = {
    PlatformEventKind.POINTER_MOVE,
    PlatformEventKind.POINTER_DOWN,
    PlatformEventKind.POINTER_UP,
}


class Window(EventEmitter):
    """Framework-level window model independent of a specific native backend."""

    def __init__(
        self,
        *,
        title: str = "SwirUI",
        width: int = 960,
        height: int = 640,
        min_width: int = 320,
        min_height: int = 240,
    ) -> None:
        super().__init__()
        if width <= 0 or height <= 0:
            raise ValueError("Window dimensions must be positive.")
        if min_width <= 0 or min_height <= 0:
            raise ValueError("Minimum window dimensions must be positive.")

        self.title = title
        self.width = width
        self.height = height
        self.min_width = min_width
        self.min_height = min_height
        self.root: Component | None = None
        self.scene: Scene | None = None
        self.hovered_scene_node: SceneNode | None = None
        self.visible = False
        self.closed = False
        self.focused = False
        self.native_handle: NativeWindowHandle | None = None
        self._platform_backend: PlatformBackend | None = None

    def set_root(self, component: Component | None) -> Window:
        old_root = self.root
        self.root = component
        self.emit("root_changed", old_root=old_root, root=component)
        return self

    def set_scene(self, scene: Scene | None) -> Window:
        """Attach a prepared render scene and invalidate the next frame."""

        old_scene = self.scene
        self.scene = scene
        self.hovered_scene_node = None
        self.emit("scene_changed", old_scene=old_scene, scene=scene)
        return self

    def set_title(self, title: str) -> None:
        if title == self.title:
            return
        old_title = self.title
        self.title = title
        if self._platform_backend is not None and self.native_handle is not None:
            self._platform_backend.set_window_title(self.native_handle, title)
        self.emit("title_changed", old_title=old_title, title=title)

    def resize(self, width: int, height: int) -> None:
        width = max(width, self.min_width)
        height = max(height, self.min_height)
        if (width, height) == (self.width, self.height):
            return
        old_size = (self.width, self.height)
        self.width = width
        self.height = height
        if self._platform_backend is not None and self.native_handle is not None:
            self._platform_backend.resize_window(self.native_handle, width, height)
        self.emit("resized", old_size=old_size, size=(width, height))

    def show(self) -> None:
        if self.closed:
            raise RuntimeError("A closed window cannot be shown again.")
        if not self.visible:
            if self._platform_backend is not None and self.native_handle is not None:
                self._platform_backend.show_window(self.native_handle)
            self.visible = True
            self.emit("shown")

    def hide(self) -> None:
        if self.visible:
            if self._platform_backend is not None and self.native_handle is not None:
                self._platform_backend.hide_window(self.native_handle)
            self.visible = False
            self.hovered_scene_node = None
            self.emit("hidden")

    def close(self) -> None:
        if self.closed:
            return
        if self._platform_backend is not None and self.native_handle is not None:
            self._platform_backend.destroy_window(self.native_handle)
        self._mark_closed()
        self._unbind_native()

    def _bind_native(self, backend: PlatformBackend, handle: NativeWindowHandle) -> None:
        if self.native_handle is not None:
            raise RuntimeError("Window is already bound to a native handle.")
        self._platform_backend = backend
        self.native_handle = handle
        self.emit("native_bound", handle=handle)

    def _unbind_native(self) -> None:
        if self.native_handle is None:
            self._platform_backend = None
            return
        old_handle = self.native_handle
        self.native_handle = None
        self._platform_backend = None
        self.emit("native_unbound", handle=old_handle)

    def _apply_platform_event(self, event: PlatformEvent) -> None:
        if event.kind is PlatformEventKind.CLOSE:
            self._mark_closed()
            self._unbind_native()
            return

        if event.kind is PlatformEventKind.RESIZE:
            if event.width is None or event.height is None:
                return
            width = max(event.width, self.min_width)
            height = max(event.height, self.min_height)
            if (width, height) != (self.width, self.height):
                old_size = (self.width, self.height)
                self.width = width
                self.height = height
                self.emit("resized", old_size=old_size, size=(width, height))
            return

        if event.kind is PlatformEventKind.FOCUS:
            focused = bool(event.focused)
            if focused != self.focused:
                self.focused = focused
                self.emit("focus_changed", focused=focused)
            return

        if event.kind in _POINTER_EVENTS:
            self._apply_pointer_event(event)
            return

        self.emit(event.kind.value, event=event)

    def _apply_pointer_event(self, event: PlatformEvent) -> None:
        path: tuple[SceneNode, ...] = ()
        if self.scene is not None and event.x is not None and event.y is not None:
            path = self.scene.hit_path_xy(event.x, event.y)
        target = path[-1] if path else None

        if event.kind is PlatformEventKind.POINTER_MOVE and target is not self.hovered_scene_node:
            previous = self.hovered_scene_node
            self.hovered_scene_node = target
            if previous is not None:
                self.emit("pointer_leave", event=event, target=previous)
            if target is not None:
                self.emit("pointer_enter", event=event, target=target, path=path)

        self.emit(event.kind.value, event=event, target=target, path=path)

    def _mark_closed(self) -> None:
        if self.closed:
            return
        self.visible = False
        self.focused = False
        self.hovered_scene_node = None
        self.closed = True
        self.emit("closed")

    def __repr__(self) -> str:
        return (
            f"Window(title={self.title!r}, width={self.width}, height={self.height}, "
            f"visible={self.visible}, closed={self.closed})"
        )
