import pytest

from swirui.rendering import (
    Color,
    CornerRadius,
    FrameScheduler,
    Point,
    Rect,
    RenderNode,
    RenderTree,
    Scene,
    SceneNode,
    SceneNodeKind,
)


def test_geometry_and_color_primitives() -> None:
    rect = Rect(10, 20, 100, 50)

    assert rect.contains(Point(10, 20))
    assert rect.contains(Point(110, 70))
    assert not rect.contains(Point(111, 70))
    assert rect.intersects(Rect(100, 60, 20, 20))
    assert not rect.intersects(Rect(200, 200, 10, 10))

    color = Color.from_hex("#00A8FFFF")
    assert color == Color(0.0, 168 / 255.0, 1.0, 1.0)
    assert color.with_alpha(0.5).a == 0.5
    assert CornerRadius.uniform(12).bottom_left == 12


def test_render_tree_orders_children_by_z_index() -> None:
    root = RenderNode("root", Rect(0, 0, 100, 100))
    front = RenderNode("front", Rect(0, 0, 10, 10), z_index=10)
    back = RenderNode("back", Rect(0, 0, 10, 10), z_index=-1)
    hidden = RenderNode("hidden", Rect(0, 0, 10, 10), visible=False)
    root.add(front, hidden, back)

    tree = RenderTree(root)

    assert [node.key for node in tree.walk()] == ["root", "back", "hidden", "front"]
    assert [node.key for node in tree.walk(visible_only=True)] == ["root", "back", "front"]

    tree.invalidate()
    assert tree.generation == 1


def test_render_tree_rejects_cycles() -> None:
    root = RenderNode("root", Rect(0, 0, 100, 100))
    child = RenderNode("child", Rect(0, 0, 10, 10))
    root.add(child)

    with pytest.raises(ValueError, match="cycle"):
        child.add(root)


def test_scene_validates_specialized_nodes() -> None:
    root = SceneNode("root", SceneNodeKind.GROUP, Rect(0, 0, 800, 600))
    card = SceneNode(
        "card",
        SceneNodeKind.RECTANGLE,
        Rect(20, 20, 300, 180),
        fill=Color.from_hex("#101824"),
        corner_radius=CornerRadius.uniform(20),
    )
    text = SceneNode("title", SceneNodeKind.TEXT, Rect(40, 40, 200, 40), text="SwirUI")
    root.add(card, text)
    scene = Scene(800, 600, root)

    assert [node.key for node in scene.walk()] == ["root", "card", "title"]

    with pytest.raises(ValueError, match="text content"):
        SceneNode("invalid", SceneNodeKind.TEXT, Rect(0, 0, 10, 10))


def test_scene_hit_testing_returns_topmost_visual_and_path() -> None:
    root = SceneNode("root", SceneNodeKind.GROUP, Rect(0, 0, 800, 600))
    panel = SceneNode("panel", SceneNodeKind.GROUP, Rect(20, 20, 400, 300))
    back = SceneNode(
        "back",
        SceneNodeKind.RECTANGLE,
        Rect(60, 60, 180, 140),
        fill=Color.from_hex("#112233"),
        z_index=1,
    )
    front = SceneNode(
        "front",
        SceneNodeKind.RECTANGLE,
        Rect(80, 80, 180, 140),
        fill=Color.from_hex("#00A8FF"),
        z_index=10,
    )
    invisible = SceneNode(
        "invisible",
        SceneNodeKind.RECTANGLE,
        Rect(80, 80, 180, 140),
        fill=Color.from_hex("#FFFFFF"),
        opacity=0.0,
        z_index=50,
    )
    panel.add(back, front, invisible)
    root.add(panel)
    scene = Scene(800, 600, root)

    target = scene.hit_test(Point(100, 100))
    path = scene.hit_path(Point(100, 100))

    assert target is front
    assert [node.key for node in path] == ["root", "panel", "front"]
    assert scene.hit_test(Point(700, 500)) is None


def test_scene_hit_testing_uses_later_insertion_for_equal_z() -> None:
    root = SceneNode("root", SceneNodeKind.GROUP, Rect(0, 0, 400, 300))
    first = SceneNode(
        "first",
        SceneNodeKind.RECTANGLE,
        Rect(20, 20, 100, 100),
        fill=Color.from_hex("#111111"),
    )
    second = SceneNode(
        "second",
        SceneNodeKind.RECTANGLE,
        Rect(20, 20, 100, 100),
        fill=Color.from_hex("#222222"),
    )
    root.add(first, second)
    scene = Scene(400, 300, root)

    assert scene.hit_test(Point(40, 40)) is second


def test_frame_scheduler_is_invalidation_driven() -> None:
    scheduler = FrameScheduler(target_fps=120)

    assert scheduler.consume(0.0) is True
    assert scheduler.consume(0.001) is False
    assert scheduler.stats.dropped_requests == 0

    scheduler.invalidate()
    assert scheduler.consume(0.001) is False
    assert scheduler.stats.dropped_requests == 1
    assert scheduler.seconds_until_due(0.001) == pytest.approx((1 / 120) - 0.001)

    assert scheduler.consume(1 / 120) is True
    assert scheduler.stats.frame_number == 2
    assert scheduler.dirty is False
