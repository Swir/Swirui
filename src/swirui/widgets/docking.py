"""Retained IDE-style docking workspace for SwirUI professional widgets."""

from __future__ import annotations

import math
from collections.abc import Hashable, Sequence
from dataclasses import dataclass, replace
from typing import Literal, cast

from swirui.core import (
    AccessibilityNode,
    AccessibilityRole,
    Component,
    Event,
    build_accessibility_tree,
)
from swirui.platforms import PlatformEvent, PlatformEventKind, PointerButton
from swirui.rendering.geometry import Color, CornerRadius, Rect
from swirui.rendering.scene import SceneNode, SceneNodeKind

from .base import Widget

DockPosition = Literal["left", "right", "top", "bottom", "center"]

_DEFAULT_BACKGROUND = Color.from_hex("#06101A")
_DEFAULT_PANE_BACKGROUND = Color.from_hex("#071722")
_DEFAULT_HEADER_BACKGROUND = Color.from_hex("#0A2030")
_DEFAULT_ACTIVE_HEADER_BACKGROUND = Color.from_hex("#0B3550")
_DEFAULT_FOREGROUND = Color.from_hex("#DDF5FF")
_DEFAULT_ACCENT = Color.from_hex("#23C9FF")


@dataclass(frozen=True, slots=True)
class DockPane:
    """Immutable docking descriptor with stable identity and retained content."""

    key: Hashable
    title: str
    content: Component
    dock: DockPosition = "center"
    extent: float = 240.0

    def __post_init__(self) -> None:
        if not isinstance(self.key, Hashable):
            raise TypeError("DockPane.key must be hashable.")
        if not self.title.strip():
            raise ValueError("DockPane.title must not be empty.")
        if not isinstance(self.content, Component):
            raise TypeError("DockPane.content must be a Component.")
        object.__setattr__(self, "dock", _normalize_dock(self.dock))
        extent = float(self.extent)
        if not math.isfinite(extent) or extent <= 0.0:
            raise ValueError("DockPane.extent must be finite and positive.")
        object.__setattr__(self, "extent", extent)


class DockWorkspace(Widget):
    """Retained docking workspace with edge panes and a tabbed center region.

    Edge panes carve deterministic logical-DIP strips from the available workspace.
    Center panes share the remaining region and expose stable-key activation without
    recreating their retained content. Panes can be re-docked at runtime through the
    public Python API while rendering continues through the existing SceneGraph/wgpu
    pipeline.
    """

    def __init__(
        self,
        panes: Sequence[DockPane],
        *,
        bounds: Rect,
        key: str | None = None,
        active_key: Hashable | None = None,
        header_height: float = 34.0,
        min_center_extent: float = 120.0,
        corner_radius: float = 6.0,
        font_size: float = 13.0,
        font_family: str = "Segoe UI",
        background: Color | None = None,
        pane_background: Color | None = None,
        header_background: Color | None = None,
        active_header_background: Color | None = None,
        foreground: Color | None = None,
        accent: Color | None = None,
        opacity: float = 1.0,
        z_index: int = 0,
        accessible_name: str = "Dock workspace",
        accessible_description: str | None = None,
    ) -> None:
        self._panes = self._validate_panes(panes)
        self._header_height = self._validate_positive(header_height, "header_height")
        self._min_center_extent = self._validate_non_negative(
            min_center_extent, "min_center_extent"
        )
        self._corner_radius = self._validate_non_negative(corner_radius, "corner_radius")
        self._font_size = self._validate_positive(font_size, "font_size")
        self._font_family = str(font_family).strip()
        if not self._font_family:
            raise ValueError("font_family must not be empty.")
        self._background = background or _DEFAULT_BACKGROUND
        self._pane_background = pane_background or _DEFAULT_PANE_BACKGROUND
        self._header_background = header_background or _DEFAULT_HEADER_BACKGROUND
        self._active_header_background = (
            active_header_background or _DEFAULT_ACTIVE_HEADER_BACKGROUND
        )
        self._foreground = foreground or _DEFAULT_FOREGROUND
        self._accent = accent or _DEFAULT_ACCENT
        self._active_key = self._initial_active_key(active_key)
        self._active_center_key = self._initial_center_key(active_key)

        super().__init__(
            bounds=bounds,
            key=key,
            opacity=opacity,
            z_index=z_index,
            clip_to_bounds=True,
            focusable=True,
            accessibility_role=AccessibilityRole.GROUP,
            accessible_name=accessible_name,
            accessible_description=accessible_description,
        )
        self.on("pointer_down", self._on_pointer_down)
        self._attach_contents()
        self._sync_accessibility_value()

    @property
    def panes(self) -> tuple[DockPane, ...]:
        return self._panes

    @property
    def active_key(self) -> Hashable | None:
        return self._active_key

    @property
    def active_pane(self) -> DockPane | None:
        return self._pane_for_key(self._active_key)

    @property
    def active_center_key(self) -> Hashable | None:
        return self._active_center_key

    @property
    def header_height(self) -> float:
        return min(self._header_height, self.bounds.height)

    def set_panes(self, panes: Sequence[DockPane]) -> DockWorkspace:
        """Replace docking descriptors while preserving stable active identities."""

        normalized = self._validate_panes(panes)
        if normalized == self._panes:
            return self
        active_key = self._active_key
        active_center_key = self._active_center_key
        for child in tuple(self.children):
            super().remove(child)
        self._panes = normalized
        keys = {pane.key for pane in normalized}
        centers = {pane.key for pane in normalized if pane.dock == "center"}
        self._active_key = active_key if active_key in keys else self._first_key()
        self._active_center_key = (
            active_center_key if active_center_key in centers else self._first_center_key()
        )
        if self._active_key is None:
            self._active_key = self._active_center_key
        self._attach_contents()
        self._sync_accessibility_value()
        self.invalidate(reason="panes")
        return self

    def activate_pane(self, key: Hashable) -> DockWorkspace:
        """Activate a pane by stable key and reveal it when it belongs to center."""

        pane = self._require_pane(key)
        changed = pane.key != self._active_key
        center_changed = pane.dock == "center" and pane.key != self._active_center_key
        if not changed and not center_changed:
            return self
        previous = self._active_key
        self._active_key = pane.key
        if pane.dock == "center":
            self._active_center_key = pane.key
        self._sync_content_visibility()
        self._sync_accessibility_value()
        self.invalidate(reason="active_pane")
        self.emit(
            "active_pane_changed",
            key=pane.key,
            pane=pane,
            previous_key=previous,
        )
        return self

    def dock_pane(
        self,
        key: Hashable,
        dock: DockPosition,
        *,
        extent: float | None = None,
    ) -> DockWorkspace:
        """Move a pane to a new docking region without replacing its content."""

        pane = self._require_pane(key)
        normalized_dock = _normalize_dock(dock)
        normalized_extent = pane.extent if extent is None else self._validate_positive(
            extent, "extent"
        )
        if pane.dock == normalized_dock and pane.extent == normalized_extent:
            return self

        updated = replace(pane, dock=normalized_dock, extent=normalized_extent)
        self._panes = tuple(
            updated if candidate.key == key else candidate for candidate in self._panes
        )
        old_center_key = self._active_center_key
        centers = {candidate.key for candidate in self._panes if candidate.dock == "center"}
        if normalized_dock == "center":
            self._active_center_key = key
        elif old_center_key not in centers:
            self._active_center_key = self._first_center_key()
        self._active_key = key
        self._sync_content_visibility()
        self._sync_accessibility_value()
        self.invalidate(reason="dock")
        self.emit(
            "pane_docked",
            key=key,
            pane=updated,
            old_dock=pane.dock,
            dock=normalized_dock,
            extent=normalized_extent,
        )
        return self

    def pane_bounds(self, key: Hashable) -> Rect:
        """Return the current logical-DIP rectangle assigned to one pane."""

        self._require_pane(key)
        return self._pane_bounds()[key]

    def content_bounds(self, key: Hashable) -> Rect:
        """Return the content rectangle below the pane header."""

        pane_bounds = self.pane_bounds(key)
        header = min(self._header_height, pane_bounds.height)
        return Rect(
            pane_bounds.x,
            pane_bounds.y + header,
            pane_bounds.width,
            max(0.0, pane_bounds.height - header),
        )

    def prepare_layout(self, viewport: Rect) -> None:
        """Arrange visible widget content into its managed docking region."""

        _ = viewport
        for pane in self._panes:
            if not pane.content.visible or not isinstance(pane.content, Widget):
                continue
            pane.content._set_layout_bounds(self.content_bounds(pane.key))

    def build_scene_node(self) -> SceneNode:
        root = SceneNode(
            key=self.key,
            kind=SceneNodeKind.RECTANGLE,
            bounds=self.bounds,
            opacity=self.opacity,
            z_index=self.z_index,
            fill=self._background,
            corner_radius=CornerRadius.uniform(self._corner_radius),
            clip_to_bounds=True,
            hit_testable=self.enabled,
        )
        bounds_by_key = self._pane_bounds()
        for pane in self._visible_shell_panes():
            pane_bounds = bounds_by_key[pane.key]
            root.add(
                SceneNode(
                    key=f"{self.key}:pane:{pane.key}:background",
                    kind=SceneNodeKind.RECTANGLE,
                    bounds=pane_bounds,
                    fill=self._pane_background,
                    corner_radius=CornerRadius.uniform(self._corner_radius),
                    z_index=0,
                    hit_testable=False,
                )
            )

        for pane, header_bounds in self._header_regions(bounds_by_key):
            active = pane.key == self._active_key
            header = SceneNode(
                key=f"{self.key}:pane:{pane.key}:header",
                kind=SceneNodeKind.RECTANGLE,
                bounds=header_bounds,
                fill=(
                    self._active_header_background if active else self._header_background
                ),
                z_index=10,
                hit_testable=False,
            )
            text_height = min(header_bounds.height, self._font_size * 1.35)
            header.add(
                SceneNode(
                    key=f"{self.key}:pane:{pane.key}:title",
                    kind=SceneNodeKind.TEXT,
                    bounds=Rect(
                        header_bounds.x + 10.0,
                        header_bounds.y + max(0.0, (header_bounds.height - text_height) * 0.5),
                        max(0.0, header_bounds.width - 20.0),
                        text_height,
                    ),
                    fill=self._foreground,
                    text=pane.title,
                    font_size=self._font_size,
                    font_family=self._font_family,
                    z_index=11,
                    hit_testable=False,
                )
            )
            if active:
                header.add(
                    SceneNode(
                        key=f"{self.key}:pane:{pane.key}:accent",
                        kind=SceneNodeKind.RECTANGLE,
                        bounds=Rect(
                            header_bounds.x,
                            header_bounds.bottom - 2.0,
                            header_bounds.width,
                            2.0,
                        ),
                        fill=self._accent,
                        z_index=12,
                        hit_testable=False,
                    )
                )
            root.add(header)
        return root

    def accessibility_snapshot(
        self,
        *,
        focused: Component | None = None,
    ) -> AccessibilityNode:
        children: list[AccessibilityNode] = []
        for pane in self._panes:
            active = pane.key == self._active_key
            children.append(
                AccessibilityNode(
                    key=f"{self.key}:a11y:pane:{pane.key}",
                    role=AccessibilityRole.BUTTON,
                    name=pane.title,
                    description=f"Docked {pane.dock}",
                    enabled=self.enabled,
                    focusable=False,
                    focused=False,
                    selected=active,
                    active=active,
                )
            )
            if pane.content.visible:
                content = build_accessibility_tree(pane.content, focused=focused)
                if content is not None:
                    children.append(content)
        return AccessibilityNode(
            key=self.key,
            role=AccessibilityRole.GROUP,
            name=self.accessible_name or self.name,
            description=self.accessible_description,
            enabled=self.enabled,
            focusable=self.focusable,
            focused=focused is self,
            value_text=self.accessible_value_text,
            children=tuple(children),
        )

    def _attach_contents(self) -> None:
        if self._panes:
            super().add(*(pane.content for pane in self._panes))
        self._sync_content_visibility()

    def _sync_content_visibility(self) -> None:
        for pane in self._panes:
            pane.content.visible = pane.dock != "center" or pane.key == self._active_center_key

    def _sync_accessibility_value(self) -> None:
        active = self.active_pane
        if active is None:
            self.accessible_value_text = f"No active pane of {len(self._panes)}"
        else:
            self.accessible_value_text = (
                f"{active.title} active, docked {active.dock}, {len(self._panes)} panes"
            )

    def _pane_bounds(self) -> dict[Hashable, Rect]:
        remaining = self.bounds
        result: dict[Hashable, Rect] = {}
        has_center = any(pane.dock == "center" for pane in self._panes)
        for pane in self._panes:
            if pane.dock == "center":
                continue
            required_center = self._min_center_extent if has_center else 0.0
            if pane.dock in {"left", "right"}:
                extent = min(
                    pane.extent,
                    max(0.0, remaining.width - required_center),
                )
                if pane.dock == "left":
                    bounds = Rect(remaining.x, remaining.y, extent, remaining.height)
                    remaining = Rect(
                        bounds.right,
                        remaining.y,
                        max(0.0, remaining.width - extent),
                        remaining.height,
                    )
                else:
                    bounds = Rect(
                        remaining.right - extent,
                        remaining.y,
                        extent,
                        remaining.height,
                    )
                    remaining = Rect(
                        remaining.x,
                        remaining.y,
                        max(0.0, remaining.width - extent),
                        remaining.height,
                    )
            else:
                extent = min(
                    pane.extent,
                    max(0.0, remaining.height - required_center),
                )
                if pane.dock == "top":
                    bounds = Rect(remaining.x, remaining.y, remaining.width, extent)
                    remaining = Rect(
                        remaining.x,
                        bounds.bottom,
                        remaining.width,
                        max(0.0, remaining.height - extent),
                    )
                else:
                    bounds = Rect(
                        remaining.x,
                        remaining.bottom - extent,
                        remaining.width,
                        extent,
                    )
                    remaining = Rect(
                        remaining.x,
                        remaining.y,
                        remaining.width,
                        max(0.0, remaining.height - extent),
                    )
            result[pane.key] = bounds

        for pane in self._panes:
            if pane.dock == "center":
                result[pane.key] = remaining
        return result

    def _visible_shell_panes(self) -> tuple[DockPane, ...]:
        visible: list[DockPane] = [pane for pane in self._panes if pane.dock != "center"]
        active_center = self._pane_for_key(self._active_center_key)
        if active_center is not None and active_center.dock == "center":
            visible.append(active_center)
        return tuple(visible)

    def _header_regions(
        self,
        bounds_by_key: dict[Hashable, Rect],
    ) -> tuple[tuple[DockPane, Rect], ...]:
        regions: list[tuple[DockPane, Rect]] = []
        for pane in self._panes:
            if pane.dock == "center":
                continue
            pane_bounds = bounds_by_key[pane.key]
            regions.append(
                (
                    pane,
                    Rect(
                        pane_bounds.x,
                        pane_bounds.y,
                        pane_bounds.width,
                        min(self._header_height, pane_bounds.height),
                    ),
                )
            )

        center_panes = tuple(pane for pane in self._panes if pane.dock == "center")
        if center_panes:
            center_bounds = bounds_by_key[center_panes[0].key]
            width = center_bounds.width / len(center_panes) if center_panes else 0.0
            for index, pane in enumerate(center_panes):
                x = center_bounds.x + width * index
                actual_width = (
                    center_bounds.right - x if index == len(center_panes) - 1 else width
                )
                regions.append(
                    (
                        pane,
                        Rect(
                            x,
                            center_bounds.y,
                            max(0.0, actual_width),
                            min(self._header_height, center_bounds.height),
                        ),
                    )
                )
        return tuple(regions)

    def _on_pointer_down(self, event: Event) -> None:
        platform_event = self._platform_event(event, PlatformEventKind.POINTER_DOWN)
        if (
            not self.enabled
            or platform_event is None
            or platform_event.button is not PointerButton.LEFT
            or platform_event.x is None
            or platform_event.y is None
        ):
            return
        bounds_by_key = self._pane_bounds()
        for pane, header_bounds in self._header_regions(bounds_by_key):
            if _contains(header_bounds, platform_event.x, platform_event.y):
                self.activate_pane(pane.key)
                event.prevent_default()
                return

    def _initial_active_key(self, key: Hashable | None) -> Hashable | None:
        if key is None:
            return self._first_key()
        self._require_pane(key)
        return key

    def _initial_center_key(self, key: Hashable | None) -> Hashable | None:
        if key is not None:
            pane = self._require_pane(key)
            if pane.dock == "center":
                return key
        return self._first_center_key()

    def _first_key(self) -> Hashable | None:
        return None if not self._panes else self._panes[0].key

    def _first_center_key(self) -> Hashable | None:
        return next((pane.key for pane in self._panes if pane.dock == "center"), None)

    def _pane_for_key(self, key: Hashable | None) -> DockPane | None:
        if key is None:
            return None
        return next((pane for pane in self._panes if pane.key == key), None)

    def _require_pane(self, key: Hashable) -> DockPane:
        pane = self._pane_for_key(key)
        if pane is None:
            raise KeyError(f"Unknown dock pane key: {key!r}")
        return pane

    @staticmethod
    def _platform_event(event: Event, kind: PlatformEventKind) -> PlatformEvent | None:
        platform_event = event.data.get("event")
        if isinstance(platform_event, PlatformEvent) and platform_event.kind is kind:
            return platform_event
        return None

    @staticmethod
    def _validate_panes(panes: Sequence[DockPane]) -> tuple[DockPane, ...]:
        normalized = tuple(panes)
        seen_keys: set[Hashable] = set()
        seen_content: set[int] = set()
        for pane in normalized:
            if not isinstance(pane, DockPane):
                raise TypeError("DockWorkspace panes must contain DockPane values.")
            if pane.key in seen_keys:
                raise ValueError(f"DockPane keys must be unique; duplicate {pane.key!r}.")
            content_id = id(pane.content)
            if content_id in seen_content:
                raise ValueError("Each DockPane must own a distinct content component.")
            seen_keys.add(pane.key)
            seen_content.add(content_id)
        return normalized

    @staticmethod
    def _validate_positive(value: float, name: str) -> float:
        normalized = float(value)
        if not math.isfinite(normalized) or normalized <= 0.0:
            raise ValueError(f"{name} must be finite and positive.")
        return normalized

    @staticmethod
    def _validate_non_negative(value: float, name: str) -> float:
        normalized = float(value)
        if not math.isfinite(normalized) or normalized < 0.0:
            raise ValueError(f"{name} must be finite and non-negative.")
        return normalized


def _normalize_dock(value: str) -> DockPosition:
    normalized = str(value).strip().lower()
    if normalized not in {"left", "right", "top", "bottom", "center"}:
        raise ValueError("dock must be left, right, top, bottom or center.")
    return cast(DockPosition, normalized)


def _contains(bounds: Rect, x: float, y: float) -> bool:
    return bounds.x <= x < bounds.right and bounds.y <= y < bounds.bottom
