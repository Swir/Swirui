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


@lru_cache(maxsize=12)
def _weave(width: float, height: float) -> tuple[Path2D, ...]:
    # Each thread is an x-monotone band. Neighbouring sinusoids change phase
    # across the fabric, so the folds cross without self-intersecting paths.
    paths = []
    for strand in range(28):
        v = strand / 27
        edge = []
        lower_edge = []
        for column in range(33):
            u = column / 32
            phase = u * math.tau * .96 + v * 2.6
            y = .49 + .23 * math.sin(phase) + .15 * math.sin(phase * 1.7 - 1.2) + .17 * (v - .5)
            envelope = .05 + .95 * math.sin(math.pi * u) ** .75
            y = .54 + envelope * (y - .54) - .18 * (u - .5)
            thickness = (.007 + .018 * math.sin(math.pi * u) ** 2) * envelope
            edge.append(Point(width * u, height * y))
            lower_edge.append(Point(width * u, height * (y + thickness)))
        paths.append(Path2D.horizontal_band(tuple(edge), tuple(lower_edge)))
    return tuple(paths)


class SilkRibbon(Widget):
    """Decorative folded strands, colored by the inherited theme. No animation timer."""

    def build_scene_node(self) -> SceneNode:
        bounds = self.bounds
        node = SceneNode(self.key, SceneNodeKind.GROUP, bounds, opacity=self.opacity,
                         z_index=self.z_index, hit_testable=False)
        if min(bounds.width, bounds.height) < 1:
            return node
        theme = self.effective_theme or FUTURE_DARK
        accent = theme.surface_color("accent")
        shadow = _mix(theme.surface_color("raised"), accent, .11)
        glint = _mix(accent, Color(1, 1, 1), .58)
        paths = _weave(bounds.width, bounds.height)
        for index, path in enumerate(paths):
            v = index / (len(paths) - 1)
            color = _mix(shadow, accent, math.sin(math.pi * v) ** 2)
            color = _mix(color, glint, math.exp(-((v - .72) / .13) ** 2))
            node.children.append(SceneNode(f"{self.key}:thread:{index}", SceneNodeKind.PATH,
                                           bounds, path=path, fill=color, hit_testable=False))
        return node
