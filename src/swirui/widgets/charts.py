"""Retained cartesian data-visualization widgets for SwirUI."""

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
