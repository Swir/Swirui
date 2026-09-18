from __future__ import annotations

import math

from swirui.rendering import Point, Rect
from swirui.rendering.affine import Affine2D
from swirui.rendering.native_affine import (
    pack_affine_clip,
    pack_affine_clips,
    pack_affine_transform,
    pack_rect,
)


def test_pack_affine_transform_matches_native_six_float_order() -> None:
    transform = Affine2D.rotation(
        math.radians(30.0),
        origin=Point(80.0, 45.0),
    ).then(Affine2D.translation(13.0, -9.0))

    assert pack_affine_transform(transform) == (
        transform.m11,
        transform.m12,
        transform.m21,
        transform.m22,
        transform.tx,
        transform.ty,
    )


def test_pack_affine_clip_preserves_authored_bounds_and_exact_transform() -> None:
    transform = Affine2D.rotation(math.radians(17.0), origin=Point(120.0, 90.0))
    bounds = Rect(40.0, 30.0, 180.0, 120.0)

    payload = pack_affine_clip((transform, bounds))

    assert payload[:6] == pack_affine_transform(transform)
    assert payload[6:] == (40.0, 30.0, 180.0, 120.0)


def test_pack_affine_clips_keeps_clip_chain_order() -> None:
    outer = (Affine2D.translation(12.0, -4.0), Rect(0.0, 0.0, 400.0, 300.0))
    inner = (
        Affine2D.rotation(math.radians(-11.0), origin=Point(140.0, 110.0)),
        Rect(60.0, 50.0, 180.0, 120.0),
    )

    payload = pack_affine_clips((outer, inner))

    assert payload == (pack_affine_clip(outer), pack_affine_clip(inner))


def test_pack_rect_uses_xy_width_height_not_visual_bounds() -> None:
    bounds = Rect(20.0, 30.0, 140.0, 80.0)

    assert pack_rect(bounds) == (20.0, 30.0, 140.0, 80.0)
