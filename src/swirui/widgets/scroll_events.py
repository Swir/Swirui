"""Shared routed pointer-scroll helpers for retained professional widgets."""

from __future__ import annotations

from swirui.core import Event
from swirui.platforms import PlatformEvent, PlatformEventKind

_SCROLL_EPSILON = 1e-9
_REMAINING_X = "remaining_scroll_delta_x"
_REMAINING_Y = "remaining_scroll_delta_y"


def routed_scroll_deltas(event: Event) -> tuple[float, float] | None:
    """Return the current unconsumed logical-DIP scroll delta for ``event``.

    The first retained consumer normalizes Shift+wheel to the horizontal axis.
    Later bubbling consumers read the residual written by earlier consumers, so
    nested scroll surfaces never apply the same wheel/trackpad motion twice.
    """

    platform_event = event.data.get("event")
    if (
        not isinstance(platform_event, PlatformEvent)
        or platform_event.kind is not PlatformEventKind.POINTER_SCROLL
    ):
        return None

    if _REMAINING_X in event.data and _REMAINING_Y in event.data:
        return (
            _normalize_delta(float(event.data[_REMAINING_X])),
            _normalize_delta(float(event.data[_REMAINING_Y])),
        )

    delta_x = float(platform_event.delta_x)
    delta_y = float(platform_event.delta_y)
    if platform_event.shift and delta_x == 0.0 and delta_y != 0.0:
        delta_x = delta_y
        delta_y = 0.0

    delta_x = _normalize_delta(delta_x)
    delta_y = _normalize_delta(delta_y)
    event.data["scroll_delta_x"] = delta_x
    event.data["scroll_delta_y"] = delta_y
    event.data[_REMAINING_X] = delta_x
    event.data[_REMAINING_Y] = delta_y
    return (delta_x, delta_y)


def update_scroll_residual(
    event: Event,
    *,
    delta_x: float,
    delta_y: float,
    consumed: bool,
) -> tuple[float, float]:
    """Publish the residual delta and stop bubbling only when it is exhausted."""

    remaining_x = _normalize_delta(float(delta_x))
    remaining_y = _normalize_delta(float(delta_y))
    event.data[_REMAINING_X] = remaining_x
    event.data[_REMAINING_Y] = remaining_y
    if consumed:
        event.prevent_default()
    if remaining_x == 0.0 and remaining_y == 0.0:
        event.stop_propagation()
    return (remaining_x, remaining_y)


def scroll_residual(event: Event) -> tuple[float, float] | None:
    """Read a residual already established by retained scroll routing."""

    if _REMAINING_X not in event.data or _REMAINING_Y not in event.data:
        return None
    return (
        _normalize_delta(float(event.data[_REMAINING_X])),
        _normalize_delta(float(event.data[_REMAINING_Y])),
    )


def _normalize_delta(value: float) -> float:
    return 0.0 if abs(value) <= _SCROLL_EPSILON else value
