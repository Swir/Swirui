"""Validate a bounded SwirUI custom shader effect before renderer integration."""

from __future__ import annotations

from swirui.rendering import CustomShaderEffect

EFFECT_SOURCE = """
fn swirui_effect(
    color: vec4<f32>,
    uv: vec2<f32>,
    params: vec4<f32>,
) -> vec4<f32> {
    let center = vec2<f32>(0.5, 0.5);
    let distance_from_center = distance(uv, center);
    let vignette = clamp(1.0 - distance_from_center * params.x, 0.0, 1.0);
    let boosted = color.rgb * (1.0 + params.y);
    return vec4<f32>(boosted * vignette, color.a);
}
"""


def main() -> None:
    effect = CustomShaderEffect(
        EFFECT_SOURCE,
        parameters=(0.9, 0.08, 0.0, 0.0),
        label="vignette-boost",
    )
    print("Pipeline key:", effect.pipeline_key)
    print("State key:", effect.state_key)
    print("Parameters:", effect.native_parameters())

    try:
        effect.validate_native()
    except RuntimeError as exc:
        print("Native validation unavailable:", exc)
        print("Build native/ with Maturin to run Naga validation.")
    else:
        print("Native Naga validation: OK")


if __name__ == "__main__":
    main()
