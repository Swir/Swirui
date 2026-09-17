"""Show retained mesh gradients flowing through SwirUI's native GPU path batch."""

from swirui import App, Window
from swirui.rendering import (
    Color,
    MeshGradient,
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
        fill=Color.from_hex("#060914"),
    )

    hero = MeshGradient(
        (
            (
                Color.from_hex("#00F0FF"),
                Color.from_hex("#2563EB"),
                Color.from_hex("#7C3AED"),
            ),
            (
                Color.from_hex("#0B132B"),
                Color.from_hex("#4F46E5"),
                Color.from_hex("#EC4899"),
            ),
            (
                Color.from_hex("#08111F"),
                Color.from_hex("#0EA5E9"),
                Color.from_hex("#8B5CF6"),
            ),
        )
    )
    root.add(hero.to_scene_node("hero-mesh", Rect(80, 70, 800, 390), subdivisions=10))

    root.add(
        SceneNode(
            key="title",
            kind=SceneNodeKind.TEXT,
            bounds=Rect(135, 145, 700, 80),
            text="SwirUI Mesh Gradient",
            fill=Color.from_hex("#FFFFFF"),
            font_size=46,
            z_index=2,
        ),
        SceneNode(
            key="subtitle",
            kind=SceneNodeKind.TEXT,
            bounds=Rect(138, 230, 690, 70),
            text="Color lattice · retained SceneGraph · native wgpu paths",
            fill=Color.from_hex("#E6F7FF"),
            font_size=21,
            z_index=2,
        ),
    )

    footer = MeshGradient.four_corner(
        Color.from_hex("#00E5FF"),
        Color.from_hex("#8B5CF6"),
        Color.from_hex("#0EA5E9"),
        Color.from_hex("#EC4899"),
    )
    root.add(footer.to_scene_node("footer-mesh", Rect(210, 505, 540, 70), subdivisions=12))
    return Scene(WIDTH, HEIGHT, root)


def main() -> None:
    app = App("SwirUI GPU Mesh Gradients")
    window = Window(title="SwirUI — GPU Mesh Gradients", width=WIDTH, height=HEIGHT)
    window.set_scene(build_scene())
    app.add_window(window)
    app.run()


if __name__ == "__main__":
    main()
