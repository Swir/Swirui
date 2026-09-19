from __future__ import annotations

import sys

import pytest

from swirui.platforms import NativeWindowHandle, PlatformEventKind
from swirui.platforms.macos_scroll import (
    MacOSCocoaPlatformBackend,
    _normalize_scroll_deltas,
)


def test_cocoa_scroll_delta_conversion_preserves_precise_trackpad_motion() -> None:
    assert _normalize_scroll_deltas(3.25, -7.5, precise=True) == pytest.approx(
        (3.25, 7.5)
    )
    assert _normalize_scroll_deltas(0.0, 1.0, precise=False) == pytest.approx(
        (0.0, -48.0)
    )


@pytest.mark.parametrize("value", [float("inf"), float("-inf"), float("nan")])
def test_cocoa_scroll_delta_conversion_rejects_non_finite_native_values(value: float) -> None:
    assert _normalize_scroll_deltas(value, 1.0, precise=True) == (0.0, 0.0)
    assert _normalize_scroll_deltas(1.0, value, precise=True) == (0.0, 0.0)


@pytest.mark.skipif(sys.platform != "darwin", reason="Cocoa normalization test")
def test_cocoa_scroll_event_normalizes_precise_delta_and_modifiers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    handle = NativeWindowHandle(99)
    backend = object.__new__(MacOSCocoaPlatformBackend)
    backend._windows = {handle: object()}  # type: ignore[assignment]

    values: dict[str, object] = {
        "type": 22,
        "window": handle.value,
        "hasPreciseScrollingDeltas": True,
        "scrollingDeltaX": 2.5,
        "scrollingDeltaY": -6.75,
    }

    def fake_send(_receiver: int, selector: str, *_args: object) -> object:
        return values.get(selector, 0)

    monkeypatch.setattr(backend, "_send", fake_send)
    monkeypatch.setattr(backend, "_event_pointer_pixels", lambda _event, _window: (31.0, 47.0))
    monkeypatch.setattr(backend, "_modifiers", lambda _event: (True, False, True, False))

    normalized = backend._normalize_event(123)

    assert len(normalized) == 1
    event = normalized[0]
    assert event.kind is PlatformEventKind.POINTER_SCROLL
    assert event.window == handle
    assert (event.x, event.y) == pytest.approx((31.0, 47.0))
    assert (event.delta_x, event.delta_y) == pytest.approx((2.5, 6.75))
    assert event.shift is True
    assert event.ctrl is False
    assert event.alt is True
    assert event.meta is False
