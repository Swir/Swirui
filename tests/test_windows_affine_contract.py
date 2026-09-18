from __future__ import annotations

import importlib
import math
import sys

import pytest

from swirui.rendering import Point
from swirui.rendering.affine import Affine2D
from swirui.rendering.native_affine import pack_affine_transform


@pytest.mark.skipif(sys.platform != "win32", reason="Native affine bridge test requires Windows")
def test_native_affine_validator_accepts_python_payload_order() -> None:
    native = importlib.import_module("_swirui_native")
    transform = Affine2D.rotation(
        math.radians(31.0),
        origin=Point(120.0, 84.0),
    ).then(Affine2D.translation(18.0, -7.0))

    assert native.validate_affine_transform(pack_affine_transform(transform)) is None


@pytest.mark.skipif(sys.platform != "win32", reason="Native affine bridge test requires Windows")
def test_native_affine_validator_rejects_invalid_payloads() -> None:
    native = importlib.import_module("_swirui_native")

    with pytest.raises(ValueError, match="exactly six floats"):
        native.validate_affine_transform((1.0, 0.0, 0.0, 1.0, 0.0))
    with pytest.raises(ValueError, match="finite"):
        native.validate_affine_transform((1.0, 0.0, 0.0, math.inf, 0.0, 0.0))
    with pytest.raises(ValueError, match="invertible"):
        native.validate_affine_transform((1.0, 2.0, 2.0, 4.0, 0.0, 0.0))
