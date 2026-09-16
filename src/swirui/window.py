"""Window model for SwirUI."""

from __future__ import annotations

from .core import Component, EventEmitter


class Window(EventEmitter):
    """Framework-level window model independent of the native backend."""

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
        self.visible = False
        self.closed = False

    def set_root(self, component: Component | None) -> Window:
        old_root = self.root
        self.root = component
        self.emit("root_changed", old_root=old_root, root=component)
        return self

    def resize(self, width: int, height: int) -> None:
        width = max(width, self.min_width)
        height = max(height, self.min_height)
        if (width, height) == (self.width, self.height):
            return
        old_size = (self.width, self.height)
        self.width = width
        self.height = height
        self.emit("resized", old_size=old_size, size=(width, height))

    def show(self) -> None:
        if self.closed:
            raise RuntimeError("A closed window cannot be shown again.")
        if not self.visible:
            self.visible = True
            self.emit("shown")

    def hide(self) -> None:
        if self.visible:
            self.visible = False
            self.emit("hidden")

    def close(self) -> None:
        if self.closed:
            return
        self.visible = False
        self.closed = True
        self.emit("closed")

    def __repr__(self) -> str:
        return (
            f"Window(title={self.title!r}, width={self.width}, height={self.height}, "
            f"visible={self.visible}, closed={self.closed})"
        )
