"""Renderer contracts used by SwirUI."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from swirui.core import Component
from swirui.window import Window


@runtime_checkable
class Renderer(Protocol):
    """Backend contract for turning a component tree into frames."""

    @property
    def name(self) -> str: ...

    def initialize(self) -> None: ...

    def render(self, window: Window, root: Component | None) -> None: ...

    def shutdown(self) -> None: ...


class NullRenderer:
    """No-op renderer used while the native GPU backend is being built."""

    name = "null"

    def __init__(self) -> None:
        self.initialized = False
        self.frames_rendered = 0

    def initialize(self) -> None:
        self.initialized = True

    def render(self, window: Window, root: Component | None) -> None:
        if not self.initialized:
            raise RuntimeError("Renderer must be initialized before rendering.")
        del window, root
        self.frames_rendered += 1

    def shutdown(self) -> None:
        self.initialized = False
