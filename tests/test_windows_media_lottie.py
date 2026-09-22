from __future__ import annotations

import sys

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="native Lottie gate is Windows-only")


LOTTIE_SOLID = br'''{
  "v":"5.7.4","fr":30,"ip":0,"op":30,"w":20,"h":10,
  "layers":[{
    "ty":1,"ip":0,"op":30,"sw":4,"sh":4,"sc":"#ff0000",
    "ks":{
      "p":{"a":1,"k":[{"t":0,"s":[2,2,0]},{"t":30,"s":[12,2,0]}]},
      "a":{"a":0,"k":[0,0,0]},
      "s":{"a":0,"k":[100,100,100]},
      "o":{"a":0,"k":100}
    }
  }]
}'''

LOTTIE_SHAPE = br'''{
  "v":"5.7.4","fr":60,"ip":0,"op":60,"w":16,"h":16,
  "layers":[{
    "ty":4,"ip":0,"op":60,
    "ks":{"p":{"k":[0,0]},"a":{"k":[0,0]},"s":{"k":[100,100]},"o":{"k":100}},
    "shapes":[
      {"ty":"rc","p":{"k":[8,8]},"s":{"k":[8,6]},"r":{"k":0}},
      {"ty":"fl","c":{"k":[0,0.5,1,1]},"o":{"k":100}},
      {"ty":"tr","p":{"k":[0,0]},"a":{"k":[0,0]},"s":{"k":[100,100]},"o":{"k":100}}
    ]
  }]
}'''


def alpha_at(rgba: bytes, width: int, x: int, y: int) -> int:
    return rgba[(y * width + x) * 4 + 3]


def test_native_lottie_metadata_motion_and_resize() -> None:
    import _swirui_native as native

    assert native.parse_lottie_metadata(LOTTIE_SOLID) == (20, 10, 30.0, 0.0, 30.0, 1)
    width, height, first = native.render_lottie_frame_rgba(LOTTIE_SOLID, 0.0, None, None)
    _, _, middle = native.render_lottie_frame_rgba(LOTTIE_SOLID, 15.0, None, None)
    assert (width, height) == (20, 10)
    assert alpha_at(first, width, 3, 3) == 255
    assert alpha_at(middle, width, 3, 3) == 0
    assert alpha_at(middle, width, 8, 3) == 255

    width, height, resized = native.render_lottie_frame_rgba(LOTTIE_SOLID, 15.0, 40, None)
    assert (width, height) == (40, 20)
    assert len(resized) == 40 * 20 * 4


def test_native_lottie_flat_shape_layer_rasterizes() -> None:
    import _swirui_native as native

    width, height, rgba = native.render_lottie_frame_rgba(LOTTIE_SHAPE, 0.0, None, None)
    assert (width, height) == (16, 16)
    assert alpha_at(rgba, width, 8, 8) == 255
    assert alpha_at(rgba, width, 1, 1) == 0
