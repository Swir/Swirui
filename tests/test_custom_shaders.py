import math

import pytest

from swirui.rendering import CustomShaderEffect

VALID_SOURCE = """
fn swirui_effect(
    color: vec4<f32>,
    uv: vec2<f32>,
    params: vec4<f32>,
) -> vec4<f32> {
    let gain = 1.0 + params.x;
    let offset = distance(uv, vec2<f32>(0.5, 0.5));
    let vignette = clamp(1.0 - offset * params.y, 0.0, 1.0);
    return vec4<f32>(color.rgb * gain * vignette, color.a);
}
"""


def test_composes_owned_fullscreen_shader_contract() -> None:
    effect = CustomShaderEffect(VALID_SOURCE, label="vignette")
    source = effect.native_wgsl()

    assert "@group(0) @binding(0)" in source
    assert "var<uniform> swirui_effect_params" in source
    assert "@vertex\nfn vs_main" in source
    assert "@fragment\nfn fs_main" in source
    assert "return swirui_effect(color, input.uv, swirui_effect_params.values);" in source


def test_pipeline_key_is_source_stable_while_state_key_tracks_parameters() -> None:
    first = CustomShaderEffect(VALID_SOURCE, parameters=(0.1, 0.2, 0.3, 0.4))
    second = first.with_parameters(0.5, 0.6, 0.7, 0.8)

    assert first.pipeline_key == second.pipeline_key
    assert first.state_key != second.state_key
    assert second.native_parameters() == (0.5, 0.6, 0.7, 0.8)


def test_rejects_invalid_contract_and_unsafe_gpu_surface_area() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        CustomShaderEffect("fn helper() -> f32 { return 1.0; }")

    with pytest.raises(ValueError, match="accept"):
        CustomShaderEffect(
            "fn swirui_effect(color: vec4<f32>) -> vec4<f32> { return color; }"
        )

    with pytest.raises(ValueError, match="attributes"):
        CustomShaderEffect(
            VALID_SOURCE + "\n@group(1) @binding(0) var extra: texture_2d<f32>;"
        )

    with pytest.raises(ValueError, match="loops"):
        CustomShaderEffect(
            VALID_SOURCE.replace(
                "let gain = 1.0 + params.x;",
                "var gain = 1.0; for (var i = 0; i < 2; i += 1) { "
                "gain += params.x; }",
            )
        )


def test_rejects_invalid_parameters_label_and_source_budget() -> None:
    with pytest.raises(ValueError, match="finite"):
        CustomShaderEffect(VALID_SOURCE, parameters=(0.0, math.inf, 0.0, 0.0))

    with pytest.raises(ValueError, match="1-64"):
        CustomShaderEffect(VALID_SOURCE, label="bad/label")

    with pytest.raises(ValueError, match="32 KiB"):
        CustomShaderEffect(VALID_SOURCE + (" " * (32 * 1024)))

    effect = CustomShaderEffect(VALID_SOURCE)
    with pytest.raises(ValueError, match="exactly four"):
        effect.with_parameters(1.0, 2.0, 3.0)


def test_native_validation_uses_composed_shader() -> None:
    captured: list[str] = []

    class NativeModule:
        @staticmethod
        def validate_custom_shader_wgsl(source: str) -> None:
            captured.append(source)

    effect = CustomShaderEffect(VALID_SOURCE)
    effect.validate_native(NativeModule())

    assert captured == [effect.native_wgsl()]


def test_native_validation_requires_validator_capability() -> None:
    effect = CustomShaderEffect(VALID_SOURCE)
    with pytest.raises(RuntimeError, match="does not expose"):
        effect.validate_native(object())
