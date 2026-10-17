from swirui import Window
from swirui.rendering import (
    BackdropBlur,
    Color,
    Path2D,
    Point,
    Rect,
    Scene,
    SceneNode,
    SceneNodeKind,
)
from swirui.rendering.ordered_wgpu_renderer import WgpuRenderer


def _scene() -> Scene:
    bounds = Rect(0, 0, 200, 120)
    root = SceneNode("root", SceneNodeKind.GROUP, bounds)
    root.add(
        SceneNode(
            "path",
            SceneNodeKind.PATH,
            bounds,
            fill=Color(1, 0, 0),
            path=Path2D((Point(0, 0), Point(200, 0), Point(0, 120))),
        ),
        SceneNode("rect", SceneNodeKind.RECTANGLE, Rect(20, 20, 40, 40), fill=Color(0, 1, 0)),
        SceneNode("text", SceneNodeKind.TEXT, Rect(20, 20, 80, 30), text="Above"),
        SceneNode("cover", SceneNodeKind.RECTANGLE, Rect(20, 20, 20, 20), fill=Color(0, 0, 1)),
    )
    return Scene(200, 120, root)


def test_mixed_primitives_preserve_authored_painter_order() -> None:
    renderer = WgpuRenderer()
    window = Window(width=200, height=120)
    entry = renderer._ordered_payload(window, _scene())
    assert entry.payload is not None
    rectangles, texts, images, paths, boundaries = entry.payload
    # Native draws each segment rect -> path -> image -> text. Splitting here
    # makes the green rectangle cover the red path, and blue cover the text.
    assert [len(segment) for segment in rectangles] == [0, 1, 1]
    assert [len(segment) for segment in texts] == [0, 1, 0]
    assert [len(segment) for segment in paths] == [3, 0, 0]
    assert images == [[], [], []]
    assert boundaries == [None, None]


def test_ordering_boundaries_do_not_add_fake_glass_and_reuse_cache() -> None:
    renderer = WgpuRenderer()
    window = Window(width=200, height=120)
    scene = _scene()
    scene.root.add(BackdropBlur(radius=4).to_scene_node("glass", Rect(30, 30, 40, 40)))
    first = renderer._ordered_payload(window, scene)
    assert first.payload is not None
    assert len(first.payload[-1]) == 3
    assert first.payload[-1][:2] == [None, None]
    assert first.payload[-1][2] is not None
    assert renderer._ordered_payload(window, scene) is first
    scene.touch()
    assert renderer._ordered_payload(window, scene).token != first.token


def test_already_ordered_batches_keep_existing_fast_path() -> None:
    renderer = WgpuRenderer()
    window = Window(width=200, height=120)
    scene = _scene()
    scene.root.children = scene.root.children[1:3]
    assert renderer._ordered_payload(window, scene).payload is None
