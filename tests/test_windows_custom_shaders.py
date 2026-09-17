import sys
import time

import pytest

from swirui import App, Window
from swirui.platforms.windows import Win32PlatformBackend
from swirui.rendering import (
    Color,
    ColorFilter,
    CustomShaderEffect,
    Rect,
    Scene,
    SceneNode,
    SceneNodeKind,
    WgpuRenderer,
)

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

SECOND_SOURCE = """
fn swirui_effect(
    color: vec4<f32>,
    uv: vec2<f32>,
    params: vec4<f32>,
) -> vec4<f32> {
    let scan = 0.82 + 0.18 * sin((uv.y * 36.0) + params.y);
    return vec4<f32>(color.rgb * scan, color.a);
}
"""


def _isolated_backend() -> Win32PlatformBackend:
    backend = Win32PlatformBackend()
    backend._class_name = f"SwirUI.CustomShaderSmoke.{id(backend):x}"
    return backend


def _scene() -> Scene:
    root = SceneNode(
        key="root",
        kind=SceneNodeKind.GROUP,
        bounds=Rect(0.0, 0.0, 640.0, 360.0),
    )
    root.add(
        SceneNode(
            key="cyan",
            kind=SceneNodeKind.RECTANGLE,
            bounds=Rect(70.0, 70.0, 220.0, 150.0),
            fill=Color(0.0, 0.72, 1.0, 1.0),
        ),
        SceneNode(
            key="violet",
            kind=SceneNodeKind.RECTANGLE,
            bounds=Rect(350.0, 105.0, 190.0, 130.0),
            fill=Color(0.55, 0.18, 1.0, 0.9),
        ),
        SceneNode(
            key="label",
            kind=SceneNodeKind.TEXT,
            bounds=Rect(120.0, 270.0, 400.0, 54.0),
            text="SwirUI Custom WGSL",
            fill=Color(1.0, 1.0, 1.0, 1.0),
            font_size=26.0,
        ),
    )
    return Scene(640.0, 360.0, root)


def test_maturin_extension_validates_composed_custom_shader() -> None:
    native = pytest.importorskip("_swirui_native")
    effect = CustomShaderEffect(
        VALID_SOURCE,
        parameters=(1.2, 0.0, 0.0, 0.0),
        label="edge-swap",
    )

    effect.validate_native(native)

    with pytest.raises(ValueError):
        native.validate_custom_shader_wgsl("@fragment fn fs_main( {")


def test_custom_shader_runs_in_real_persistent_wgpu_postprocess_chain() -> None:
    initial = CustomShaderEffect(
        VALID_SOURCE,
        parameters=(1.2, 0.0, 0.0, 0.0),
        label="edge-swap",
    )
    renderer = WgpuRenderer(
        scene_blur_radius=2.0,
        color_filter=ColorFilter.saturation(1.08),
        custom_shader=initial,
    )
    app = App(
        "SwirUI Custom Shader Integration",
        platform_backend=_isolated_backend(),
        renderer=renderer,
    )
    window = Window(title="SwirUI GPU Custom Shader Smoke", width=640, height=360)
    window.set_scene(_scene())
    app.add_window(window)

    try:
        app.start()
        assert renderer.frames_rendered == 1
        assert renderer.persistent_context_count == 1
        native_handle = window.native_handle
        assert native_handle is not None
        context = renderer._contexts[native_handle.value]
        assert context.custom_shader_enabled is True
        assert context.custom_shader_target_size == window.pixel_size
        assert context.custom_shader_generation == 1
        assert context.custom_shader_pipeline_generation == 1
        assert context.color_filter_enabled is True
        assert context.blur_target_size == window.pixel_size
        first_context = context
        first_target_generation = context.custom_shader_generation
        first_pipeline_generation = context.custom_shader_pipeline_generation

        renderer.set_custom_shader(initial.with_parameters(0.4, 0.0, 0.0, 0.0))
        app.invalidate(window)
        assert app.render_pending(time.monotonic() + 1.0) == 1
        assert renderer._contexts[native_handle.value] is first_context
        assert context.custom_shader_generation == first_target_generation
        assert context.custom_shader_pipeline_generation == first_pipeline_generation

        replacement = CustomShaderEffect(
            SECOND_SOURCE,
            parameters=(0.0, 1.1, 0.0, 0.0),
            label="scanline",
        )
        renderer.set_custom_shader(replacement)
        app.invalidate(window)
        assert app.render_pending(time.monotonic() + 1.0) == 1
        assert context.custom_shader_generation == first_target_generation
        assert context.custom_shader_pipeline_generation == first_pipeline_generation + 1

        renderer.set_custom_shader(None)
        app.invalidate(window)
        assert app.render_pending(time.monotonic() + 1.0) == 1
        assert context.custom_shader_enabled is False
        assert context.custom_shader_target_size == window.pixel_size
        assert context.custom_shader_generation == first_target_generation
    finally:
        app.stop()
