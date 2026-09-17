"""Retained resizable split container for the SwirUI core-widget layer."""

from __future__ import annotations

import math

from swirui.core import AccessibilityRole, Component, Event
from swirui.platforms import PlatformEvent, PlatformEventKind, PointerButton
from swirui.rendering.geometry import Color, Rect
from swirui.rendering.scene import SceneNode, SceneNodeKind

from .base import Widget

_VK_END = 0x23
_VK_HOME = 0x24
_VK_LEFT = 0x25
_VK_UP = 0x26
_VK_RIGHT = 0x27
_VK_DOWN = 0x28

_DEFAULT_DIVIDER = Color.from_hex("#184A62")
_DEFAULT_DIVIDER_HOVER = Color.from_hex("#23C9FF")
_DEFAULT_DIVIDER_ACTIVE = Color.from_hex("#62E5FF")
_DEFAULT_DIVIDER_DISABLED = Color.from_hex("#344550")


class SplitView(Widget):
    """Two-pane retained container with a focusable, draggable divider.

    Pane children author their geometry in pane-local logical DIPs. Scene
    compilation translates each retained subtree into its pane and clips it
    without mutating public component geometry. ``orientation="horizontal"``
    creates left/right panes; ``orientation="vertical"`` creates top/bottom
    panes.
    """

    def __init__(
        self,
        *,
        bounds: Rect,
        first: Component | None = None,
        second: Component | None = None,
        key: str | None = None,
        orientation: str = "horizontal",
        split_ratio: float = 0.5,
        min_ratio: float = 0.15,
        max_ratio: float = 0.85,
        divider_size: float = 8.0,
        keyboard_step: float = 0.05,
        divider_color: Color | None = None,
        divider_hover_color: Color | None = None,
        divider_active_color: Color | None = None,
        divider_disabled_color: Color | None = None,
        opacity: float = 1.0,
        z_index: int = 0,
        accessible_name: str | None = None,
        accessible_description: str | None = None,
    ) -> None:
        self._orientation = self._validate_orientation(orientation)
        self._min_ratio = self._validate_ratio(min_ratio, "min_ratio")
        self._max_ratio = self._validate_ratio(max_ratio, "max_ratio")
        if self._min_ratio >= self._max_ratio:
            raise ValueError("min_ratio must be smaller than max_ratio.")
        self._split_ratio = self._clamp_ratio(
            self._validate_ratio(split_ratio, "split_ratio")
        )
        self._divider_size = self._validate_positive(divider_size, "divider_size")
        self._keyboard_step = self._validate_positive(keyboard_step, "keyboard_step")
        self._divider_color = divider_color or _DEFAULT_DIVIDER
        self._divider_hover_color = divider_hover_color or _DEFAULT_DIVIDER_HOVER
        self._divider_active_color = divider_active_color or _DEFAULT_DIVIDER_ACTIVE
        self._divider_disabled_color = divider_disabled_color or _DEFAULT_DIVIDER_DISABLED
        self._first: Component | None = None
        self._second: Component | None = None
        self._hovered = False
        self._dragging = False
        self._focused = False
        self._drag_anchor = 0.0
        super().__init__(
            bounds=bounds,
            key=key,
            opacity=opacity,
            z_index=z_index,
            focusable=True,
            accessibility_role=AccessibilityRole.SLIDER,
            accessible_name=accessible_name or "Split view divider",
            accessible_description=accessible_description,
        )
        self._sync_accessibility()
        self.on("pointer_enter", self._on_pointer_enter)
        self.on("pointer_leave", self._on_pointer_leave)
        self.on("pointer_down", self._on_pointer_down)
        self.on("pointer_move", self._on_pointer_move)
        self.on("pointer_up", self._on_pointer_up)
        self.on("key_down", self._on_key_down)
        self.on("focus_gained", self._on_focus_gained)
        self.on("focus_lost", self._on_focus_lost)
        self.on("invalidated", self._on_invalidated)
        if first is not None or second is not None:
            if first is None or second is None:
                raise ValueError("SplitView requires both first and second panes.")
            self.set_panes(first, second)

    @property
    def orientation(self) -> str:
        return self._orientation

    @orientation.setter
    def orientation(self, value: str) -> None:
        normalized = self._validate_orientation(value)
        if normalized == self._orientation:
            return
        self._orientation = normalized
        self._dragging = False
        self.invalidate(reason="orientation")

    @property
    def split_ratio(self) -> float:
        return self._split_ratio

    @split_ratio.setter
    def split_ratio(self, value: float) -> None:
        self.set_split_ratio(value)

    @property
    def min_ratio(self) -> float:
        return self._min_ratio

    @property
    def max_ratio(self) -> float:
        return self._max_ratio

    @property
    def divider_size(self) -> float:
        return self._divider_size

    @divider_size.setter
    def divider_size(self, value: float) -> None:
        normalized = self._validate_positive(value, "divider_size")
        if normalized == self._divider_size:
            return
        self._divider_size = normalized
        self.invalidate(reason="divider_size")

    @property
    def keyboard_step(self) -> float:
        return self._keyboard_step

    @keyboard_step.setter
    def keyboard_step(self, value: float) -> None:
        normalized = self._validate_positive(value, "keyboard_step")
        if normalized == self._keyboard_step:
            return
        self._keyboard_step = normalized

    @property
    def first(self) -> Component | None:
        return self._first

    @property
    def second(self) -> Component | None:
        return self._second

    @property
    def hovered(self) -> bool:
        return self._hovered

    @property
    def dragging(self) -> bool:
        return self._dragging

    @property
    def focused(self) -> bool:
        return self._focused

    @property
    def first_pane_bounds(self) -> Rect:
        first, _divider, _second = self._pane_bounds()
        return first

    @property
    def second_pane_bounds(self) -> Rect:
        _first, _divider, second = self._pane_bounds()
        return second

    @property
    def divider_bounds(self) -> Rect:
        _first, divider, _second = self._pane_bounds()
        return divider

    def set_panes(self, first: Component, second: Component) -> SplitView:
        """Replace the two managed pane subtrees."""

        if first is second:
            raise ValueError("SplitView panes must be distinct components.")
        if first is self or second is self:
            raise ValueError("A SplitView cannot use itself as a pane.")
        if first is self._first and second is self._second:
            return self

        previous = tuple(
            child for child in (self._first, self._second) if child is not None
        )
        for child in previous:
            if child.parent is self:
                super().remove(child)

        self._first = first
        self._second = second
        super().add(first, second)
        self.invalidate(reason="panes")
        return self

    def add(self, *children: Component) -> SplitView:
        """Set both panes in one operation."""

        if len(children) != 2:
            raise ValueError("SplitView.add() requires exactly two pane components.")
        return self.set_panes(children[0], children[1])

    def remove(self, child: Component) -> SplitView:
        if child is not self._first and child is not self._second:
            raise ValueError("Component is not a managed SplitView pane.")
        super().remove(child)
        if child is self._first:
            self._first = None
        if child is self._second:
            self._second = None
        self.invalidate(reason="panes")
        return self

    def clear(self) -> None:
        for child in tuple(
            item for item in (self._first, self._second) if item is not None
        ):
            self.remove(child)

    def set_split_ratio(self, value: float, *, reason: str = "programmatic") -> bool:
        """Clamp and apply the first-pane ratio.

        Returns ``True`` only when the effective split changed.
        """

        normalized = self._clamp_ratio(self._validate_ratio(value, "split_ratio"))
        if normalized == self._split_ratio:
            return False
        old_ratio = self._split_ratio
        self._split_ratio = normalized
        self._sync_accessibility()
        self.invalidate(reason="split_ratio")
        self.emit(
            "split_changed",
            old_ratio=old_ratio,
            ratio=normalized,
            reason=reason,
        )
        return True

    def build_scene_node(self) -> SceneNode:
        root = SceneNode(
            key=self.key,
            kind=SceneNodeKind.GROUP,
            bounds=self.bounds,
            opacity=self.opacity,
            z_index=self.z_index,
            clip_to_bounds=True,
            hit_testable=False,
        )
        root.add(
            SceneNode(
                key=self.key,
                kind=SceneNodeKind.RECTANGLE,
                bounds=self.divider_bounds,
                fill=self._current_divider_color(),
                z_index=1000,
                hit_testable=self.enabled,
            )
        )
        return root

    def prepare_scene_children(
        self,
        children: tuple[SceneNode, ...],
    ) -> tuple[SceneNode, ...]:
        """Translate local pane subtrees and clip each one to its current pane."""

        node_by_key = {node.key: node for node in children}
        prepared: list[SceneNode] = []
        pane_specs = (
            ("first", self._first, self.first_pane_bounds),
            ("second", self._second, self.second_pane_bounds),
        )
        for label, component, pane_bounds in pane_specs:
            if component is None:
                continue
            child = node_by_key.get(component.key)
            if child is None:
                continue
            self._translate_subtree(child, dx=pane_bounds.x, dy=pane_bounds.y)
            wrapper = SceneNode(
                key=f"{self.key}:pane:{label}",
                kind=SceneNodeKind.GROUP,
                bounds=pane_bounds,
                z_index=0,
                clip_to_bounds=True,
                hit_testable=False,
            )
            wrapper.add(child)
            prepared.append(wrapper)
        return tuple(prepared)

    def _pane_bounds(self) -> tuple[Rect, Rect, Rect]:
        if self._orientation == "horizontal":
            available = max(0.0, self.bounds.width - self._divider_size)
            first_extent = available * self._split_ratio
            first = Rect(
                self.bounds.x,
                self.bounds.y,
                first_extent,
                self.bounds.height,
            )
            divider = Rect(
                self.bounds.x + first_extent,
                self.bounds.y,
                self._divider_size,
                self.bounds.height,
            )
            second = Rect(
                divider.right,
                self.bounds.y,
                max(0.0, self.bounds.right - divider.right),
                self.bounds.height,
            )
            return first, divider, second

        available = max(0.0, self.bounds.height - self._divider_size)
        first_extent = available * self._split_ratio
        first = Rect(
            self.bounds.x,
            self.bounds.y,
            self.bounds.width,
            first_extent,
        )
        divider = Rect(
            self.bounds.x,
            self.bounds.y + first_extent,
            self.bounds.width,
            self._divider_size,
        )
        second = Rect(
            self.bounds.x,
            divider.bottom,
            self.bounds.width,
            max(0.0, self.bounds.bottom - divider.bottom),
        )
        return first, divider, second

    def _on_pointer_enter(self, event: Event) -> None:
        if self.enabled and self._event_targets_divider(event):
            self._set_interaction_state(hovered=True, reason="pointer_enter")

    def _on_pointer_leave(self, _event: Event) -> None:
        if not self._dragging:
            self._set_interaction_state(hovered=False, reason="pointer_leave")

    def _on_pointer_down(self, event: Event) -> None:
        platform_event = self._platform_event(event, PlatformEventKind.POINTER_DOWN)
        if (
            not self.enabled
            or platform_event is None
            or platform_event.button is not PointerButton.LEFT
            or not self._event_targets_divider(event)
        ):
            return

        coordinate = self._axis_coordinate(platform_event)
        if coordinate is None:
            return
        divider = self.divider_bounds
        divider_center = (
            divider.x + (divider.width * 0.5)
            if self._orientation == "horizontal"
            else divider.y + (divider.height * 0.5)
        )
        self._drag_anchor = coordinate - divider_center
        self._set_interaction_state(
            hovered=True,
            dragging=True,
            reason="pointer_down",
        )
        event.prevent_default()

    def _on_pointer_move(self, event: Event) -> None:
        if not self.enabled or not self._dragging:
            return
        platform_event = self._platform_event(event, PlatformEventKind.POINTER_MOVE)
        if platform_event is None:
            return
        coordinate = self._axis_coordinate(platform_event)
        if coordinate is None:
            return
        ratio = self._ratio_for_coordinate(coordinate - self._drag_anchor)
        if self.set_split_ratio(ratio, reason="pointer"):
            event.prevent_default()

    def _on_pointer_up(self, event: Event) -> None:
        platform_event = self._platform_event(event, PlatformEventKind.POINTER_UP)
        if (
            platform_event is None
            or platform_event.button is not PointerButton.LEFT
            or not self._dragging
        ):
            return
        self._set_interaction_state(dragging=False, reason="pointer_up")
        event.prevent_default()

    def _on_key_down(self, event: Event) -> None:
        if not self.enabled:
            return
        platform_event = self._platform_event(event, PlatformEventKind.KEY_DOWN)
        if platform_event is None:
            return
        if platform_event.ctrl or platform_event.alt or platform_event.meta:
            return

        key_code = platform_event.key_code
        delta = 0.0
        if self._orientation == "horizontal":
            if key_code == _VK_LEFT:
                delta = -self._keyboard_step
            elif key_code == _VK_RIGHT:
                delta = self._keyboard_step
        else:
            if key_code == _VK_UP:
                delta = -self._keyboard_step
            elif key_code == _VK_DOWN:
                delta = self._keyboard_step

        changed = False
        if delta:
            changed = self.set_split_ratio(
                self._split_ratio + delta,
                reason="keyboard",
            )
        elif key_code == _VK_HOME:
            changed = self.set_split_ratio(self._min_ratio, reason="keyboard")
        elif key_code == _VK_END:
            changed = self.set_split_ratio(self._max_ratio, reason="keyboard")

        if changed:
            event.prevent_default()

    def _on_focus_gained(self, _event: Event) -> None:
        self._set_interaction_state(focused=True, reason="focus_gained")

    def _on_focus_lost(self, _event: Event) -> None:
        self._set_interaction_state(
            hovered=False,
            dragging=False,
            focused=False,
            reason="focus_lost",
        )

    def _on_invalidated(self, event: Event) -> None:
        if event.data.get("reason") == "enabled" and not self.enabled:
            self._hovered = False
            self._dragging = False

    def _set_interaction_state(
        self,
        *,
        hovered: bool | None = None,
        dragging: bool | None = None,
        focused: bool | None = None,
        reason: str,
    ) -> None:
        changed = False
        if hovered is not None and hovered != self._hovered:
            self._hovered = hovered
            changed = True
        if dragging is not None and dragging != self._dragging:
            self._dragging = dragging
            changed = True
        if focused is not None and focused != self._focused:
            self._focused = focused
            changed = True
        if changed:
            self.invalidate(reason=reason)

    def _ratio_for_coordinate(self, coordinate: float) -> float:
        if self._orientation == "horizontal":
            available = self.bounds.width - self._divider_size
            if available <= 0.0:
                return self._split_ratio
            first_extent = coordinate - self.bounds.x - (self._divider_size * 0.5)
        else:
            available = self.bounds.height - self._divider_size
            if available <= 0.0:
                return self._split_ratio
            first_extent = coordinate - self.bounds.y - (self._divider_size * 0.5)
        return self._clamp_ratio(first_extent / available)

    def _current_divider_color(self) -> Color:
        if not self.enabled:
            return self._divider_disabled_color
        if self._dragging:
            return self._divider_active_color
        if self._hovered or self._focused:
            return self._divider_hover_color
        return self._divider_color

    def _sync_accessibility(self) -> None:
        self.accessible_value = self._split_ratio * 100.0
        self.accessible_min_value = self._min_ratio * 100.0
        self.accessible_max_value = self._max_ratio * 100.0
        self.accessible_value_text = f"{self._split_ratio * 100.0:.0f}% first pane"

    def _event_targets_divider(self, event: Event) -> bool:
        scene_target = event.data.get("scene_target")
        return isinstance(scene_target, SceneNode) and scene_target.key == self.key

    def _axis_coordinate(self, event: PlatformEvent) -> float | None:
        return event.x if self._orientation == "horizontal" else event.y

    def _clamp_ratio(self, value: float) -> float:
        return min(max(value, self._min_ratio), self._max_ratio)

    @classmethod
    def _validate_ratio(cls, value: float, name: str) -> float:
        normalized = cls._validate_finite(value, name)
        if not 0.0 <= normalized <= 1.0:
            raise ValueError(f"{name} must be between 0.0 and 1.0.")
        return normalized

    @classmethod
    def _validate_positive(cls, value: float, name: str) -> float:
        normalized = cls._validate_finite(value, name)
        if normalized <= 0.0:
            raise ValueError(f"{name} must be greater than zero.")
        return normalized

    @staticmethod
    def _validate_finite(value: float, name: str) -> float:
        normalized = float(value)
        if not math.isfinite(normalized):
            raise ValueError(f"{name} must be finite.")
        return normalized

    @staticmethod
    def _validate_orientation(value: str) -> str:
        normalized = str(value).strip().lower()
        if normalized not in {"horizontal", "vertical"}:
            raise ValueError("orientation must be 'horizontal' or 'vertical'.")
        return normalized

    @classmethod
    def _translate_subtree(cls, node: SceneNode, *, dx: float, dy: float) -> None:
        bounds = node.bounds
        node.bounds = Rect(bounds.x + dx, bounds.y + dy, bounds.width, bounds.height)
        for child in node.children:
            cls._translate_subtree(child, dx=dx, dy=dy)

    @staticmethod
    def _platform_event(event: Event, kind: PlatformEventKind) -> PlatformEvent | None:
        platform_event = event.data.get("event")
        if isinstance(platform_event, PlatformEvent) and platform_event.kind is kind:
            return platform_event
        return None
