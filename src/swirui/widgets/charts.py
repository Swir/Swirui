"""Shared public data models for retained cartesian charts."""

from __future__ import annotations

import math
from collections.abc import Hashable, Sequence
from dataclasses import dataclass

from swirui.rendering import Color


@dataclass(frozen=True, slots=True)
class ChartPoint:
    """One stable labelled numeric sample."""

    key: Hashable
    label: str
    value: float

    def __post_init__(self) -> None:
        hash(self.key)
        label = self.label.strip()
        value = float(self.value)
        if not label:
            raise ValueError("ChartPoint label must not be empty.")
        if not math.isfinite(value):
            raise ValueError("ChartPoint value must be finite.")
        object.__setattr__(self, "label", label)
        object.__setattr__(self, "value", value)


@dataclass(frozen=True, slots=True)
class ChartSeries:
    """Stable named series with an optional explicit color."""

    key: Hashable
    name: str
    points: Sequence[ChartPoint]
    color: Color | None = None

    def __post_init__(self) -> None:
        hash(self.key)
        name = self.name.strip()
        points = tuple(self.points)
        if not name:
            raise ValueError("ChartSeries name must not be empty.")
        if not points:
            raise ValueError("ChartSeries requires at least one point.")
        keys: set[Hashable] = set()
        for point in points:
            if point.key in keys:
                raise ValueError(f"Duplicate chart point key: {point.key!r}")
            keys.add(point.key)
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "points", points)


@dataclass(frozen=True, slots=True)
class ChartSelection:
    """Stable public description of one selected cartesian chart sample."""

    series_key: Hashable
    point_key: Hashable
    series_index: int
    point_index: int
    label: str
    value: float

    def __post_init__(self) -> None:
        hash(self.series_key)
        hash(self.point_key)
        if self.series_index < 0 or self.point_index < 0:
            raise ValueError("Chart selection indices must be non-negative.")
        label = self.label.strip()
        value = float(self.value)
        if not label:
            raise ValueError("ChartSelection label must not be empty.")
        if not math.isfinite(value):
            raise ValueError("ChartSelection value must be finite.")
        object.__setattr__(self, "label", label)
        object.__setattr__(self, "value", value)


@dataclass(frozen=True, slots=True)
class ChartViewport:
    """Visible cartesian data window in point-index and value coordinates."""

    x_min: float
    x_max: float
    y_min: float
    y_max: float

    def __post_init__(self) -> None:
        values = tuple(float(value) for value in (self.x_min, self.x_max, self.y_min, self.y_max))
        if not all(math.isfinite(value) for value in values):
            raise ValueError("ChartViewport values must be finite.")
        x_min, x_max, y_min, y_max = values
        if x_min > x_max:
            raise ValueError("ChartViewport x_min must not exceed x_max.")
        if y_min >= y_max:
            raise ValueError("ChartViewport y_min must be smaller than y_max.")
        object.__setattr__(self, "x_min", x_min)
        object.__setattr__(self, "x_max", x_max)
        object.__setattr__(self, "y_min", y_min)
        object.__setattr__(self, "y_max", y_max)


__all__ = ["ChartPoint", "ChartSelection", "ChartSeries", "ChartViewport"]
