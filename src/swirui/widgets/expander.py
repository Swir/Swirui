"""Retained disclosure widgets for expandable content groups."""

from __future__ import annotations

import math
from collections.abc import Callable

from swirui.core import AccessibilityRole, Component, Event
from swirui.platforms import PlatformEvent, PlatformEventKind, PointerButton
from swirui.rendering.geometry import Color, CornerRadius, Rect
from swirui.rendering.scene import SceneNode, SceneNodeKind

from .base import Widget

_VK_RETURN = 0x0D
_VK_SPACE = 0x20
_VK_LEFT = 0x25
_VK_UP = 0x26
_VK_RIGHT = 0x27
_VK_DOWN = 0x28

_DEFAULT_BACKGROUND = Color.from_hex("#0B1623")
_DEFAULT_HOVER_BACKGROUND = Color.from_hex("#10283A")
_DEFAULT_PRESSED_BACKGROUND = Color.from_hex("#0A6FA8")
_DEFAULT_FOCUSED_BACKGROUND = Color.from_hex("#12334A")
_DEFAULT_DISABLED_BACKGROUND = Color.from_hex("#26333D")
_DEFAULT_FOREGROUND = Color.from_hex("#ECF9FF")
_DEFAULT_ACCENT = Color.from_hex("#23C9FF")


class Expander(Widget):
    """Focusable disclosure header that owns one optional content component.

    ``bounds`` describes the retained header geometry. The content component keeps
    its own logical-DIP geometry because layout is intentionally handled outside
    the 0.4 widget layer. Collapsing the expander removes the content subtree from
    visual compilation, hit testing, focus traversal and accessibility snapshots
    by toggling the owned content component's visibility.
    """

    def __init__(
        self,
        title: str,
        *,
        bounds: Rect,
        content: Component | None = None,
        expanded: bool = False,
        key: str | None = None,
        background: Color | None = None,
        hover_background: Color | None = None,
        pressed_background: Color | None = None,
        focused_background: Color | None = None,
        disabled_background: Color | None = None,
        foreground: Color | None = None,
        accent: Color | None = None,
        corner_radius: float = 8.0,
        font_size: float = 15.0,
        font_family: str = "Segoe UI",
        padding: float = 12.0,
        opacity: float = 1.0,
        z_index: int = 0,
        accessible_name: str | None = None,
        accessible_description: str | None = None,
    ) -> None:
        self._title = str(title)
        self._expanded = bool(expanded)
        self._content: Component | None = None
        self._background = background or _DEFAULT_BACKGROUND
        self._hover_background = hover_background or _DEFAULT_HOVER_BACKGROUND
        self._pressed_background = pressed_background or _DEFAULT_PRESSED_BACKGROUND
        self._focused_background = focused_background or _DEFAULT_FOCUSED_BACKGROUND
        self._disabled_background = disabled_background or _DEFAULT_DISABLED_BACKGROUND
        self._foreground = foreground or _DEFAULT_FOREGROUND
        self._accent = accent or _DEFAULT_ACCENT
        self._corner_radius = self._validate_non_negative(corner_radius, "corner_radius")
        self._font_size = self._validate_positive(font_size, "font_size")
        self._font_family = self._validate_font_family(font_family)
        self._padding = self._validate_non_negative(padding, "padding")
        self._auto_accessible_name = accessible_name is None
        self._hovered = False
        self._pressed = False
        self._focused = False
        super().__init__(
            bounds=bounds,
            key=key,
            opacity=opacity,
            z_index=z_index,
            focusable=True,
            accessibility_role=AccessibilityRole.BUTTON,
            accessible_name=self._title if accessible_name is None else accessible_name,
            accessible_description=accessible_description,
        )
        self.accessible_value_text = self._state_text()
        self.on("pointer_enter", self._on_pointer_enter)
        self.on("pointer_leave", self._on_pointer_leave)
        self.on("pointer_down", self._on_pointer_down)
        self.on("pointer_up", self._on_pointer_up)
        self.on("key_down", self._on_key_down)
        self.on("key_up", self._on_key_up)
        self.on("focus_gained", self._on_focus_gained)
        self.on("focus_lost", self._on_focus_lost)
        self.on("invalidated", self._on_invalidated)
        if content is not None:
            self.set_content(content)

    @property
    def title(self) -> str:
        return self._title

    @title.setter
    def title(self, value: str) -> None:
        normalized = str(value)
        if normalized == self._title:
            return
        self._title = normalized
        if self._auto_accessible_name:
            self.accessible_name = normalized
        self.invalidate(reason="title")

    @property
    def content(self) -> Component | None:
        return self._content

    @property
    def expanded(self) -> bool:
        return self._expanded

    @expanded.setter
    def expanded(self, value: bool) -> None:
        self.set_expanded(value)

    @property
    def hovered(self) -> bool:
        return self._hovered

    @property
    def pressed(self) -> bool:
        return self._pressed

    @property
    def focused(self) -> bool:
        return self._focused

    def set_content(self, content: Component | None) -> Expander:
        """Replace the managed content subtree while preserving disclosure state."""

        if content is self._content:
            return self
        if content is self:
            raise ValueError("An expander cannot use itself as content.")
        previous = self._content
        if previous is not None:
            super().remove(previous)
        self._content = content
        if content is not None:
            super().add(content)
            content.visible = self._expanded
        self.invalidate(reason="content")
        return self

    def add(self, *children: Component) -> Expander:
        """Set exactly one managed content component."""

        if len(children) != 1:
            raise ValueError("Expander.add() requires exactly one content component.")
        return self.set_content(children[0])

    def remove(self, child: Component) -> Expander:
        if child is not self._content:
            raise ValueError("Component is not the expander's managed content.")
        super().remove(child)
        self._content = None
        self.invalidate(reason="content")
        return self

    def clear(self) -> None:
        if self._content is not None:
            self.remove(self._content)

    def set_expanded(self, expanded: bool) -> Expander:
        normalized = bool(expanded)
        if normalized == self._expanded:
            return self
        self._expanded = normalized
        if self._content is not None:
            self._content.visible = normalized
        self.accessible_value_text = self._state_text()
        self.invalidate(reason="expanded")
        self.emit("expanded_changed", expanded=normalized)
        return self

    def expand(self) -> Expander:
        return self.set_expanded(True)

    def collapse(self) -> Expander:
        return self.set_expanded(False)

    def toggle(self) -> Expander:
        return self.set_expanded(not self._expanded)

    def build_scene_node(self) -> SceneNode:
        node = SceneNode(
            key=self.key,
            kind=SceneNodeKind.RECTANGLE,
            bounds=self.bounds,
            opacity=self.opacity,
            z_index=self.z_index,
            fill=self._current_background(),
            corner_radius=CornerRadius.uniform(self._corner_radius),
            clip_to_bounds=False,
            hit_testable=self.enabled,
        )
        text_bounds = self._title_bounds()
        if self.title and text_bounds.width > 0.0 and text_bounds.height > 0.0:
            node.add(
                SceneNode(
                    key=f"{self.key}:title",
                    kind=SceneNodeKind.TEXT,
                    bounds=text_bounds,
                    fill=self._foreground,
                    text=self.title,
                    font_size=self._font_size,
                    font_family=self._font_family,
                    hit_testable=False,
                )
            )
        indicator_bounds = self._indicator_bounds()
        if indicator_bounds.width > 0.0 and indicator_bounds.height > 0.0:
            node.add(
                SceneNode(
                    key=f"{self.key}:indicator",
                    kind=SceneNodeKind.TEXT,
                    bounds=indicator_bounds,
                    fill=self._accent,
                    text="▾" if self._expanded else "›",
                    font_size=self._font_size + 2.0,
                    font_family=self._font_family,
                    hit_testable=False,
                )
            )
        return node

    def _title_bounds(self) -> Rect:
        indicator_width = max(18.0, self._font_size * 1.5)
        width = max(0.0, self.bounds.width - (2.0 * self._padding) - indicator_width)
        line_height = min(self.bounds.height, self._font_size * 1.25)
        y = self.bounds.y + max(0.0, (self.bounds.height - line_height) * 0.5)
        return Rect(self.bounds.x + self._padding, y, width, line_height)

    def _indicator_bounds(self) -> Rect:
        width = max(18.0, self._font_size * 1.5)
        height = min(self.bounds.height, self._font_size * 1.4)
        return Rect(
            self.bounds.right - self._padding - width,
            self.bounds.y + max(0.0, (self.bounds.height - height) * 0.5),
            width,
            height,
        )

    def _current_background(self) -> Color:
        if not self.enabled:
            return self._disabled_background
        if self._pressed:
            return self._pressed_background
        if self._hovered:
            return self._hover_background
        if self._focused:
            return self._focused_background
        return self._background

    def _set_interaction_state(
        self,
        *,
        hovered: bool | None = None,
        pressed: bool | None = None,
        focused: bool | None = None,
        reason: str,
    ) -> None:
        changed = False
        if hovered is not None and hovered != self._hovered:
            self._hovered = hovered
            changed = True
        if pressed is not None and pressed != self._pressed:
            self._pressed = pressed
            changed = True
        if focused is not None and focused != self._focused:
            self._focused = focused
            changed = True
        if changed:
            self.invalidate(reason=reason)

    def _on_pointer_enter(self, _event: Event) -> None:
        if self.enabled:
            self._set_interaction_state(hovered=True, reason="pointer_enter")

    def _on_pointer_leave(self, _event: Event) -> None:
        self._set_interaction_state(hovered=False, pressed=False, reason="pointer_leave")

    def _on_pointer_down(self, event: Event) -> None:
        platform_event = self._platform_event(event, PlatformEventKind.POINTER_DOWN)
        if (
            not self.enabled
            or platform_event is None
            or platform_event.button is not PointerButton.LEFT
        ):
            return
        self._set_interaction_state(pressed=True, reason="pointer_down")

    def _on_pointer_up(self, event: Event) -> None:
        platform_event = self._platform_event(event, PlatformEventKind.POINTER_UP)
        if platform_event is None or platform_event.button is not PointerButton.LEFT:
            return
        activate = self.enabled and self._pressed
        self._set_interaction_state(pressed=False, reason="pointer_up")
        if activate:
            self.toggle()
            self.emit("click", input_event=event)

    def _on_key_down(self, event: Event) -> None:
        platform_event = self._platform_event(event, PlatformEventKind.KEY_DOWN)
        if not self.enabled or platform_event is None:
            return
        if platform_event.ctrl or platform_event.alt or platform_event.meta:
            return
        if platform_event.key_code in (_VK_RETURN, _VK_SPACE):
            self._set_interaction_state(pressed=True, reason="key_down")
            event.prevent_default()
            return
        if platform_event.key_code in (_VK_RIGHT, _VK_DOWN):
            self.expand()
            event.prevent_default()
        elif platform_event.key_code in (_VK_LEFT, _VK_UP):
            self.collapse()
            event.prevent_default()

    def _on_key_up(self, event: Event) -> None:
        platform_event = self._platform_event(event, PlatformEventKind.KEY_UP)
        if platform_event is None or platform_event.key_code not in (_VK_RETURN, _VK_SPACE):
            return
        if platform_event.ctrl or platform_event.alt or platform_event.meta:
            return
        activate = self.enabled and self._pressed
        self._set_interaction_state(pressed=False, reason="key_up")
        event.prevent_default()
        if activate:
            self.toggle()
            self.emit("click", input_event=event)

    def _on_focus_gained(self, _event: Event) -> None:
        self._set_interaction_state(focused=True, reason="focus_gained")

    def _on_focus_lost(self, _event: Event) -> None:
        self._set_interaction_state(focused=False, pressed=False, reason="focus_lost")

    def _on_invalidated(self, event: Event) -> None:
        if event.data.get("reason") == "enabled" and not self.enabled:
            self._hovered = False
            self._pressed = False

    def _state_text(self) -> str:
        return "Expanded" if self._expanded else "Collapsed"

    @staticmethod
    def _platform_event(event: Event, kind: PlatformEventKind) -> PlatformEvent | None:
        platform_event = event.data.get("event")
        if isinstance(platform_event, PlatformEvent) and platform_event.kind is kind:
            return platform_event
        return None

    @staticmethod
    def _validate_positive(value: float, name: str) -> float:
        normalized = float(value)
        if not math.isfinite(normalized) or normalized <= 0.0:
            raise ValueError(f"{name} must be finite and greater than zero.")
        return normalized

    @staticmethod
    def _validate_non_negative(value: float, name: str) -> float:
        normalized = float(value)
        if not math.isfinite(normalized) or normalized < 0.0:
            raise ValueError(f"{name} must be finite and non-negative.")
        return normalized

    @staticmethod
    def _validate_font_family(value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("font_family cannot be empty.")
        return normalized


class Accordion(Component):
    """Logical group coordinating one or more :class:`Expander` widgets.

    By default only one item can be expanded at a time. ``require_one`` can be
    enabled for navigation surfaces that must always keep one panel open.
    """

    def __init__(
        self,
        *items: Expander,
        key: str | None = None,
        allow_multiple: bool = False,
        require_one: bool = False,
        accessible_name: str | None = None,
        accessible_description: str | None = None,
    ) -> None:
        super().__init__(
            "Accordion",
            key=key,
            accessibility_role=AccessibilityRole.GROUP,
            accessible_name=accessible_name or "Accordion",
            accessible_description=accessible_description,
        )
        self._allow_multiple = bool(allow_multiple)
        self._require_one = bool(require_one)
        if self._allow_multiple and self._require_one:
            raise ValueError("require_one is only supported for exclusive accordions.")
        self._subscriptions: dict[int, Callable[[], None]] = {}
        self._coordinating = False
        if items:
            self.add(*items)
        self._normalize_group()

    @property
    def allow_multiple(self) -> bool:
        return self._allow_multiple

    @property
    def require_one(self) -> bool:
        return self._require_one

    @property
    def items(self) -> tuple[Expander, ...]:
        return tuple(child for child in self.children if isinstance(child, Expander))

    @property
    def expanded_items(self) -> tuple[Expander, ...]:
        return tuple(item for item in self.items if item.expanded)

    @property
    def expanded_item(self) -> Expander | None:
        expanded = self.expanded_items
        return expanded[0] if expanded else None

    def add(self, *children: Component) -> Accordion:
        expanders = tuple(child for child in children if isinstance(child, Expander))
        if len(expanders) != len(children):
            raise TypeError("Accordion children must be Expander instances.")
        for expander in expanders:
            if expander.parent is self:
                continue
            super().add(expander)
            self._subscriptions[id(expander)] = expander.on(
                "expanded_changed",
                self._on_expander_changed,
            )
            if not self._allow_multiple and expander.expanded:
                self._collapse_others(expander)
        self._ensure_required_item()
        return self

    def remove(self, child: Component) -> Accordion:
        if not isinstance(child, Expander) or child.parent is not self:
            raise ValueError("Component is not an expander in this accordion.")
        unsubscribe = self._subscriptions.pop(id(child), None)
        if unsubscribe is not None:
            unsubscribe()
        super().remove(child)
        self._ensure_required_item()
        return self

    def clear(self) -> None:
        for item in self.items:
            self.remove(item)

    def _on_expander_changed(self, event: Event) -> None:
        item = event.source
        if not isinstance(item, Expander) or item.parent is not self:
            return
        if self._coordinating:
            return
        expanded = bool(event.data.get("expanded"))
        self._coordinating = True
        try:
            if expanded and not self._allow_multiple:
                self._collapse_others(item)
            elif not expanded and self._require_one and not self.expanded_items:
                item.expand()
        finally:
            self._coordinating = False
        self.emit("selection_changed", item=item, expanded=item.expanded)
        self.invalidate(reason="accordion_selection", source=item)

    def _collapse_others(self, active: Expander) -> None:
        for item in self.items:
            if item is not active and item.expanded:
                item.collapse()

    def _ensure_required_item(self) -> None:
        if self._require_one and self.items and not self.expanded_items:
            self.items[0].expand()

    def _normalize_group(self) -> None:
        if self._allow_multiple:
            return
        expanded = self.expanded_items
        if len(expanded) > 1:
            for item in expanded[1:]:
                item.collapse()
        self._ensure_required_item()
