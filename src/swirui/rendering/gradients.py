"""Backend-neutral gradient primitives built on SwirUI's retained GPU path pipeline.

The first Visual Engine gradient slices deliberately reuse the already-verified
filled-path renderer instead of introducing effect-specific native pipelines.
Linear gradients are tessellated into convex projection bands. Radial gradients
are tessellated into nested convex disks over an edge-color backing rectangle.
Both forms therefore flow through the same clipped, HiDPI-aware native GPU shape
batch as ordinary :class:`SceneNodeKind.PATH` content.

Coordinates are normalized relative to the supplied bounds. ``Point(0, 0)`` is
the top-left corner and ``Point(1, 1)`` is the bottom-right corner. Normalized
coordinates may extend outside that range so applications can place gradient
axes or focal centers beyond the painted rectangle.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass

from .geometry import Color, Path2D, Point, Rect
from .scene import SceneNode, SceneNodeKind

_EPSILON = 1.0e-9
_DEFAULT_STEPS = 96
_DEFAULT_RADIAL_STEPS = 64
_DEFAULT_RADIAL_SEGMENTS = 48
_MAX_STEPS = 512
_MAX_RADIAL_SEGMENTS = 256
_UNIT_RECTANGLE = (
    Point(0.0, 0.0),
    Point(1.0, 0.0),
    Point(1.0, 1.0),
    Point(0.0, 1.0),
)


@dataclass(frozen=True, slots=True)
class GradientStop:
    """One normalized color stop shared by gradient paint types."""

    offset: float
    color: Color

    def __post_init__(self) -> None:
        if not math.isfinite(self.offset) or not 0.0 <= self.offset <= 1.0:
            raise ValueError("Gradient stop offsets must be finite values between 0.0 and 1.0.")


@dataclass(frozen=True, slots=True)
class LinearGradient:
    """Immutable multi-stop linear gradient in normalized local coordinates."""

    start: Point
    end: Point
    stops: tuple[GradientStop, ...]

    def __post_init__(self) -> None:
        values = (self.start.x, self.start.y, self.end.x, self.end.y)
        if any(not math.isfinite(value) for value in values):
            raise ValueError("Linear gradient endpoints must use finite coordinates.")
        if math.isclose(self.start.x, self.end.x, abs_tol=_EPSILON) and math.isclose(
            self.start.y, self.end.y, abs_tol=_EPSILON
        ):
            raise ValueError("Linear gradient start and end points must differ.")
        _validate_stops(self.stops)

    @classmethod
    def two_color(
        cls,
        start_color: Color,
        end_color: Color,
        *,
        start: Point | None = None,
        end: Point | None = None,
    ) -> LinearGradient:
        """Create the common two-color gradient spanning offsets 0 → 1."""

        return cls(
            start=Point(0.0, 0.5) if start is None else start,
            end=Point(1.0, 0.5) if end is None else end,
            stops=(GradientStop(0.0, start_color), GradientStop(1.0, end_color)),
        )

    def color_at(self, offset: float) -> Color:
        """Sample the gradient with edge colors clamped outside the stop range."""

        return _color_at_stops(self.stops, offset)

    def to_scene_node(
        self,
        key: str,
        bounds: Rect,
        *,
        steps: int = _DEFAULT_STEPS,
        opacity: float = 1.0,
        z_index: int = 0,
    ) -> SceneNode:
        """Build a retained scene subtree rendered by the native GPU path batch.

        ``steps`` controls the tessellation quality. The generated convex bands
        retain ``key`` so SceneGraph hit-testing still resolves to the owning
        component's stable key instead of exposing implementation-only band ids.
        The parent clips all bands to the requested bounds and carries opacity and
        z-order as one logical visual.
        """

        _validate_visual_arguments(key, bounds, opacity)
        if not 2 <= steps <= _MAX_STEPS:
            raise ValueError(f"Linear gradient steps must be between 2 and {_MAX_STEPS}.")

        coverage_start, coverage_end = self._coverage_range()
        boundaries = {
            coverage_start + (coverage_end - coverage_start) * index / steps
            for index in range(steps + 1)
        }
        boundaries.update(
            stop.offset
            for stop in self.stops
            if coverage_start < stop.offset < coverage_end
        )
        ordered = sorted(boundaries)

        group = _gradient_group(key, bounds, opacity, z_index)
        for lower, upper in zip(ordered, ordered[1:], strict=False):
            if upper - lower <= _EPSILON:
                continue
            polygon = self._band_polygon(lower, upper)
            if len(polygon) < 3 or abs(_polygon_area(polygon)) <= _EPSILON:
                continue
            local_points = tuple(
                Point(point.x * bounds.width, point.y * bounds.height) for point in polygon
            )
            group.add(
                SceneNode(
                    key=key,
                    kind=SceneNodeKind.PATH,
                    bounds=bounds,
                    fill=self.color_at((lower + upper) * 0.5),
                    path=Path2D(local_points),
                )
            )
        if not group.children:
            raise RuntimeError("Linear gradient tessellation produced no drawable bands.")
        return group

    def _parameter(self, point: Point) -> float:
        dx = self.end.x - self.start.x
        dy = self.end.y - self.start.y
        denominator = dx * dx + dy * dy
        return ((point.x - self.start.x) * dx + (point.y - self.start.y) * dy) / denominator

    def _coverage_range(self) -> tuple[float, float]:
        parameters = [self._parameter(point) for point in _UNIT_RECTANGLE]
        return min(parameters), max(parameters)

    def _band_polygon(self, lower: float, upper: float) -> tuple[Point, ...]:
        polygon = _clip_projection_half_plane(
            _UNIT_RECTANGLE,
            self._parameter,
            lower,
            keep_greater=True,
        )
        polygon = _clip_projection_half_plane(
            polygon,
            self._parameter,
            upper,
            keep_greater=False,
        )
        return _deduplicate_polygon(polygon)


@dataclass(frozen=True, slots=True)
class RadialGradient:
    """Immutable multi-stop radial gradient using normalized elliptical geometry.

    The gradient is circular in normalized coordinates. Mapping normalized x/y to
    arbitrary rectangular bounds naturally produces an ellipse, which matches
    object-bounding-box gradient semantics without adding backend-specific state.
    ``radius`` is measured in normalized units from ``center``.
    """

    center: Point
    radius: float
    stops: tuple[GradientStop, ...]

    def __post_init__(self) -> None:
        if any(not math.isfinite(value) for value in (self.center.x, self.center.y)):
            raise ValueError("Radial gradient centers must use finite coordinates.")
        if not math.isfinite(self.radius) or self.radius <= 0.0:
            raise ValueError("Radial gradient radius must be a finite value greater than zero.")
        _validate_stops(self.stops)

    @classmethod
    def two_color(
        cls,
        center_color: Color,
        edge_color: Color,
        *,
        center: Point | None = None,
        radius: float = math.sqrt(0.5),
    ) -> RadialGradient:
        """Create a two-color radial gradient that reaches default box corners."""

        return cls(
            center=Point(0.5, 0.5) if center is None else center,
            radius=radius,
            stops=(GradientStop(0.0, center_color), GradientStop(1.0, edge_color)),
        )

    def color_at(self, offset: float) -> Color:
        """Sample normalized distance from the gradient center."""

        return _color_at_stops(self.stops, offset)

    def to_scene_node(
        self,
        key: str,
        bounds: Rect,
        *,
        steps: int = _DEFAULT_RADIAL_STEPS,
        segments: int = _DEFAULT_RADIAL_SEGMENTS,
        opacity: float = 1.0,
        z_index: int = 0,
    ) -> SceneNode:
        """Build a clipped retained subtree of nested GPU-filled convex disks.

        An edge-color rectangle establishes clamped color outside the nominal
        radius. Disks are then submitted largest-to-smallest so each inner disk
        covers the center of the previous one, approximating annular color bands
        without requiring polygon holes or a dedicated effect shader. Geometry is
        immutable after construction and is therefore tessellated only once.
        """

        _validate_visual_arguments(key, bounds, opacity)
        if not 2 <= steps <= _MAX_STEPS:
            raise ValueError(f"Radial gradient steps must be between 2 and {_MAX_STEPS}.")
        if not 12 <= segments <= _MAX_RADIAL_SEGMENTS:
            raise ValueError(
                "Radial gradient segments must be between "
                f"12 and {_MAX_RADIAL_SEGMENTS}."
            )

        group = _gradient_group(key, bounds, opacity, z_index)
        group.add(
            SceneNode(
                key=key,
                kind=SceneNodeKind.RECTANGLE,
                bounds=bounds,
                fill=self.color_at(1.0),
            )
        )
        half_step = 0.5 / steps
        for step in range(steps, 0, -1):
            normalized_radius = step / steps
            points = self._disk_points(bounds, normalized_radius, segments)
            group.add(
                SceneNode(
                    key=key,
                    kind=SceneNodeKind.PATH,
                    bounds=bounds,
                    fill=self.color_at(max(0.0, normalized_radius - half_step)),
                    path=Path2D(points),
                )
            )
        return group

    def _disk_points(
        self,
        bounds: Rect,
        normalized_radius: float,
        segments: int,
    ) -> tuple[Point, ...]:
        radius = self.radius * normalized_radius
        return tuple(
            Point(
                (self.center.x + math.cos(math.tau * index / segments) * radius)
                * bounds.width,
                (self.center.y + math.sin(math.tau * index / segments) * radius)
                * bounds.height,
            )
            for index in range(segments)
        )


def _validate_stops(stops: tuple[GradientStop, ...]) -> None:
    if len(stops) < 2:
        raise ValueError("Gradients require at least two color stops.")
    if any(
        current.offset <= previous.offset
        for previous, current in zip(stops, stops[1:], strict=False)
    ):
        raise ValueError("Gradient stop offsets must be strictly increasing.")


def _validate_visual_arguments(key: str, bounds: Rect, opacity: float) -> None:
    if not key:
        raise ValueError("Gradient scene keys cannot be empty.")
    if bounds.width <= 0.0 or bounds.height <= 0.0:
        raise ValueError("Gradient bounds must have positive dimensions.")
    if not 0.0 <= opacity <= 1.0:
        raise ValueError("Gradient opacity must be between 0.0 and 1.0.")


def _gradient_group(key: str, bounds: Rect, opacity: float, z_index: int) -> SceneNode:
    return SceneNode(
        key=key,
        kind=SceneNodeKind.GROUP,
        bounds=bounds,
        opacity=opacity,
        z_index=z_index,
        clip_to_bounds=True,
    )


def _color_at_stops(stops: tuple[GradientStop, ...], offset: float) -> Color:
    if not math.isfinite(offset):
        raise ValueError("Gradient sample offsets must be finite.")
    if offset <= stops[0].offset:
        return stops[0].color
    if offset >= stops[-1].offset:
        return stops[-1].color

    for left, right in zip(stops, stops[1:], strict=False):
        if offset > right.offset:
            continue
        span = right.offset - left.offset
        position = (offset - left.offset) / span
        return _mix_color(left.color, right.color, position)
    return stops[-1].color


def _mix_color(left: Color, right: Color, position: float) -> Color:
    position = min(max(position, 0.0), 1.0)
    inverse = 1.0 - position
    return Color(
        left.r * inverse + right.r * position,
        left.g * inverse + right.g * position,
        left.b * inverse + right.b * position,
        left.a * inverse + right.a * position,
    )


def _clip_projection_half_plane(
    polygon: tuple[Point, ...],
    parameter: Callable[[Point], float],
    threshold: float,
    *,
    keep_greater: bool,
) -> tuple[Point, ...]:
    if not polygon:
        return ()

    result: list[Point] = []
    previous = polygon[-1]
    previous_value = parameter(previous)
    previous_inside = _inside_projection(previous_value, threshold, keep_greater)

    for current in polygon:
        current_value = parameter(current)
        current_inside = _inside_projection(current_value, threshold, keep_greater)
        if current_inside != previous_inside:
            denominator = current_value - previous_value
            if abs(denominator) > _EPSILON:
                fraction = (threshold - previous_value) / denominator
                fraction = min(max(fraction, 0.0), 1.0)
                result.append(
                    Point(
                        previous.x + (current.x - previous.x) * fraction,
                        previous.y + (current.y - previous.y) * fraction,
                    )
                )
        if current_inside:
            result.append(current)
        previous = current
        previous_value = current_value
        previous_inside = current_inside

    return tuple(result)


def _inside_projection(value: float, threshold: float, keep_greater: bool) -> bool:
    if keep_greater:
        return value >= threshold - _EPSILON
    return value <= threshold + _EPSILON


def _deduplicate_polygon(points: tuple[Point, ...]) -> tuple[Point, ...]:
    if not points:
        return ()
    compact: list[Point] = []
    for point in points:
        if compact and _points_close(compact[-1], point):
            continue
        compact.append(point)
    if len(compact) >= 2 and _points_close(compact[0], compact[-1]):
        compact.pop()
    return tuple(compact)


def _points_close(left: Point, right: Point) -> bool:
    return math.isclose(left.x, right.x, abs_tol=_EPSILON) and math.isclose(
        left.y, right.y, abs_tol=_EPSILON
    )


def _polygon_area(points: tuple[Point, ...]) -> float:
    return 0.5 * sum(
        point.x * points[(index + 1) % len(points)].y
        - points[(index + 1) % len(points)].x * point.y
        for index, point in enumerate(points)
    )
