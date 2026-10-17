"""Single-line editing geometry, with an explicit portable estimate fallback."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class TextLineLayout:
    width: float
    carets: tuple[float, ...]
    segments: tuple[tuple[int, int, float, float], ...]

    def hit_test(self, x: float) -> int:
        return min(range(len(self.carets)), key=lambda i: abs(self.carets[i] - x))

    def selection_spans(self, start: int, end: int) -> tuple[tuple[float, float], ...]:
        if start >= end:
            return ()
        spans = sorted(
            (left, right) for a, b, left, right in self.segments if a < end and b > start
        )
        merged: list[tuple[float, float]] = []
        for left, right in spans:
            if merged and left <= merged[-1][1] + 0.01:
                merged[-1] = (merged[-1][0], max(merged[-1][1], right))
            else:
                merged.append((left, right))
        return tuple(merged)


class TextShaper(Protocol):
    def shape_line(self, text: str, size: float, family: str, scale: float) -> TextLineLayout: ...


class NativeTextShaper:
    def __init__(self, native: Any, *, supports_color_spans: bool = False) -> None:
        self._native = native
        self.supports_color_spans = supports_color_spans

    def shape_line(self, text: str, size: float, family: str, scale: float) -> TextLineLayout:
        width, carets, segments = self._native.shape_line(text, size * scale, family)
        return TextLineLayout(
            width / scale,
            tuple(x / scale for x in carets),
            tuple((a, b, left / scale, right / scale) for a, b, left, right in segments),
        )


def estimated_line(text: str, size: float) -> TextLineLayout:
    """Deterministic fallback for headless/portable renderers without a font shaper."""
    advance = max(1.0, size * 0.58)
    carets = tuple(i * advance for i in range(len(text) + 1))
    return TextLineLayout(
        max(1.0, carets[-1] + 1.0),
        carets,
        tuple((i, i + 1, carets[i], carets[i + 1]) for i in range(len(text))),
    )
