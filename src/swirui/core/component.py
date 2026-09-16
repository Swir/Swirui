"""Component tree primitives for SwirUI."""

from __future__ import annotations

from collections.abc import Iterator
from uuid import uuid4

from .events import EventEmitter


class Component(EventEmitter):
    """Base object for every visual and logical UI component."""

    def __init__(
        self,
        name: str | None = None,
        *,
        key: str | None = None,
        focusable: bool = False,
    ) -> None:
        super().__init__()
        self.name = name or self.__class__.__name__
        self.key = key or uuid4().hex
        self.parent: Component | None = None
        self.children: list[Component] = []
        self.enabled = True
        self.visible = True
        self.focusable = focusable

    def add(self, *children: Component) -> Component:
        for child in children:
            if child is self:
                raise ValueError("A component cannot be its own child.")
            if child._contains(self):
                raise ValueError("Adding this child would create a component cycle.")
            if child.parent is self:
                continue
            if child.parent is not None:
                child.parent.remove(child)
            child.parent = self
            self.children.append(child)
            self.emit("child_added", child=child)
        return self

    def remove(self, child: Component) -> Component:
        try:
            self.children.remove(child)
        except ValueError as exc:
            raise ValueError("Component is not a child of this parent.") from exc
        child.parent = None
        self.emit("child_removed", child=child)
        return child

    def clear(self) -> None:
        for child in tuple(self.children):
            self.remove(child)

    def walk(self, *, include_self: bool = True) -> Iterator[Component]:
        if include_self:
            yield self
        for child in self.children:
            yield child
            yield from child.walk(include_self=False)

    def find(self, key: str) -> Component | None:
        return next((component for component in self.walk() if component.key == key), None)

    def _contains(self, target: Component) -> bool:
        return any(component is target for component in self.walk())

    def __iter__(self) -> Iterator[Component]:
        return iter(self.children)

    def __len__(self) -> int:
        return len(self.children)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r}, key={self.key!r})"
