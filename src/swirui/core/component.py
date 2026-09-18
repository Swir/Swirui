"""Component tree primitives for SwirUI."""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING
from uuid import uuid4

from .accessibility import AccessibilityRole
from .events import EventEmitter

if TYPE_CHECKING:
    from swirui.window import Window


class Component(EventEmitter):
    """Base object for every visual and logical UI component.

    Components participate in an explicit retained lifecycle while mounted by a
    :class:`~swirui.widgets.runtime.WidgetRuntime`. Lifecycle hooks are safe to
    override in subclasses; event emission remains available for composition.
    """

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
        accessible_value: float | None = None,
        accessible_min_value: float | None = None,
        accessible_max_value: float | None = None,
        accessible_value_text: str | None = None,
    ) -> None:
        super().__init__()
        self.name = name or self.__class__.__name__
        self.key = key or uuid4().hex
        self.parent: Component | None = None
        self.children: list[Component] = []
        self._enabled = True
        self._visible = True
        self._focusable = bool(focusable)
        self._mounted_window: Window | None = None
        self.accessibility_role = accessibility_role
        self.accessible_name = accessible_name
        self.accessible_description = accessible_description
        self.accessible_checked = accessible_checked
        self.accessible_value = accessible_value
        self.accessible_min_value = accessible_min_value
        self.accessible_max_value = accessible_max_value
        self.accessible_value_text = accessible_value_text

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

    @property
    def mounted(self) -> bool:
        """Whether this component currently belongs to a mounted retained tree."""

        return self._mounted_window is not None

    @property
    def mounted_window(self) -> Window | None:
        """Return the Window hosting this component, or ``None`` when detached."""

        return self._mounted_window

    def on_mount(self, window: Window) -> None:
        """Lifecycle hook called once after the component becomes mounted."""

        del window

    def on_update(self, *, reason: str, source: Component) -> None:
        """Lifecycle hook called for invalidation affecting this mounted component.

        ``source`` identifies the deepest component that initiated the retained
        invalidation while ``reason`` preserves the framework mutation category.
        Ancestors receive the same source as invalidation bubbles through the tree.
        """

        del reason, source

    def on_unmount(self, window: Window) -> None:
        """Lifecycle hook called after descendants detach from the hosting window."""

        del window

    def add(self, *children: Component) -> Component:
        for child in children:
            if child is self:
                raise ValueError("A component cannot be its own child.")
            if child._contains(self):
                raise ValueError("Adding this child would create a component cycle.")
            if child.parent is self:
                continue
            if (
                child.parent is None
                and child.mounted_window is not None
                and child.mounted_window is not self._mounted_window
            ):
                raise ValueError("A mounted root cannot be attached to a different component tree.")

            old_parent = child.parent
            if old_parent is not None:
                old_parent.remove(child)
            child.parent = self
            self.children.append(child)
            try:
                if self._mounted_window is not None:
                    child._mount(self._mounted_window)
            except BaseException:
                self.children.remove(child)
                child.parent = None
                raise
            child.emit("parent_changed", old_parent=old_parent, new_parent=self)
            self.emit("child_added", child=child)
            self.invalidate(reason="child_added", source=child)
        return self

    def remove(self, child: Component) -> Component:
        if child not in self.children:
            raise ValueError("Component is not a child of this parent.")
        if self._mounted_window is not None:
            child._unmount()
        self.children.remove(child)
        child.parent = None
        child.emit("parent_changed", old_parent=self, new_parent=None)
        self.emit("child_removed", child=child)
        self.invalidate(reason="child_removed", source=child)
        return child

    def clear(self) -> None:
        for child in tuple(self.children):
            self.remove(child)

    def invalidate(self, *, reason: str = "changed", source: Component | None = None) -> None:
        """Mark this retained component subtree as changed."""

        origin = self if source is None else source
        if self._mounted_window is not None:
            self.on_update(reason=reason, source=origin)
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

    def _mount(self, window: Window) -> None:
        """Mount this subtree into ``window`` with deterministic parent-first hooks."""

        if self._mounted_window is window:
            return
        if self._mounted_window is not None:
            raise ValueError("Component is already mounted in another window.")

        self._mounted_window = window
        mounted_children: list[Component] = []
        try:
            self.on_mount(window)
            self.emit("mounted", window=window)
            for child in self.children:
                child._mount(window)
                mounted_children.append(child)
        except BaseException:
            for child in reversed(mounted_children):
                child._unmount()
            self._mounted_window = None
            raise

    def _unmount(self) -> None:
        """Unmount this subtree with deterministic child-first hooks."""

        window = self._mounted_window
        if window is None:
            return
        for child in reversed(self.children):
            child._unmount()
        self._mounted_window = None
        self.on_unmount(window)
        self.emit("unmounted", window=window)

    def __iter__(self) -> Iterator[Component]:
        return iter(self.children)

    def __len__(self) -> int:
        return len(self.children)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r}, key={self.key!r})"
