"""A folded, palette-aware ribbon for decorative material previews."""

from __future__ import annotations

import math
from functools import lru_cache

from ..rendering import Color, Path2D, Point, SceneNode, SceneNodeKind
from ..theme import FUTURE_DARK
from .base import Widget


def _mix(a: Color, b: Color, weight: float) -> Color:
    return Color(a.r + (b.r - a.r) * weight, a.g + (b.g - a.g) * weight,
                 a.b + (b.b - a.b) * weight, a.a + (b.a - a.a) * weight)


_FACE_BANDS = 16


@lru_cache(maxsize=12)
def _weave(width: float, height: float) -> tuple[Path2D, ...]:
    # Two faces share a curved fold. Neighbouring bands reuse the exact edge so
    # the backdrop cannot leak through the weave at fractional display scales.
    edges: list[list[Point]] = [[] for _ in range(2 * _FACE_BANDS + 1)]
    for column in range(29):
        u = column / 28
        center = .51 + .25 * math.sin(math.tau * (u + .06)) - .11 * (u - .5)
        half_width = .012 + .20 * math.sin(math.pi * u) ** .72
        top, bottom = center - half_width, center + half_width
        fold = center + half_width * .89 * math.sin(math.tau * (u - .09))
        for row, edge in enumerate(edges):
            t = row / _FACE_BANDS
            y = top + t * (fold - top) if t <= 1 else fold + (t - 1) * (bottom - fold)
            edge.append(Point(width * u, height * y))
    rows = [tuple(edge) for edge in edges]
    return tuple(Path2D.horizontal_band(upper, lower)
                 for upper, lower in zip(rows[:-1], rows[1:], strict=True))


class SilkRibbon(Widget):
    """Folded satin with an accent-colored face and a shaded reverse."""

    def build_scene_node(self) -> SceneNode:
        bounds = self.bounds
        node = SceneNode(self.key, SceneNodeKind.GROUP, bounds, opacity=self.opacity,
                         z_index=self.z_index, hit_testable=False)
        if min(bounds.width, bounds.height) < 1:
            return node
        theme = self.effective_theme or FUTURE_DARK
        accent = theme.surface_color("accent")
        shadow = _mix(_mix(accent, Color(0, 0, 0), .72), theme.surface_color("raised"), .20)
        glint = _mix(accent, Color(1, 1, 1), .76)
        paths = _weave(bounds.width, bounds.height)
        for index, path in enumerate(paths):
            v = (index % _FACE_BANDS + .5) / _FACE_BANDS
            if index < _FACE_BANDS:
                color = _mix(shadow, accent, .95 - .60 * v)
                color = _mix(color, glint, math.exp(-((v - .27) / .23) ** 2))
            else:
                color = _mix(shadow, accent, .08 + .64 * v ** 1.6)
            node.children.append(SceneNode(f"{self.key}:thread:{index}", SceneNodeKind.PATH,
                                           bounds, path=path, fill=color, hit_testable=False))
        return node
