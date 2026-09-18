"""Backend-neutral intrinsic text measurement for retained widgets.

The native renderer remains responsible for final glyph shaping. Layout needs a
fast deterministic desired-size estimate before a renderer surface exists, so
this module provides a conservative Unicode-aware measurement model in logical
DIPs. It intentionally avoids platform font APIs and external dependencies.
"""

from __future__ import annotations

import math
import unicodedata

from swirui.rendering.geometry import Size


def measure_text_block(
    text: str,
    *,
    font_size: float,
    available_width: float | None = None,
    line_height_factor: float = 1.25,
    wrap: bool = True,
) -> Size:
    """Estimate the natural logical-DIP size of a text block.

    Explicit newlines are preserved. When ``available_width`` is finite and
    wrapping is enabled, lines wrap at Unicode scalar boundaries. The renderer
    still performs authoritative shaping with glyphon/cosmic-text; this estimate
    is only the pre-render layout contract used by ``measure()``.
    """

    size = float(font_size)
    if not math.isfinite(size) or size <= 0.0:
        raise ValueError("font_size must be finite and greater than zero.")

    factor = float(line_height_factor)
    if not math.isfinite(factor) or factor <= 0.0:
        raise ValueError("line_height_factor must be finite and greater than zero.")

    width_limit = _normalize_width_limit(available_width) if wrap else None
    normalized = str(text).replace("\r\n", "\n").replace("\r", "\n")
    widths = [0.0]

    for char in normalized:
        if char == "\n":
            widths.append(0.0)
            continue

        advance = _glyph_advance(char, size)
        current = widths[-1]
        if width_limit is not None and current > 0.0 and current + advance > width_limit:
            widths.append(min(advance, width_limit))
        else:
            widths[-1] = current + advance
            if width_limit is not None:
                widths[-1] = min(widths[-1], width_limit)

    width = max(widths, default=0.0)
    if width_limit is not None:
        width = min(width, width_limit)
    line_height = size * factor
    return Size(width, line_height * max(1, len(widths)))


def _normalize_width_limit(value: float | None) -> float | None:
    if value is None:
        return None
    normalized = float(value)
    if math.isnan(normalized) or normalized < 0.0:
        raise ValueError("available_width must be non-negative and not NaN.")
    if math.isinf(normalized):
        return None
    return normalized


def _glyph_advance(char: str, font_size: float) -> float:
    if char == "\t":
        return font_size * 1.32
    if char.isspace():
        return font_size * 0.33
    if unicodedata.combining(char):
        return 0.0

    category = unicodedata.category(char)
    if category in {"Cf", "Cc"}:
        return 0.0
    if unicodedata.east_asian_width(char) in {"W", "F"}:
        return font_size
    if category.startswith("S"):
        return font_size
    if category.startswith("P"):
        return font_size * 0.45
    if char in "ilI|!.,'`":
        return font_size * 0.32
    if char in "mwMW@#%&":
        return font_size * 0.82
    return font_size * 0.58
