import pytest

from swirui.rendering import CustomShaderEffect, WgpuRenderer

SOURCE_A = """
fn swirui_effect(
    color: vec4<f32>,
    uv: vec2<f32>,
    params: vec4<f32>,
) -> vec4<f32> {
    let gain = 1.0 + params.x;
    return vec4<f32>(color.rgb * gain, color.a);
}
"""

SOURCE_B = """
fn swirui_effect(
    color: vec4<f32>,
    uv: vec2<f32>,
    params: vec4<f32>,
) -> vec4<f32> {
    let pulse = 0.75 + 0.25 * params.y;
    return vec4<f32>(color.bgr * pulse, color.a);
}
"""


class FakeNative:
    def __init__(self) -> None:
        self.validated: list[str] = []

    def validate_custom_shader_wgsl(self, source: str) -> None:
        self.validated.append(source)


class FakeContext:
    def __init__(self, *, fail_source: str | None = None) -> None:
        self.fail_source = fail_source
        self.shader_source: str | None = None
        self.parameters: list[float] | None = None
        self.set_calls = 0
        self.clear_calls = 0

    def set_custom_shader(self, source: str, parameters: list[float]) -> None:
        if self.fail_source is not None and self.fail_source in source:
            raise RuntimeError("synthetic GPU pipeline failure")
        self.shader_source = source
        self.parameters = list(parameters)
        self.set_calls += 1

    def clear_custom_shader(self) -> None:
        self.shader_source = None
        self.parameters = None
        self.clear_calls += 1


def test_renderer_configures_and_clears_live_custom_shader_contexts() -> None:
    native = FakeNative()
    renderer = WgpuRenderer(native_module=native)
    first = FakeContext()
    second = FakeContext()
    renderer._contexts[1] = first
    renderer._contexts[2] = second

    effect = CustomShaderEffect(SOURCE_A, parameters=(0.2, 0.0, 0.0, 0.0))
    renderer.set_custom_shader(effect)

    assert renderer.custom_shader is effect
    assert native.validated == [effect.native_wgsl()]
    assert first.shader_source == effect.native_wgsl()
    assert second.shader_source == effect.native_wgsl()
    assert first.parameters == [0.2, 0.0, 0.0, 0.0]
    assert second.parameters == [0.2, 0.0, 0.0, 0.0]

    updated = effect.with_parameters(0.7, 0.1, 0.0, 0.0)
    renderer.set_custom_shader(updated)
    assert first.parameters == [0.7, 0.1, 0.0, 0.0]
    assert second.parameters == [0.7, 0.1, 0.0, 0.0]

    renderer.set_custom_shader(None)
    assert renderer.custom_shader is None
    assert first.shader_source is None
    assert second.shader_source is None
    assert first.clear_calls == 1
    assert second.clear_calls == 1


def test_renderer_rolls_back_already_updated_contexts_on_failure() -> None:
    native = FakeNative()
    renderer = WgpuRenderer(native_module=native)
    first = FakeContext()
    second = FakeContext(fail_source="color.bgr")
    renderer._contexts[1] = first
    renderer._contexts[2] = second

    stable = CustomShaderEffect(SOURCE_A, parameters=(0.1, 0.0, 0.0, 0.0))
    renderer.set_custom_shader(stable)
    replacement = CustomShaderEffect(SOURCE_B, parameters=(0.0, 0.8, 0.0, 0.0))

    with pytest.raises(RuntimeError, match="synthetic GPU pipeline failure"):
        renderer.set_custom_shader(replacement)

    assert renderer.custom_shader is stable
    assert first.shader_source == stable.native_wgsl()
    assert first.parameters == list(stable.native_parameters())
    assert second.shader_source == stable.native_wgsl()
    assert second.parameters == list(stable.native_parameters())


def test_renderer_requires_native_custom_shader_entrypoint() -> None:
    renderer = WgpuRenderer(native_module=FakeNative())
    renderer._contexts[1] = object()
    effect = CustomShaderEffect(SOURCE_A)

    with pytest.raises(RuntimeError, match="does not support custom shader effects"):
        renderer.set_custom_shader(effect)

    assert renderer.custom_shader is None
