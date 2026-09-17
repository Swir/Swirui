"""Component tree primitives for SwirUI."""

from __future__ import annotations

from collections.abc import Iterator
from uuid import uuid4

from .accessibility import AccessibilityRole
from .events import EventEmitter


class Component(EventEmitter):
    """Base object for every visual and logical UI component."""

    def __init__(
        self,
        name: str | None = None,
        *,
        key: str | None = None,
        focusable: bool = False,
        accessibility_role: AccessibilityRole = AccessibilityRole.GENERIC,
        accessible_name: str | None = None,
        accessible_description: str | None = None,
        accessible_checked: bool | None = None,
    ) -> None:
        super().__init__()
        self.name = name or self.__class__.__name__
        self.key = key or uuid4().hex
        self.parent: Component | None = None
        self.children: list[Component] = []
        self._enabled = True
        self._visible = True
        self._focusable = bool(focusable)
        self.accessibility_role = accessibility_role
        self.accessible_name = accessible_name
        self.accessible_description = accessible_description
        self.accessible_checked = accessible_checked

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        normalized = bool(value)
        if normalized == self._enabled:
            return
        self._enabled = normalized
        self.invalidate(reason="enabled")

    @property
    def visible(self) -> bool:
        return self._visible

    @visible.setter
    def visible(self, value: bool) -> None:
        normalized = bool(value)
        if normalized == self._visible:
            return
        self._visible = normalized
        self.invalidate(reason="visible")

    @property
    def focusable(self) -> bool:
        return self._focusable

    @focusable.setter
    def focusable(self, value: bool) -> None:
        normalized = bool(value)
        if normalized == self._focusable:
            return
        self._focusable = normalized
        self.invalidate(reason="focusable")

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
            self.invalidate(reason="child_added", source=child)
        return self

    def remove(self, child: Component) -> Component:
        try:
            self.children.remove(child)
        except ValueError as exc:
            raise ValueError("Component is not a child of this parent.") from exc
        child.parent = None
        self.emit("child_removed", child=child)
        self.invalidate(reason="child_removed", source=child)
        return child

    def clear(self) -> None:
        for child in tuple(self.children):
            self.remove(child)

    def invalidate(self, *, reason: str = "changed", source: Component | None = None) -> None:
        """Mark this retained component subtree as changed.

        Invalidation bubbles through component parents while preserving the
        component that originally changed. Rendering runtimes can therefore
        subscribe once at the mounted root instead of attaching listeners to
        every widget. The event is synchronous and deliberately carries no
        renderer dependency, keeping the core tree backend-neutral.
        """

        origin = self if source is None else source
        self.emit("invalidated", component=origin, reason=reason)
        if self.parent is not None:
            self.parent.invalidate(reason=reason, source=origin)

    def set_enabled(self, enabled: bool) -> Component:
        self.enabled = enabled
        return self

    def set_visible(self, visible: bool) -> Component:
        self.visible = visible
        return self

    def set_focusable(self, focusable: bool) -> Component:
        self.focusable = focusable
        return self

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
