from __future__ import annotations

import sys
import types

import pytest

from swirui.media import decode_lottie
from swirui.rendering import Rect
from swirui.widgets.lottie import Lottie


LOTTIE = b'{"v":"5.7.4","fr":30,"ip":0,"op":30,"w":20,"h":10,"layers":[{"ty":1}]}'


class Renderer:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int, int, bytes]] = []

    def register_image_rgba(
        self,
        resource_id: str,
        width: int,
        height: int,
        rgba: bytes | bytearray | memoryview,
    ) -> None:
        self.calls.append((resource_id, width, height, bytes(rgba)))


def fake_native() -> types.SimpleNamespace:
    def render(
        data: bytes,
        frame: float,
        width: int | None,
        height: int | None,
    ) -> tuple[int, int, bytes]:
        _ = data
        target_width = width or 20
        target_height = height or 10
        shade = int(frame) % 255
        rgba = bytes((shade, 0, 0, 255)) * (target_width * target_height)
        return target_width, target_height, rgba

    return types.SimpleNamespace(
        parse_lottie_metadata=lambda data: (20, 10, 30.0, 0.0, 30.0, 1),
        render_lottie_frame_rgba=render,
    )


def test_lottie_timing_loops_and_clamps(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "_swirui_native", fake_native())
    composition = decode_lottie(LOTTIE)

    assert composition.duration_ms == pytest.approx(1000.0)
    assert composition.frame_for_elapsed(500.0) == pytest.approx(15.0)
    assert composition.frame_for_elapsed(1500.0) == pytest.approx(15.0)
    assert composition.frame_for_elapsed(1500.0, loop=False) < 30.0


def test_lottie_widget_registers_and_rebinds_frames(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "_swirui_native", fake_native())
    composition = decode_lottie(LOTTIE)
    renderer = Renderer()
    widget = Lottie(
        composition,
        renderer,
        "demo:lottie",
        bounds=Rect(0.0, 0.0, 200.0, 100.0),
        render_width=40,
        render_height=20,
    )

    assert widget.pixel_size == (40, 20)
    assert renderer.calls[0][0] == "demo:lottie"
    widget.tick(500.0)
    assert widget.elapsed_ms == pytest.approx(500.0)
    assert len(renderer.calls) == 2
    assert renderer.calls[-1][3] != renderer.calls[0][3]

    widget.pause().tick(250.0)
    assert widget.elapsed_ms == pytest.approx(500.0)
    assert len(renderer.calls) == 2
    widget.play().seek(750.0)
    assert widget.elapsed_ms == pytest.approx(750.0)
    assert len(renderer.calls) == 3


def test_lottie_rejects_invalid_elapsed_time(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "_swirui_native", fake_native())
    composition = decode_lottie(LOTTIE)

    with pytest.raises(ValueError, match="non-negative"):
        composition.frame_for_elapsed(-1.0)
