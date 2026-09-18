"""Animate retained blur and glow descriptors on the real SwirUI frame clock."""

from __future__ import annotations

from swirui import (
    AnimationController,
    AnimationParallel,
    App,
    BackdropBlurTransition,
    GlowTransition,
    Window,
)
from swirui.rendering import (
    BackdropBlur,
    Color,
    CornerRadius,
    Glow,
    Rect,
    Scene,
    SceneNode,
    SceneNodeKind,
)

app = App(name="SwirUI Effect Transition Demo")
window = app.add_window(Window(title="SwirUI blur + glow transition", width=760, height=460))
source_glow = Glow(
    color=Color(0.0, 0.45, 1.0, 0.12),
    blur_radius=8.0,
    steps=12,
)
target_glow = Glow(
    color=Color(0.2, 0.9, 1.0, 0.52),
    blur_radius=34.0,
    spread=5.0,
    steps=12,
)
source_blur = BackdropBlur(radius=6.0, corner_radius=CornerRadius.uniform(14.0))
target_blur = BackdropBlur(radius=32.0, corner_radius=CornerRadius.uniform(32.0))
glow_state = [source_glow]
blur_state = [source_blur]


def build_scene() -> Scene:
    root = SceneNode(
        key="root",
        kind=SceneNodeKind.GROUP,
        bounds=Rect(0.0, 0.0, 760.0, 460.0),
        hit_testable=False,
    )
    panel = Rect(160.0, 120.0, 440.0, 220.0)
    root.add(
        SceneNode(
            key="background",
            kind=SceneNodeKind.RECTANGLE,
            bounds=Rect(0.0, 0.0, 760.0, 460.0),
            fill=Color.from_hex("#07111C"),
            hit_testable=False,
        )
    )
    blur_node = blur_state[0].to_scene_node("demo-blur", panel, z_index=1)
    blur_node.add(
        SceneNode(
            key="glass-tint",
            kind=SceneNodeKind.RECTANGLE,
            bounds=panel,
            fill=Color(0.03, 0.14, 0.25, 0.60),
            corner_radius=blur_state[0].corner_radius,
            hit_testable=False,
        )
    )
    root.add(
        blur_node,
        glow_state[0].to_scene_node(
            "demo-glow",
            panel,
            corner_radius=blur_state[0].corner_radius,
            z_index=2,
        ),
        SceneNode(
            key="panel",
            kind=SceneNodeKind.RECTANGLE,
            bounds=panel,
            fill=Color(0.04, 0.12, 0.22, 0.82),
            corner_radius=blur_state[0].corner_radius,
            z_index=3,
        ),
        SceneNode(
            key="title",
            kind=SceneNodeKind.TEXT,
            bounds=Rect(220.0, 205.0, 320.0, 70.0),
            text="SwirUI Blur + Glow",
            fill=Color.from_hex("#F4FAFF"),
            font_size=30.0,
            z_index=4,
        ),
    )
    return Scene(760.0, 460.0, root)


def refresh() -> None:
    window.set_scene(build_scene())
    app.invalidate(window)


def update_glow(value: Glow) -> None:
    glow_state[0] = value
    refresh()


def update_blur(value: BackdropBlur) -> None:
    blur_state[0] = value
    refresh()


window.set_scene(build_scene())
controller = AnimationController(app, window)
controller.play(
    AnimationParallel(
        GlowTransition(source_glow, target_glow, 1.2, update_glow),
        BackdropBlurTransition(source_blur, target_blur, 1.2, update_blur),
    )
)

try:
    app.run()
finally:
    controller.dispose()
