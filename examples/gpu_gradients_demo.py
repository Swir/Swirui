"""Run SwirUI's first Visual Engine linear-gradient scene on the native GPU path."""

from swirui import App, Window
from swirui.rendering import (
    Color,
    GradientStop,
    LinearGradient,
    Point,
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

    diagonal = LinearGradient(
        start=Point(-0.1, 0.05),
        end=Point(1.1, 0.95),
        stops=(
            GradientStop(0.0, Color.from_hex("#00D9FF")),
            GradientStop(0.42, Color.from_hex("#2563EB")),
            GradientStop(0.72, Color.from_hex("#7C3AED")),
            GradientStop(1.0, Color.from_hex("#EC4899")),
        ),
    )
    root.add(diagonal.to_scene_node("hero-gradient", Rect(80, 90, 800, 300), steps=128))

    root.add(
        SceneNode(
            key="title",
            kind=SceneNodeKind.TEXT,
            bounds=Rect(120, 150, 720, 80),
            text="SwirUI Visual Engine",
            fill=Color.from_hex("#FFFFFF"),
            font_size=46,
            z_index=2,
        ),
        SceneNode(
            key="subtitle",
            kind=SceneNodeKind.TEXT,
            bounds=Rect(122, 235, 700, 60),
            text="Linear gradients · retained SceneGraph · native GPU paths",
            fill=Color.from_hex("#E6F7FF"),
            font_size=22,
            z_index=2,
        ),
    )

    accent = LinearGradient.two_color(
        Color.from_hex("#00E5FF"),
        Color.from_hex("#8B5CF6"),
        start=Point(0.0, 0.5),
        end=Point(1.0, 0.5),
    )
    root.add(accent.to_scene_node("accent-gradient", Rect(180, 470, 600, 44), steps=96))
    return Scene(WIDTH, HEIGHT, root)


def main() -> None:
    app = App("SwirUI GPU Gradients")
    window = Window(title="SwirUI — GPU Linear Gradients", width=WIDTH, height=HEIGHT)
    window.set_scene(build_scene())
    app.add_window(window)
    app.run()


if __name__ == "__main__":
    main()
