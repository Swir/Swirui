import sys
import time

import pytest

from swirui import (
    AnimationController,
    AnimationParallel,
    App,
    BackdropBlurTransition,
    GlowTransition,
    Window,
    linear,
)
from swirui.platforms.windows import Win32PlatformBackend
from swirui.rendering import (
    BackdropBlur,
    Color,
    CornerRadius,
    Glow,
    Rect,
    Scene,
    SceneNode,
    SceneNodeKind,
    WgpuRenderer,
)


def _isolated_backend() -> Win32PlatformBackend:
    backend = Win32PlatformBackend()
    backend._class_name = f"SwirUI.EffectAnimation.{id(backend):x}"
    return backend


def _scene(glow: Glow, blur: BackdropBlur) -> Scene:
    root = SceneNode(
        key="root",
        kind=SceneNodeKind.GROUP,
        bounds=Rect(0.0, 0.0, 640.0, 360.0),
        hit_testable=False,
    )
    panel_bounds = Rect(150.0, 95.0, 340.0, 170.0)
    root.add(
        SceneNode(
            key="background",
            kind=SceneNodeKind.RECTANGLE,
            bounds=Rect(0.0, 0.0, 640.0, 360.0),
            fill=Color.from_hex("#07111C"),
            hit_testable=False,
        )
    )
    blur_node = blur.to_scene_node("animated-blur", panel_bounds, z_index=1)
    blur_node.add(
        SceneNode(
            key="glass-tint",
            kind=SceneNodeKind.RECTANGLE,
            bounds=panel_bounds,
            fill=Color(0.03, 0.13, 0.24, 0.62),
            corner_radius=blur.corner_radius,
            hit_testable=False,
        )
    )
    root.add(
        blur_node,
        glow.to_scene_node(
            "animated-glow",
            panel_bounds,
            corner_radius=blur.corner_radius,
            z_index=2,
        ),
        SceneNode(
            key="panel",
            kind=SceneNodeKind.RECTANGLE,
            bounds=panel_bounds,
            fill=Color(0.05, 0.12, 0.22, 0.82),
            corner_radius=blur.corner_radius,
            z_index=3,
        ),
    )
    return Scene(640.0, 360.0, root)


def _render_after_invalidation(
    app: App,
    renderer: WgpuRenderer,
    previous_frames: int,
    *,
    timeout: float = 1.0,
) -> None:
    deadline = time.monotonic() + timeout
    while renderer.frames_rendered <= previous_frames:
        app.process_events()
        app.render_pending(time.monotonic() + 1.0)
        if time.monotonic() >= deadline:
            pytest.fail("Timed out waiting for the animated Win32 GPU frame.")
        time.sleep(0.005)


@pytest.mark.skipif(sys.platform != "win32", reason="effect animation smoke requires Windows")
def test_blur_and_glow_transitions_reuse_real_persistent_wgpu_context() -> None:
    renderer = WgpuRenderer()
    app = App(
        "SwirUI effect animation smoke",
        platform_backend=_isolated_backend(),
        renderer=renderer,
    )
    window = Window(title="SwirUI blur and glow transition", width=640, height=360)
    source_glow = Glow(
        color=Color(0.0, 0.45, 1.0, 0.16),
        blur_radius=8.0,
        spread=0.0,
        steps=8,
    )
    target_glow = Glow(
        color=Color(0.15, 0.88, 1.0, 0.48),
        blur_radius=28.0,
        spread=4.0,
        steps=8,
    )
    source_blur = BackdropBlur(radius=6.0, corner_radius=CornerRadius.uniform(12.0))
    target_blur = BackdropBlur(radius=30.0, corner_radius=CornerRadius.uniform(28.0))
    glow_state = [source_glow]
    blur_state = [source_blur]
    window.set_scene(_scene(source_glow, source_blur))
    app.add_window(window)
    controller = AnimationController(app, window)

    def refresh() -> None:
        window.set_scene(_scene(glow_state[0], blur_state[0]))
        app.invalidate(window)

    def update_glow(value: Glow) -> None:
        glow_state[0] = value
        refresh()

    def update_blur(value: BackdropBlur) -> None:
        blur_state[0] = value
        refresh()

    try:
        app.start()
        assert window.native_handle is not None
        assert renderer.frames_rendered >= 1
        assert renderer.persistent_context_count == 1
        handle = window.native_handle.value
        initial_context = renderer._contexts[handle]

        controller.play(
            AnimationParallel(
                GlowTransition(source_glow, target_glow, 0.5, update_glow, easing=linear),
                BackdropBlurTransition(
                    source_blur,
                    target_blur,
                    0.5,
                    update_blur,
                    easing=linear,
                ),
            )
        )
        controller.tick(0.25)
        assert glow_state[0].blur_radius == pytest.approx(18.0)
        assert glow_state[0].spread == pytest.approx(2.0)
        assert blur_state[0].radius == pytest.approx(18.0)
        assert blur_state[0].corner_radius == CornerRadius.uniform(20.0)

        previous_frames = renderer.frames_rendered
        _render_after_invalidation(app, renderer, previous_frames)
        assert renderer.persistent_context_count == 1
        assert renderer._contexts[handle] is initial_context
        assert window.scene is not None
        blur_node = next(node for node in window.scene.walk() if node.key == "animated-blur")
        assert blur_node.blur_radius == pytest.approx(blur_state[0].radius)
        assert source_blur.radius <= blur_node.blur_radius <= target_blur.radius
        assert any(node.key.startswith("animated-glow:layer:") for node in window.scene.walk())

        controller.tick(0.25)
        assert glow_state[0] == target_glow
        assert blur_state[0] == target_blur
        previous_frames = renderer.frames_rendered
        _render_after_invalidation(app, renderer, previous_frames)
        assert renderer.persistent_context_count == 1
        assert renderer._contexts[handle] is initial_context
    finally:
        controller.dispose()
        app.stop()
