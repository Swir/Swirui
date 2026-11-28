from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from swirui.media import ImageAsset, ImageFrame, MediaFormat, decode_image
from swirui.rendering import Point, Rect
from swirui.widgets.image import Image, ImageFit


def test_image_contain_preserves_aspect_ratio_and_centers_resource() -> None:
    widget = Image(
        "hero",
        pixel_width=100,
        pixel_height=100,
        bounds=Rect(0.0, 0.0, 200.0, 100.0),
        fit=ImageFit.CONTAIN,
    )

    node = widget.build_scene_node()

    assert len(node.children) == 1
    assert node.children[0].bounds == Rect(50.0, 0.0, 100.0, 100.0)
    assert node.children[0].resource_id == "hero"
    assert node.clip_to_bounds is False


def test_image_cover_clips_overflow() -> None:
    widget = Image(
        "cover",
        pixel_width=100,
        pixel_height=100,
        bounds=Rect(10.0, 20.0, 200.0, 100.0),
        fit=ImageFit.COVER,
    )

    node = widget.build_scene_node()

    assert node.children[0].bounds == Rect(10.0, -30.0, 200.0, 200.0)
    assert node.clip_to_bounds is True


@pytest.mark.parametrize(("fit", "expected"), [
    (ImageFit.COVER, Rect(-65, 20, 200, 100)),
    (ImageFit.CONTAIN, Rect(10, 32.5, 100, 50)),
    (ImageFit.NONE, Rect(-215, -5, 400, 200)),
    (ImageFit.FILL, Rect(10, 20, 100, 100)),
])
def test_image_position_aligns_the_fitted_resource_within_its_bounds(
    fit: ImageFit, expected: Rect
) -> None:
    image = Image("photo", pixel_width=400, pixel_height=200, bounds=Rect(10, 20, 100, 100),
                  fit=fit, image_position=Point(.75, .25))
    assert image.build_scene_node().children[0].bounds == expected
    assert image.bounds == Rect(10, 20, 100, 100)


def test_image_position_is_live_and_keeps_the_last_valid_crop() -> None:
    image = Image("portrait", pixel_width=80, pixel_height=160, bounds=Rect(5, 15, 80, 80),
                  fit=ImageFit.COVER)
    assert image.image_position == Point(.5, .5)
    changes = []
    image.on("invalidated", lambda e: changes.append(e.data["reason"]))
    image.image_position = Point(0, 1)
    image.image_position = Point(0, 1)
    for invalid in (Point(-.01, .5), Point(1, 1.1), Point(float("nan"), 0), Point(0, float("inf"))):
        with pytest.raises(ValueError):
            image.image_position = invalid
    with pytest.raises(TypeError):
        image.image_position = (0, 1)
    assert changes == ["image_position"]
    assert image.image_position == Point(0, 1)
    assert image.build_scene_node().children[0].bounds == Rect(5, -65, 80, 160)


def test_animated_asset_obeys_gif_loop_timing() -> None:
    first = ImageFrame(1, 1, bytes((255, 0, 0, 255)), duration_ms=50)
    second = ImageFrame(1, 1, bytes((0, 0, 255, 255)), duration_ms=50)
    asset = ImageAsset(MediaFormat.GIF, (first, second), loop_count=1)

    assert asset.frame_at(0) is first
    assert asset.frame_at(75) is second
    assert asset.frame_at(125) is first
    assert asset.frame_at(250) is second


def test_register_all_uses_deterministic_frame_ids() -> None:
    calls: list[tuple[str, int, int, bytes]] = []

    class Renderer:
        def register_image_rgba(
            self,
            resource_id: str,
            width: int,
            height: int,
            rgba: bytes | bytearray | memoryview,
        ) -> None:
            calls.append((resource_id, width, height, bytes(rgba)))

    frames = (
        ImageFrame(1, 1, bytes((1, 2, 3, 255)), duration_ms=20),
        ImageFrame(1, 1, bytes((4, 5, 6, 255)), duration_ms=20),
    )
    asset = ImageAsset(MediaFormat.GIF, frames, loop_count=0)

    assert asset.register_all(Renderer(), "spinner") == ("spinner:0", "spinner:1")
    assert [call[0] for call in calls] == ["spinner:0", "spinner:1"]


def test_decode_svg_uses_native_rasterizer(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = SimpleNamespace(
        decode_svg_rgba=lambda data, width, height: (
            width or 2,
            height or 1,
            [255, 0, 0, 255] * ((width or 2) * (height or 1)),
        )
    )
    monkeypatch.setitem(sys.modules, "_swirui_native", fake)

    asset = decode_image(
        b'<svg xmlns="http://www.w3.org/2000/svg" width="2" height="1"/>',
        width=4,
        height=2,
    )

    assert asset.format is MediaFormat.SVG
    assert (asset.width, asset.height) == (4, 2)
    assert len(asset.frames[0].rgba) == 32


def test_frame_validates_rgba_payload_size() -> None:
    with pytest.raises(ValueError, match="exactly 16 bytes"):
        ImageFrame(2, 2, bytes((0, 0, 0, 0)))
