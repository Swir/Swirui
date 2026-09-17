"""Advanced retained layout containers for the SwirUI 0.5 layout engine."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from swirui.rendering.geometry import Rect, Size
from swirui.rendering.scene import SceneNode, SceneNodeKind

from .base import Widget
from .layout import CrossAxisAlignment, Insets, MainAxisAlignment


class Dock(StrEnum):
    """Edge used by :class:`DockPanel` when arranging one direct child."""

    LEFT = "left"
    TOP = "top"
    RIGHT = "right"
    BOTTOM = "bottom"
    FILL = "fill"


class FlowDirection(StrEnum):
    """Primary direction used by :class:`Flow`."""

    HORIZONTAL = "horizontal"
    VERTICAL = "vertical"


@dataclass(frozen=True, slots=True)
class OverlayPlacement:
    """Per-child alignment and offset inside an :class:`Overlay`."""

    horizontal: CrossAxisAlignment = CrossAxisAlignment.START
    vertical: CrossAxisAlignment = CrossAxisAlignment.START
    offset_x: float = 0.0
    offset_y: float = 0.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "horizontal", CrossAxisAlignment(self.horizontal))
        object.__setattr__(self, "vertical", CrossAxisAlignment(self.vertical))
        if not math.isfinite(self.offset_x) or not math.isfinite(self.offset_y):
            raise ValueError("Overlay offsets must be finite values.")


@dataclass(frozen=True, slots=True)
class ConstraintSpec:
    """Parent-relative anchors for one :class:`ConstraintLayout` child.

    ``left``/``right`` and ``top``/``bottom`` are logical-DIP offsets from the
    corresponding parent content edge. ``center_x`` and ``center_y`` are offsets
    from the centered position. Explicit width/height win over paired-edge
    stretching; child min/max constraints are always applied last.
    """

    left: float | None = None
    top: float | None = None
    right: float | None = None
    bottom: float | None = None
    center_x: float | None = None
    center_y: float | None = None
    width: float | None = None
    height: float | None = None

    def __post_init__(self) -> None:
        for name in ("left", "top", "right", "bottom", "center_x", "center_y"):
            value = getattr(self, name)
            if value is not None and not math.isfinite(value):
                raise ValueError(f"{name} must be finite when provided.")
        for name in ("width", "height"):
            value = getattr(self, name)
            if value is not None and (not math.isfinite(value) or value < 0.0):
                raise ValueError(f"{name} must be finite and non-negative when provided.")
        if self.left is not None and self.right is not None and self.center_x is not None:
            raise ValueError("Horizontal constraints cannot combine left, right and center_x.")
        if self.top is not None and self.bottom is not None and self.center_y is not None:
            raise ValueError("Vertical constraints cannot combine top, bottom and center_y.")


class _AdvancedPanel(Widget):
    """Shared retained panel mechanics for advanced layout containers."""

    def __init__(
        self,
        *,
        bounds: Rect,
        padding: Insets | float = 0.0,
        fill_viewport: bool = False,
        name: str | None = None,
        key: str | None = None,
        opacity: float = 1.0,
        z_index: int = 0,
        clip_to_bounds: bool = False,
    ) -> None:
        super().__init__(
            bounds=bounds,
            name=name,
            key=key,
            opacity=opacity,
            z_index=z_index,
            clip_to_bounds=clip_to_bounds,
        )
        self._padding = padding if isinstance(padding, Insets) else Insets.all(padding)
        self._fill_viewport = bool(fill_viewport)

    @property
    def padding(self) -> Insets:
        return self._padding

    @padding.setter
    def padding(self, value: Insets | float) -> None:
        normalized = value if isinstance(value, Insets) else Insets.all(value)
        if normalized == self._padding:
            return
        self._padding = normalized
        self.invalidate(reason="layout_padding")

    @property
    def fill_viewport(self) -> bool:
        return self._fill_viewport

    @fill_viewport.setter
    def fill_viewport(self, value: bool) -> None:
        normalized = bool(value)
        if normalized == self._fill_viewport:
            return
        self._fill_viewport = normalized
        self.invalidate(reason="fill_viewport")

    def build_scene_node(self) -> SceneNode:
        return SceneNode(
            key=self.key,
            kind=SceneNodeKind.GROUP,
            bounds=self.bounds,
            opacity=self.opacity,
            z_index=self.z_index,
            clip_to_bounds=self.clip_to_bounds,
            hit_testable=False,
        )

    def _content_bounds(self, viewport: Rect) -> Rect:
        if self.fill_viewport:
            self._set_layout_bounds(viewport)
        padding = self.padding
        return Rect(
            self.bounds.x + padding.left,
            self.bounds.y + padding.top,
            max(0.0, self.bounds.width - padding.left - padding.right),
            max(0.0, self.bounds.height - padding.top - padding.bottom),
        )

    def _layout_children(self) -> tuple[Widget, ...]:
        return tuple(
            child for child in self.children if isinstance(child, Widget) and child.visible
        )

    def _add_padding(self, size: Size) -> Size:
        return Size(
            size.width + self.padding.left + self.padding.right,
            size.height + self.padding.top + self.padding.bottom,
        )


class DockPanel(_AdvancedPanel):
    """Consume parent edges in order and leave remaining space to fill children."""

    def __init__(
        self,
        *,
        bounds: Rect,
        padding: Insets | float = 0.0,
        spacing: float = 0.0,
        fill_viewport: bool = False,
        name: str | None = None,
        key: str | None = None,
        opacity: float = 1.0,
        z_index: int = 0,
        clip_to_bounds: bool = False,
    ) -> None:
        super().__init__(
            bounds=bounds,
            padding=padding,
            fill_viewport=fill_viewport,
            name=name,
            key=key,
            opacity=opacity,
            z_index=z_index,
            clip_to_bounds=clip_to_bounds,
        )
        self._spacing = _validate_non_negative(spacing, "spacing")
        self._docks: dict[str, Dock] = {}

    @property
    def spacing(self) -> float:
        return self._spacing

    @spacing.setter
    def spacing(self, value: float) -> None:
        normalized = _validate_non_negative(value, "spacing")
        if normalized == self._spacing:
            return
        self._spacing = normalized
        self.invalidate(reason="dock_spacing")

    def set_dock(self, child: Widget, dock: Dock) -> DockPanel:
        """Assign a direct child to an edge or the remaining fill slot."""

        normalized = Dock(dock)
        if child.parent is not None and child.parent is not self:
            raise ValueError("Dock metadata can only be assigned to this panel's child.")
        if self._docks.get(child.key, Dock.FILL) is normalized:
            return self
        self._docks[child.key] = normalized
        self.invalidate(reason="dock_assignment", source=child)
        return self

    def dock_for(self, child: Widget) -> Dock:
        return self._docks.get(child.key, Dock.FILL)

    def measure(self, available: Size | None = None) -> Size:
        children = self._layout_children()
        if not children:
            return self.layout_constraints.constrain(self._add_padding(Size(0.0, 0.0)))

        remaining_width = available.width if available is not None else math.inf
        remaining_height = available.height if available is not None else math.inf
        width = 0.0
        height = 0.0
        fill_width = 0.0
        fill_height = 0.0
        for index, child in enumerate(children):
            measured = child.measure(Size(remaining_width, remaining_height))
            dock = self.dock_for(child)
            gap = self.spacing if index > 0 else 0.0
            if dock in (Dock.LEFT, Dock.RIGHT):
                width += gap + measured.width
                height = max(height, measured.height)
                if math.isfinite(remaining_width):
                    remaining_width = max(0.0, remaining_width - measured.width - gap)
            elif dock in (Dock.TOP, Dock.BOTTOM):
                height += gap + measured.height
                width = max(width, measured.width)
                if math.isfinite(remaining_height):
                    remaining_height = max(0.0, remaining_height - measured.height - gap)
            else:
                fill_width = max(fill_width, measured.width)
                fill_height = max(fill_height, measured.height)
        natural = Size(max(width, width + fill_width), max(height, height + fill_height))
        return self.layout_constraints.constrain(self._add_padding(natural))

    def prepare_layout(self, viewport: Rect) -> None:
        remaining = self._content_bounds(viewport)
        children = self._layout_children()
        for index, child in enumerate(children):
            dock = self.dock_for(child)
            measured = child.measure(remaining.size)
            if dock is Dock.FILL:
                child._set_layout_bounds(remaining)
                continue

            if index > 0 and self.spacing > 0.0:
                remaining = _inset_for_dock_gap(remaining, dock, self.spacing)

            if dock is Dock.LEFT:
                width = min(measured.width, remaining.width)
                child._set_layout_bounds(Rect(remaining.x, remaining.y, width, remaining.height))
                remaining = Rect(
                    remaining.x + width,
                    remaining.y,
                    max(0.0, remaining.width - width),
                    remaining.height,
                )
            elif dock is Dock.RIGHT:
                width = min(measured.width, remaining.width)
                child._set_layout_bounds(
                    Rect(remaining.right - width, remaining.y, width, remaining.height)
                )
                remaining = Rect(
                    remaining.x,
                    remaining.y,
                    max(0.0, remaining.width - width),
                    remaining.height,
                )
            elif dock is Dock.TOP:
                height = min(measured.height, remaining.height)
                child._set_layout_bounds(Rect(remaining.x, remaining.y, remaining.width, height))
                remaining = Rect(
                    remaining.x,
                    remaining.y + height,
                    remaining.width,
                    max(0.0, remaining.height - height),
                )
            elif dock is Dock.BOTTOM:
                height = min(measured.height, remaining.height)
                child._set_layout_bounds(
                    Rect(remaining.x, remaining.bottom - height, remaining.width, height)
                )
                remaining = Rect(
                    remaining.x,
                    remaining.y,
                    remaining.width,
                    max(0.0, remaining.height - height),
                )


class Flow(_AdvancedPanel):
    """Content-driven bidirectional flow with optional wrapping."""

    def __init__(
        self,
        *,
        bounds: Rect,
        direction: FlowDirection = FlowDirection.HORIZONTAL,
        wrap: bool = True,
        spacing: float = 0.0,
        line_spacing: float = 0.0,
        padding: Insets | float = 0.0,
        main_alignment: MainAxisAlignment = MainAxisAlignment.START,
        cross_alignment: CrossAxisAlignment = CrossAxisAlignment.START,
        fill_viewport: bool = False,
        name: str | None = None,
        key: str | None = None,
        opacity: float = 1.0,
        z_index: int = 0,
        clip_to_bounds: bool = False,
    ) -> None:
        super().__init__(
            bounds=bounds,
            padding=padding,
            fill_viewport=fill_viewport,
            name=name,
            key=key,
            opacity=opacity,
            z_index=z_index,
            clip_to_bounds=clip_to_bounds,
        )
        self._direction = FlowDirection(direction)
        self._wrap = bool(wrap)
        self._spacing = _validate_non_negative(spacing, "spacing")
        self._line_spacing = _validate_non_negative(line_spacing, "line_spacing")
        self._main_alignment = MainAxisAlignment(main_alignment)
        self._cross_alignment = CrossAxisAlignment(cross_alignment)

    @property
    def direction(self) -> FlowDirection:
        return self._direction

    @direction.setter
    def direction(self, value: FlowDirection) -> None:
        normalized = FlowDirection(value)
        if normalized is self._direction:
            return
        self._direction = normalized
        self.invalidate(reason="flow_direction")

    @property
    def wrap(self) -> bool:
        return self._wrap

    @wrap.setter
    def wrap(self, value: bool) -> None:
        normalized = bool(value)
        if normalized == self._wrap:
            return
        self._wrap = normalized
        self.invalidate(reason="flow_wrap")

    @property
    def spacing(self) -> float:
        return self._spacing

    @spacing.setter
    def spacing(self, value: float) -> None:
        normalized = _validate_non_negative(value, "spacing")
        if normalized == self._spacing:
            return
        self._spacing = normalized
        self.invalidate(reason="flow_spacing")

    @property
    def line_spacing(self) -> float:
        return self._line_spacing

    @line_spacing.setter
    def line_spacing(self, value: float) -> None:
        normalized = _validate_non_negative(value, "line_spacing")
        if normalized == self._line_spacing:
            return
        self._line_spacing = normalized
        self.invalidate(reason="flow_line_spacing")

    def measure(self, available: Size | None = None) -> Size:
        width_limit = self.bounds.width if available is None else available.width
        height_limit = self.bounds.height if available is None else available.height
        inner_width = max(0.0, width_limit - self.padding.left - self.padding.right)
        inner_height = max(0.0, height_limit - self.padding.top - self.padding.bottom)
        lines = self._lines(Size(inner_width, inner_height))
        natural = self._natural_size(lines)
        return self.layout_constraints.constrain(self._add_padding(natural))

    def prepare_layout(self, viewport: Rect) -> None:
        content = self._content_bounds(viewport)
        lines = self._lines(content.size)
        cross_cursor = content.y if self.direction is FlowDirection.HORIZONTAL else content.x

        for line in lines:
            line_main = sum(self._main_size(size) for _child, size in line)
            line_main += self.spacing * max(0, len(line) - 1)
            line_cross = max(self._cross_size(size) for _child, size in line)
            available_main = content.width if self.direction is FlowDirection.HORIZONTAL else content.height
            remaining = max(0.0, available_main - line_main)
            offset, gap = _main_position(self.main_alignment, remaining, len(line), self.spacing)
            main_cursor = (
                content.x + offset
                if self.direction is FlowDirection.HORIZONTAL
                else content.y + offset
            )

            for child, size in line:
                main_size = self._main_size(size)
                measured_cross = self._cross_size(size)
                cross_size = self._resolve_cross(child, line_cross, measured_cross)
                cross_offset = _cross_offset(self.cross_alignment, line_cross, cross_size)
                if self.direction is FlowDirection.HORIZONTAL:
                    bounds = Rect(
                        main_cursor,
                        cross_cursor + cross_offset,
                        main_size,
                        cross_size,
                    )
                else:
                    bounds = Rect(
                        cross_cursor + cross_offset,
                        main_cursor,
                        cross_size,
                        main_size,
                    )
                child._set_layout_bounds(bounds)
                main_cursor += main_size + gap
            cross_cursor += line_cross + self.line_spacing

    @property
    def main_alignment(self) -> MainAxisAlignment:
        return self._main_alignment

    @main_alignment.setter
    def main_alignment(self, value: MainAxisAlignment) -> None:
        normalized = MainAxisAlignment(value)
        if normalized is self._main_alignment:
            return
        self._main_alignment = normalized
        self.invalidate(reason="flow_main_alignment")

    @property
    def cross_alignment(self) -> CrossAxisAlignment:
        return self._cross_alignment

    @cross_alignment.setter
    def cross_alignment(self, value: CrossAxisAlignment) -> None:
        normalized = CrossAxisAlignment(value)
        if normalized is self._cross_alignment:
            return
        self._cross_alignment = normalized
        self.invalidate(reason="flow_cross_alignment")

    def _lines(self, available: Size) -> list[list[tuple[Widget, Size]]]:
        lines: list[list[tuple[Widget, Size]]] = []
        current: list[tuple[Widget, Size]] = []
        occupied = 0.0
        limit = available.width if self.direction is FlowDirection.HORIZONTAL else available.height

        for child in self._layout_children():
            size = child.measure(available)
            main = self._main_size(size)
            needed = main if not current else self.spacing + main
            if self.wrap and current and occupied + needed > limit:
                lines.append(current)
                current = []
                occupied = 0.0
                needed = main
            current.append((child, size))
            occupied += needed
        if current:
            lines.append(current)
        return lines

    def _natural_size(self, lines: list[list[tuple[Widget, Size]]]) -> Size:
        if not lines:
            return Size(0.0, 0.0)
        main = max(
            sum(self._main_size(size) for _child, size in line)
            + self.spacing * max(0, len(line) - 1)
            for line in lines
        )
        cross = sum(
            max(self._cross_size(size) for _child, size in line) for line in lines
        ) + self.line_spacing * max(0, len(lines) - 1)
        if self.direction is FlowDirection.HORIZONTAL:
            return Size(main, cross)
        return Size(cross, main)

    def _main_size(self, size: Size) -> float:
        return size.width if self.direction is FlowDirection.HORIZONTAL else size.height

    def _cross_size(self, size: Size) -> float:
        return size.height if self.direction is FlowDirection.HORIZONTAL else size.width

    def _resolve_cross(self, child: Widget, available: float, measured: float) -> float:
        constraints = child.layout_constraints
        if self.direction is FlowDirection.HORIZONTAL:
            minimum, maximum = constraints.min_height, constraints.max_height
        else:
            minimum, maximum = constraints.min_width, constraints.max_width
        target = available if self.cross_alignment is CrossAxisAlignment.STRETCH else measured
        return min(max(target, minimum), maximum)


class Overlay(_AdvancedPanel):
    """Overlay children using independent alignment and logical-DIP offsets."""

    def __init__(
        self,
        *,
        bounds: Rect,
        padding: Insets | float = 0.0,
        fill_viewport: bool = False,
        name: str | None = None,
        key: str | None = None,
        opacity: float = 1.0,
        z_index: int = 0,
        clip_to_bounds: bool = False,
    ) -> None:
        super().__init__(
            bounds=bounds,
            padding=padding,
            fill_viewport=fill_viewport,
            name=name,
            key=key,
            opacity=opacity,
            z_index=z_index,
            clip_to_bounds=clip_to_bounds,
        )
        self._placements: dict[str, OverlayPlacement] = {}

    def set_placement(self, child: Widget, placement: OverlayPlacement) -> Overlay:
        if child.parent is not None and child.parent is not self:
            raise ValueError("Overlay placement can only be assigned to this overlay's child.")
        if self._placements.get(child.key) == placement:
            return self
        self._placements[child.key] = placement
        self.invalidate(reason="overlay_placement", source=child)
        return self

    def placement_for(self, child: Widget) -> OverlayPlacement:
        return self._placements.get(child.key, OverlayPlacement())

    def measure(self, available: Size | None = None) -> Size:
        children = self._layout_children()
        if not children:
            return self.layout_constraints.constrain(self._add_padding(Size(0.0, 0.0)))
        sizes = [child.measure(available) for child in children]
        natural = Size(
            max(size.width for size in sizes),
            max(size.height for size in sizes),
        )
        return self.layout_constraints.constrain(self._add_padding(natural))

    def prepare_layout(self, viewport: Rect) -> None:
        content = self._content_bounds(viewport)
        for child in self._layout_children():
            placement = self.placement_for(child)
            measured = child.measure(content.size)
            width = _aligned_extent(
                measured.width,
                content.width,
                child.layout_constraints.min_width,
                child.layout_constraints.max_width,
                placement.horizontal,
            )
            height = _aligned_extent(
                measured.height,
                content.height,
                child.layout_constraints.min_height,
                child.layout_constraints.max_height,
                placement.vertical,
            )
            child._set_layout_bounds(
                Rect(
                    _aligned_origin(content.x, content.width, width, placement.horizontal)
                    + placement.offset_x,
                    _aligned_origin(content.y, content.height, height, placement.vertical)
                    + placement.offset_y,
                    width,
                    height,
                )
            )


class ConstraintLayout(_AdvancedPanel):
    """Arrange children from explicit parent-relative edge and center constraints."""

    def __init__(
        self,
        *,
        bounds: Rect,
        padding: Insets | float = 0.0,
        fill_viewport: bool = False,
        name: str | None = None,
        key: str | None = None,
        opacity: float = 1.0,
        z_index: int = 0,
        clip_to_bounds: bool = False,
    ) -> None:
        super().__init__(
            bounds=bounds,
            padding=padding,
            fill_viewport=fill_viewport,
            name=name,
            key=key,
            opacity=opacity,
            z_index=z_index,
            clip_to_bounds=clip_to_bounds,
        )
        self._constraints: dict[str, ConstraintSpec] = {}

    def set_constraints(self, child: Widget, spec: ConstraintSpec) -> ConstraintLayout:
        if child.parent is not None and child.parent is not self:
            raise ValueError("Constraint metadata can only be assigned to this layout's child.")
        if self._constraints.get(child.key) == spec:
            return self
        self._constraints[child.key] = spec
        self.invalidate(reason="constraint_spec", source=child)
        return self

    def constraints_for(self, child: Widget) -> ConstraintSpec:
        return self._constraints.get(child.key, ConstraintSpec())

    def measure(self, available: Size | None = None) -> Size:
        children = self._layout_children()
        if not children:
            return self.layout_constraints.constrain(self._add_padding(Size(0.0, 0.0)))
        max_right = 0.0
        max_bottom = 0.0
        for child in children:
            size = child.measure(available)
            spec = self.constraints_for(child)
            width = size.width if spec.width is None else spec.width
            height = size.height if spec.height is None else spec.height
            left = spec.left or 0.0
            top = spec.top or 0.0
            right = spec.right or 0.0
            bottom = spec.bottom or 0.0
            max_right = max(max_right, left + width + right)
            max_bottom = max(max_bottom, top + height + bottom)
        return self.layout_constraints.constrain(self._add_padding(Size(max_right, max_bottom)))

    def prepare_layout(self, viewport: Rect) -> None:
        content = self._content_bounds(viewport)
        for child in self._layout_children():
            spec = self.constraints_for(child)
            measured = child.measure(content.size)
            width = self._resolve_extent(
                measured.width,
                spec.width,
                spec.left,
                spec.right,
                content.width,
                child.layout_constraints.min_width,
                child.layout_constraints.max_width,
            )
            height = self._resolve_extent(
                measured.height,
                spec.height,
                spec.top,
                spec.bottom,
                content.height,
                child.layout_constraints.min_height,
                child.layout_constraints.max_height,
            )
            x = self._resolve_origin(
                content.x,
                content.width,
                width,
                spec.left,
                spec.right,
                spec.center_x,
            )
            y = self._resolve_origin(
                content.y,
                content.height,
                height,
                spec.top,
                spec.bottom,
                spec.center_y,
            )
            child._set_layout_bounds(Rect(x, y, width, height))

    @staticmethod
    def _resolve_extent(
        measured: float,
        explicit: float | None,
        near: float | None,
        far: float | None,
        available: float,
        minimum: float,
        maximum: float,
    ) -> float:
        if explicit is not None:
            target = explicit
        elif near is not None and far is not None:
            target = max(0.0, available - near - far)
        else:
            target = measured
        return min(max(target, minimum), maximum)

    @staticmethod
    def _resolve_origin(
        origin: float,
        available: float,
        extent: float,
        near: float | None,
        far: float | None,
        center: float | None,
    ) -> float:
        if near is not None:
            return origin + near
        if far is not None:
            return origin + available - far - extent
        if center is not None:
            return origin + (available - extent) / 2.0 + center
        return origin


def _validate_non_negative(value: float, name: str) -> float:
    normalized = float(value)
    if not math.isfinite(normalized) or normalized < 0.0:
        raise ValueError(f"{name} must be a finite non-negative value.")
    return normalized


def _aligned_extent(
    measured: float,
    available: float,
    minimum: float,
    maximum: float,
    alignment: CrossAxisAlignment,
) -> float:
    target = available if alignment is CrossAxisAlignment.STRETCH else measured
    return min(max(target, minimum), maximum)


def _aligned_origin(
    origin: float,
    available: float,
    extent: float,
    alignment: CrossAxisAlignment,
) -> float:
    remaining = max(0.0, available - extent)
    if alignment is CrossAxisAlignment.CENTER:
        return origin + remaining / 2.0
    if alignment is CrossAxisAlignment.END:
        return origin + remaining
    return origin


def _cross_offset(alignment: CrossAxisAlignment, available: float, extent: float) -> float:
    remaining = max(0.0, available - extent)
    if alignment is CrossAxisAlignment.CENTER:
        return remaining / 2.0
    if alignment is CrossAxisAlignment.END:
        return remaining
    return 0.0


def _main_position(
    alignment: MainAxisAlignment,
    remaining: float,
    count: int,
    spacing: float,
) -> tuple[float, float]:
    if alignment is MainAxisAlignment.CENTER:
        return remaining / 2.0, spacing
    if alignment is MainAxisAlignment.END:
        return remaining, spacing
    if alignment is MainAxisAlignment.SPACE_BETWEEN and count > 1:
        return 0.0, spacing + remaining / (count - 1)
    return 0.0, spacing


def _inset_for_dock_gap(rect: Rect, dock: Dock, gap: float) -> Rect:
    if dock is Dock.LEFT:
        return Rect(
            min(rect.right, rect.x + gap),
            rect.y,
            max(0.0, rect.width - gap),
            rect.height,
        )
    if dock is Dock.RIGHT:
        return Rect(rect.x, rect.y, max(0.0, rect.width - gap), rect.height)
    if dock is Dock.TOP:
        return Rect(
            rect.x,
            min(rect.bottom, rect.y + gap),
            rect.width,
            max(0.0, rect.height - gap),
        )
    if dock is Dock.BOTTOM:
        return Rect(rect.x, rect.y, rect.width, max(0.0, rect.height - gap))
    return rect
