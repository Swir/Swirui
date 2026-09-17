import sys

import pytest

from swirui.rendering import CustomShaderEffect


pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="requires Windows native extension")


VALID_SOURCE = """
fn swirui_effect(
    color: vec4<f32>,
    uv: vec2<f32>,
    params: vec4<f32>,
) -> vec4<f32> {
    let centered = abs(uv - vec2<f32>(0.5, 0.5));
    let edge = clamp(max(centered.x, centered.y) * params.x, 0.0, 1.0);
    return vec4<f32>(mix(color.rgb, color.bgr, edge), color.a);
}
"""


def test_maturin_extension_validates_composed_custom_shader() -> None:
    native = pytest.importorskip("_swirui_native")
    effect = CustomShaderEffect(VALID_SOURCE, parameters=(1.2, 0.0, 0.0, 0.0), label="edge-swap")

    effect.validate_native(native)

    with pytest.raises(ValueError):
        native.validate_custom_shader_wgsl("@fragment fn fs_main( {")
