"""Internal packing contract for retained affine data crossing into the Rust core.

The public transform model remains :class:`swirui.rendering.affine.Affine2D`.
This module intentionally contains no rendering behavior; it gives the Python
renderer bridge one canonical six-float matrix order and exact clip-region
payload for the native compositor work that follows.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TypeAlias

from .affine import Affine2D
from .geometry import Rect
from .scene import ClipRegion

NativeAffineTransform: TypeAlias = tuple[float, float, float, float, float, float]
NativeAffineClip: TypeAlias = tuple[
    float,
    float,
    float,
    float,
    float,
    float,
    float,
    float,
    float,
    float,
]


def pack_affine_transform(transform: Affine2D) -> NativeAffineTransform:
    """Pack one transform in the exact order consumed by the Rust affine contract."""

    return (
        transform.m11,
        transform.m12,
        transform.m21,
        transform.m22,
        transform.tx,
        transform.ty,
    )


def pack_affine_clip(region: ClipRegion) -> NativeAffineClip:
    """Pack one exact transformed clip as matrix + authored rectangle geometry."""

    transform, bounds = region
    return (*pack_affine_transform(transform), *pack_rect(bounds))


def pack_affine_clips(regions: Iterable[ClipRegion]) -> tuple[NativeAffineClip, ...]:
    """Pack a clip chain without flattening rotated regions to axis-aligned bounds."""

    return tuple(pack_affine_clip(region) for region in regions)


def pack_rect(bounds: Rect) -> tuple[float, float, float, float]:
    """Pack authored rectangle geometry as x, y, width, height."""

    return bounds.x, bounds.y, bounds.width, bounds.height
