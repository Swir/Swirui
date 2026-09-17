"""Show retained drop shadows flowing through SwirUI's native GPU rectangle batch."""

from swirui import App, Window
from swirui.rendering import (
    Color,
    CornerRadius,
    DropShadow,
    Point,
    Rect,
    Scene,
    SceneNode,
    SceneNodeKind,
)

WIDTH = 980
HEIGHT = 660


def _card(
    root: SceneNode,
    *,
    key: str,
    bounds: Rect,
    fill: Color,
    title: str,
    shadow: DropShadow,
) -> None:
    radius = CornerRadius.uniform(26.0)
    root.add(
        shadow.to_scene_node(f"{key}-shadow", bounds, corner_radius=radius),
        SceneNode(
            key=key,
            kind=SceneNodeKind.RECTANGLE,
            bounds=bounds,
            fill=fill,
            corner_radius=radius,
        ),
        SceneNode(
            key=f"{key}-title",
            kind=SceneNodeKind.TEXT,
            bounds=Rect(bounds.x + 34.0, bounds.y + 38.0, bounds.width - 68.0, 56.0),
            text=title,
            fill=Color.from_hex("#F8FAFC"),
            font_size=29.0,
            z_index=2,
        ),
    )


def build_scene() -> Scene:
    root = SceneNode(
        key="root",
        kind=SceneNodeKind.GROUP,
        bounds=Rect(0.0, 0.0, WIDTH, HEIGHT),
        fill=Color.from_hex("#060914"),
    )
    root.add(
        SceneNode(
            key="heading",
            kind=SceneNodeKind.TEXT,
            bounds=Rect(82.0, 52.0, 810.0, 70.0),
            text="SwirUI Retained GPU Shadows",
            fill=Color.from_hex("#F8FAFC"),
            font_size=40.0,
            z_index=5,
        )
    )

    _card(
        root,
        key="blue-card",
        bounds=Rect(95.0, 180.0, 350.0, 250.0),
        fill=Color.from_hex("#101C46"),
        title="Soft depth",
        shadow=DropShadow(
            color=Color(0.0, 0.58, 1.0, 0.36),
            offset=Point(0.0, 18.0),
            blur_radius=34.0,
            spread=2.0,
            steps=16,
        ),
    )
    _card(
        root,
        key="violet-card",
        bounds=Rect(535.0, 180.0, 350.0, 250.0),
        fill=Color.from_hex("#24113F"),
        title="Neon depth",
        shadow=DropShadow(
            color=Color(0.65, 0.25, 1.0, 0.42),
            offset=Point(0.0, 14.0),
            blur_radius=38.0,
            spread=4.0,
            steps=18,
        ),
    )

    root.add(
        SceneNode(
            key="footer",
            kind=SceneNodeKind.TEXT,
            bounds=Rect(180.0, 525.0, 620.0, 55.0),
            text="Retained layers · rounded rectangles · native wgpu batch",
            fill=Color.from_hex("#9CCBFF"),
            font_size=20.0,
            z_index=5,
        )
    )
    return Scene(WIDTH, HEIGHT, root)


def main() -> None:
    app = App("SwirUI GPU Shadows")
    window = Window(title="SwirUI — Retained GPU Shadows", width=WIDTH, height=HEIGHT)
    window.set_scene(build_scene())
    app.add_window(window)
    app.run()


if __name__ == "__main__":
    main()
