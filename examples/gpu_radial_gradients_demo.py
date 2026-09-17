"""Show retained radial gradients flowing through SwirUI's native GPU shape batch."""

from swirui import App, Window
from swirui.rendering import (
    Color,
    GradientStop,
    Point,
    RadialGradient,
    Rect,
    Scene,
    SceneNode,
    SceneNodeKind,
)

WIDTH = 960
HEIGHT = 640


def build_scene() -> Scene:
    root = SceneNode(
        key="root",
        kind=SceneNodeKind.GROUP,
        bounds=Rect(0, 0, WIDTH, HEIGHT),
        fill=Color.from_hex("#070B14"),
    )

    hero = RadialGradient(
        center=Point(0.34, 0.38),
        radius=0.95,
        stops=(
            GradientStop(0.0, Color.from_hex("#E8FDFF")),
            GradientStop(0.22, Color.from_hex("#3BE8FF")),
            GradientStop(0.56, Color.from_hex("#3157E8")),
            GradientStop(1.0, Color.from_hex("#32136B")),
        ),
    )
    root.add(
        hero.to_scene_node(
            "hero-radial",
            Rect(90, 80, 780, 360),
            steps=72,
            segments=56,
        )
    )

    root.add(
        SceneNode(
            key="title",
            kind=SceneNodeKind.TEXT,
            bounds=Rect(140, 150, 690, 80),
            text="SwirUI Radial Gradient",
            fill=Color.from_hex("#FFFFFF"),
            font_size=44,
            z_index=2,
        ),
        SceneNode(
            key="subtitle",
            kind=SceneNodeKind.TEXT,
            bounds=Rect(142, 235, 660, 70),
            text="Retained SceneGraph · clipped ellipse · native wgpu paths",
            fill=Color.from_hex("#E9F9FF"),
            font_size=21,
            z_index=2,
        ),
    )

    glow = RadialGradient.two_color(
        Color.from_hex("#D8FCFF"),
        Color.from_hex("#101426"),
        center=Point(0.5, 0.5),
        radius=0.78,
    )
    root.add(glow.to_scene_node("footer-glow", Rect(260, 485, 440, 90), steps=48, segments=48))
    return Scene(WIDTH, HEIGHT, root)


def main() -> None:
    app = App("SwirUI GPU Radial Gradients")
    window = Window(title="SwirUI — GPU Radial Gradients", width=WIDTH, height=HEIGHT)
    window.set_scene(build_scene())
    app.add_window(window)
    app.run()


if __name__ == "__main__":
    main()
