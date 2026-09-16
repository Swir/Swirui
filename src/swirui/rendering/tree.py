"""Retained render-tree model for SwirUI."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

from .geometry import Rect


@dataclass(slots=True)
class RenderNode:
    """Backend-neutral visual node produced from the component tree."""

    key: str
    bounds: Rect
    visible: bool = True
    opacity: float = 1.0
    z_index: int = 0
    children: list[RenderNode] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not 0.0 <= self.opacity <= 1.0:
            raise ValueError("opacity must be between 0.0 and 1.0.")

    def add(self, *children: RenderNode) -> RenderNode:
        for child in children:
            if child is self or child.contains(self):
                raise ValueError("Adding this node would create a render-tree cycle.")
            if child not in self.children:
                self.children.append(child)
        return self

    def remove(self, child: RenderNode) -> None:
        try:
            self.children.remove(child)
        except ValueError as exc:
            raise ValueError("Render node is not a direct child.") from exc

    def walk(self, *, visible_only: bool = False) -> Iterator[RenderNode]:
        if not visible_only or self.visible:
            yield self
        if visible_only and not self.visible:
            return
        for child in sorted(self.children, key=lambda item: item.z_index):
            yield from child.walk(visible_only=visible_only)

    def contains(self, target: RenderNode) -> bool:
        return any(node is target for node in self.walk())

    def find(self, key: str) -> RenderNode | None:
        return next((node for node in self.walk() if node.key == key), None)


class RenderTree:
    """Container for the retained visual tree and its generation counter."""

    def __init__(self, root: RenderNode | None = None) -> None:
        self.root = root
        self.generation = 0

    def set_root(self, root: RenderNode | None) -> None:
        if root is self.root:
            return
        self.root = root
        self.generation += 1

    def invalidate(self) -> None:
        self.generation += 1

    def walk(self, *, visible_only: bool = False) -> Iterator[RenderNode]:
        if self.root is not None:
            yield from self.root.walk(visible_only=visible_only)
