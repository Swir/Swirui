import pytest

from swirui.rendering import BackdropBlur, Color, CornerRadius, Rect, Scene, SceneNode, SceneNodeKind


def test_backdrop_blur_builds_non_interactive_painter_boundary() -> None:
    blur = BackdropBlur(radius=20.0, corner_radius=CornerRadius.uniform(14.0))
    node = blur.to_scene_node("glass", Rect(40, 30, 260, 150), z_index=4)

    assert node.kind is SceneNodeKind.BACKDROP_BLUR
    assert node.blur_radius == 20.0
    assert node.corner_radius == CornerRadius.uniform(14.0)
    assert node.clip_to_bounds is True
    assert node.hit_testable is False
    assert node.z_index == 4


def test_backdrop_blur_children_follow_boundary_in_painter_order() -> None:
    root = SceneNode("root", SceneNodeKind.GROUP, Rect(0, 0, 640, 360))
    background = SceneNode(
        "background",
        SceneNodeKind.RECTANGLE,
        Rect(0, 0, 640, 360),
        fill=Color.from_hex("#07111F"),
    )
    glass = BackdropBlur(radius=16.0).to_scene_node("glass", Rect(80, 60, 320, 180))
    foreground = SceneNode(
        "foreground",
        SceneNodeKind.RECTANGLE,
        Rect(100, 80, 120, 48),
        fill=Color.from_hex("#FFFFFF44"),
    )
    glass.add(foreground)
    root.add(background, glass)

    scene = Scene(640, 360, root)
    assert [node.key for node in scene.walk()] == [
        "root",
        "background",
        "glass",
        "foreground",
    ]

    composited = list(scene.walk_composited())
    blur_entry = next(item for item in composited if item[0] is glass)
    foreground_entry = next(item for item in composited if item[0] is foreground)
    assert blur_entry[2] == Rect(80, 60, 320, 180)
    assert foreground_entry[2] == Rect(80, 60, 320, 180)


def test_backdrop_blur_never_becomes_direct_hit_target() -> None:
    node = BackdropBlur(radius=12.0).to_scene_node("glass", Rect(20, 20, 200, 120))
    assert node.hit_test_xy(40, 40) is None


def test_backdrop_blur_validates_radius_and_bounds() -> None:
    with pytest.raises(ValueError, match="range"):
        BackdropBlur(radius=0.0)
    with pytest.raises(ValueError, match="range"):
        BackdropBlur(radius=65.0)
    with pytest.raises(ValueError, match="finite"):
        BackdropBlur(radius=float("nan"))
    with pytest.raises(ValueError, match="positive"):
        BackdropBlur(radius=8.0).to_scene_node("glass", Rect(0, 0, 0, 20))


def test_scene_node_rejects_invalid_raw_backdrop_radius() -> None:
    with pytest.raises(ValueError, match="range"):
        SceneNode(
            "bad",
            SceneNodeKind.BACKDROP_BLUR,
            Rect(0, 0, 100, 100),
            blur_radius=0.0,
        )
