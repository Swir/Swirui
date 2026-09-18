"""Retained Row/Column layout primitives for SwirUI."""

from __future__ import annotations

import math
from enum import StrEnum

from swirui.rendering.geometry import Rect, Size
from swirui.rendering.scene import SceneNode, SceneNodeKind

from .base import LayoutConstraints, Widget


class MainAxisAlignment(StrEnum):
    """Placement of children along a layout container's main axis."""

    START = "start"
    CENTER = "center"
    END = "end"
    SPACE_BETWEEN = "space_between"


class CrossAxisAlignment(StrEnum):
    """Placement of children along a layout container's cross axis."""

    START = "start"
    CENTER = "center"
    END = "end"
    STRETCH = "stretch"


class Insets:
    """Immutable logical-DIP padding values."""

    __slots__ = ("bottom", "left", "right", "top")

    def __init__(
        self,
        left: float = 0.0,
        top: float = 0.0,
        right: float = 0.0,
        bottom: float = 0.0,
    ) -> None:
        values = tuple(float(value) for value in (left, top, right, bottom))
        if any(not math.isfinite(value) or value < 0.0 for value in values):
            raise ValueError("Insets must use finite non-negative values.")
        self.left, self.top, self.right, self.bottom = values

    @classmethod
    def all(cls, value: float) -> Insets:
        return cls(value, value, value, value)

    @classmethod
    def symmetric(cls, *, horizontal: float = 0.0, vertical: float = 0.0) -> Insets:
        return cls(horizontal, vertical, horizontal, vertical)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Insets):
            return NotImplemented
        return (
            self.left,
            self.top,
            self.right,
            self.bottom,
        ) == (
            other.left,
            other.top,
            other.right,
            other.bottom,
        )

    def __repr__(self) -> str:
        return (
            "Insets("
            f"left={self.left!r}, top={self.top!r}, "
            f"right={self.right!r}, bottom={self.bottom!r}"
            ")"
        )


class _LinearLayout(Widget):
    """Shared deterministic layout engine for Row and Column."""

    _horizontal = False

    def __init__(
        self,
        *,
        bounds: Rect,
        spacing: float = 0.0,
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
            name=name,
            key=key,
            opacity=opacity,
            z_index=z_index,
            clip_to_bounds=clip_to_bounds,
        )
        self._spacing = self._validate_spacing(spacing)
        self._padding = padding if isinstance(padding, Insets) else Insets.all(padding)
        self._main_alignment = MainAxisAlignment(main_alignment)
        self._cross_alignment = CrossAxisAlignment(cross_alignment)
        self._fill_viewport = bool(fill_viewport)

    @property
    def spacing(self) -> float:
        return self._spacing

    @spacing.setter
    def spacing(self, value: float) -> None:
        normalized = self._validate_spacing(value)
        if normalized == self._spacing:
            return
        self._spacing = normalized
        self.invalidate(reason="layout_spacing")

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
    def main_alignment(self) -> MainAxisAlignment:
        return self._main_alignment

    @main_alignment.setter
    def main_alignment(self, value: MainAxisAlignment) -> None:
        normalized = MainAxisAlignment(value)
        if normalized is self._main_alignment:
            return
        self._main_alignment = normalized
        self.invalidate(reason="main_alignment")

    @property
    def cross_alignment(self) -> CrossAxisAlignment:
        return self._cross_alignment

    @cross_alignment.setter
    def cross_alignment(self, value: CrossAxisAlignment) -> None:
        normalized = CrossAxisAlignment(value)
        if normalized is self._cross_alignment:
            return
        self._cross_alignment = normalized
        self.invalidate(reason="cross_alignment")

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

    def measure(self, available: Size | None = None) -> Size:
        children = self._layout_children()
        padding_main = self._padding_main
        padding_cross = self._padding_cross
        if not children:
            natural = Size(
                padding_main if self._horizontal else padding_cross,
                padding_cross if self._horizontal else padding_main,
            )
            return self.layout_constraints.constrain(natural)

        sizes = [child.measure(available) for child in children]
        main = sum(self._main_size(size) for size in sizes)
        main += self.spacing * max(0, len(sizes) - 1)
        cross = max(self._cross_size(size) for size in sizes)
        if self._horizontal:
            natural = Size(main + padding_main, cross + padding_cross)
        else:
            natural = Size(cross + padding_cross, main + padding_main)
        return self.layout_constraints.constrain(natural)

    def prepare_layout(self, viewport: Rect) -> None:
        """Arrange visible direct Widget children before SceneGraph compilation."""

        if self.fill_viewport:
            self._set_layout_bounds(viewport)

        children = self._layout_children()
        if not children:
            return

        content = self._content_bounds()
        available_main = self._main_extent(content)
        available_cross = self._cross_extent(content)
        gap_total = self.spacing * max(0, len(children) - 1)
        child_available_main = max(0.0, available_main - gap_total)
        available_size = (
            Size(child_available_main, available_cross)
            if self._horizontal
            else Size(available_cross, child_available_main)
        )
        measured = [child.measure(available_size) for child in children]
        main_sizes = [self._main_size(size) for size in measured]

        occupied = sum(main_sizes) + gap_total
        if occupied < available_main:
            self._grow(children, main_sizes, available_main - occupied)
        elif occupied > available_main:
            self._shrink(children, main_sizes, occupied - available_main)

        remaining = max(0.0, available_main - sum(main_sizes) - gap_total)
        main_offset, gap = self._main_position(remaining, len(children))
        cursor = self._main_origin(content) + main_offset

        for child, main_size in zip(children, main_sizes, strict=True):
            final_available = (
                Size(main_size, available_cross)
                if self._horizontal
                else Size(available_cross, main_size)
            )
            final_measure = child.measure(final_available)
            cross_size = self._cross_size(final_measure)
            cross_size = self._resolve_cross_size(child, available_cross, cross_size)
            cross_offset = self._cross_offset(available_cross, cross_size)
            child_bounds = self._rect_for(
                main=cursor,
                cross=self._cross_origin(content) + cross_offset,
                main_size=main_size,
                cross_size=cross_size,
            )
            child._set_layout_bounds(child_bounds)
            cursor += main_size + gap

    def _layout_children(self) -> tuple[Widget, ...]:
        return tuple(
            child for child in self.children if isinstance(child, Widget) and child.visible
        )

    def _content_bounds(self) -> Rect:
        padding = self.padding
        width = max(0.0, self.bounds.width - padding.left - padding.right)
        height = max(0.0, self.bounds.height - padding.top - padding.bottom)
        return Rect(
            self.bounds.x + padding.left,
            self.bounds.y + padding.top,
            width,
            height,
        )

    @property
    def _padding_main(self) -> float:
        if self._horizontal:
            return self.padding.left + self.padding.right
        return self.padding.top + self.padding.bottom

    @property
    def _padding_cross(self) -> float:
        if self._horizontal:
            return self.padding.top + self.padding.bottom
        return self.padding.left + self.padding.right

    def _main_size(self, size: Size) -> float:
        return size.width if self._horizontal else size.height

    def _cross_size(self, size: Size) -> float:
        return size.height if self._horizontal else size.width

    def _main_extent(self, rect: Rect) -> float:
        return rect.width if self._horizontal else rect.height

    def _cross_extent(self, rect: Rect) -> float:
        return rect.height if self._horizontal else rect.width

    def _main_origin(self, rect: Rect) -> float:
        return rect.x if self._horizontal else rect.y

    def _cross_origin(self, rect: Rect) -> float:
        return rect.y if self._horizontal else rect.x

    def _main_limits(self, constraints: LayoutConstraints) -> tuple[float, float]:
        if self._horizontal:
            return constraints.min_width, constraints.max_width
        return constraints.min_height, constraints.max_height

    def _cross_limits(self, constraints: LayoutConstraints) -> tuple[float, float]:
        if self._horizontal:
            return constraints.min_height, constraints.max_height
        return constraints.min_width, constraints.max_width

    def _grow(self, children: tuple[Widget, ...], sizes: list[float], extra: float) -> None:
        active = {index for index, child in enumerate(children) if child.layout_grow > 0.0}
        epsilon = 1.0e-9
        while extra > epsilon and active:
            total_weight = sum(children[index].layout_grow for index in active)
            if total_weight <= epsilon:
                break
            consumed = 0.0
            saturated: set[int] = set()
            for index in tuple(active):
                child = children[index]
                _, maximum = self._main_limits(child.layout_constraints)
                share = extra * child.layout_grow / total_weight
                capacity = max(0.0, maximum - sizes[index])
                delta = min(share, capacity)
                sizes[index] += delta
                consumed += delta
                if capacity <= share + epsilon:
                    saturated.add(index)
            extra -= consumed
            active -= saturated
            if consumed <= epsilon:
                break

    def _shrink(self, children: tuple[Widget, ...], sizes: list[float], excess: float) -> None:
        active = {
            index
            for index, child in enumerate(children)
            if sizes[index] > self._main_limits(child.layout_constraints)[0]
        }
        epsilon = 1.0e-9
        while excess > epsilon and active:
            capacities = {
                index: sizes[index] - self._main_limits(children[index].layout_constraints)[0]
                for index in active
            }
            total_capacity = sum(capacities.values())
            if total_capacity <= epsilon:
                break
            removed = 0.0
            exhausted: set[int] = set()
            for index in tuple(active):
                capacity = capacities[index]
                share = excess * capacity / total_capacity
                delta = min(share, capacity)
                sizes[index] -= delta
                removed += delta
                if capacity <= share + epsilon:
                    exhausted.add(index)
            excess -= removed
            active -= exhausted
            if removed <= epsilon:
                break

    def _resolve_cross_size(
        self,
        child: Widget,
        available_cross: float,
        measured_cross: float,
    ) -> float:
        minimum, maximum = self._cross_limits(child.layout_constraints)
        if self.cross_alignment is CrossAxisAlignment.STRETCH:
            return min(max(available_cross, minimum), maximum)
        return min(max(measured_cross, minimum), maximum)

    def _cross_offset(self, available: float, size: float) -> float:
        remaining = max(0.0, available - size)
        if self.cross_alignment is CrossAxisAlignment.CENTER:
            return remaining / 2.0
        if self.cross_alignment is CrossAxisAlignment.END:
            return remaining
        return 0.0

    def _main_position(self, remaining: float, count: int) -> tuple[float, float]:
        if self.main_alignment is MainAxisAlignment.CENTER:
            return remaining / 2.0, self.spacing
        if self.main_alignment is MainAxisAlignment.END:
            return remaining, self.spacing
        if self.main_alignment is MainAxisAlignment.SPACE_BETWEEN and count > 1:
            return 0.0, self.spacing + remaining / (count - 1)
        return 0.0, self.spacing

    def _rect_for(
        self,
        *,
        main: float,
        cross: float,
        main_size: float,
        cross_size: float,
    ) -> Rect:
        if self._horizontal:
            return Rect(main, cross, main_size, cross_size)
        return Rect(cross, main, cross_size, main_size)

    @staticmethod
    def _validate_spacing(value: float) -> float:
        normalized = float(value)
        if not math.isfinite(normalized) or normalized < 0.0:
            raise ValueError("spacing must be a finite non-negative value.")
        return normalized


class Row(_LinearLayout):
    """Arrange visible Widget children from left to right in logical DIPs."""

    _horizontal = True


class Column(_LinearLayout):
    """Arrange visible Widget children from top to bottom in logical DIPs."""

    _horizontal = False
