import pytest

from swirui import FUTURE_LIGHT, Component, ProgressBar, ProgressRing, build_accessibility_tree
from swirui.core import AccessibilityRole, Event
from swirui.rendering import Color, LinearGradient, Point, Rect, SceneNodeKind
from swirui.widgets import compile_component_scene


def test_progress_bar_compiles_fill_and_numeric_semantics() -> None:
    root = Component("root")
    progress = ProgressBar(
        key="build",
        bounds=Rect(20.0, 30.0, 300.0, 14.0),
        value=40.0,
        accessible_name="Build progress",
    )
    root.add(progress)
    changes: list[Event] = []
    progress.on("changed", changes.append)

    scene = compile_component_scene(root, width=400.0, height=120.0)
    tree = build_accessibility_tree(root)

    assert scene is not None
    fill = next(node for node in scene.walk() if node.key == "build:fill")
    assert fill.bounds.width == 120.0
    assert fill.hit_testable is False
    assert tree is not None
    semantics = tree.find("build")
    assert semantics is not None
    assert semantics.role is AccessibilityRole.PROGRESS_BAR
    assert semantics.value == 40.0
    assert semantics.min_value == 0.0
    assert semantics.max_value == 100.0
    assert semantics.value_text == "40%"

    progress.value = 130.0
    assert progress.value == 100.0
    assert progress.progress == 1.0
    assert len(changes) == 1
    assert changes[0].data["old_value"] == 40.0
    assert changes[0].data["value"] == 100.0


def test_gradient_bar_clips_a_fixed_scale_and_remains_pointer_transparent() -> None:
    bounds = Rect(10, 20, 240, 16)
    gradient = LinearGradient.two_color(Color.from_hex("#A38BFF"), Color.from_hex("#82E7B8"),
                                        start=Point(0, 0), end=Point(1, 1))
    bar = ProgressBar(bounds=bounds, minimum=20, maximum=60, value=30, fill_gradient=gradient)
    root = Component(theme=FUTURE_LIGHT)
    root.add(bar)
    changes = []
    bar.on("changed", changes.append)
    paint = bar.build_scene_node().children[0]
    assert paint.clip_to_bounds and paint.bounds == Rect(10, 20, 60, 16)
    assert all(node.bounds == bounds for node in paint.children)
    assert len({node.fill for node in paint.children}) > 2
    assert not any(node.hit_testable for node in paint.walk())
    scene = compile_component_scene(root, width=320, height=100)
    assert scene is not None and scene.hit_test(Point(50, 28)) is None
    assert bar.accessible_value == 30 and bar.accessible_value_text == "25%"

    bar.enabled = False
    assert bar.build_scene_node().children[0].fill == FUTURE_LIGHT.surface_color("disabled")
    bar.enabled = True
    assert bar.build_scene_node().children[0].children[0].path is paint.children[0].path
    bar.fill_gradient = None
    assert bar.build_scene_node().children[0].fill == FUTURE_LIGHT.surface_color("accent")
    with pytest.raises(TypeError, match="fill_gradient"):
        bar.fill_gradient = "mint"
    assert bar.fill_gradient is None and not changes
    bar.fill_gradient = gradient
    bar.value = 20
    assert not bar.build_scene_node().children
    bar.value = 60
    assert bar.build_scene_node().children[0].bounds == bounds
    bar.bounds = Rect(10, 20, 240, 0)
    assert not bar.build_scene_node().children
    for size in (.0001, .00001):
        bar.bounds = Rect(10, 20, size, size)
        assert bar.build_scene_node().children[0].bounds == bar.bounds
    bar.bounds = bounds
    assert bar.build_scene_node().children[0].children[0].path is paint.children[0].path


def test_progress_ring_uses_deterministic_retained_path_segments() -> None:
    root = Component("root")
    ring = ProgressRing(
        key="ring",
        bounds=Rect(20.0, 20.0, 96.0, 96.0),
        value=50.0,
        segments=16,
        thickness=8.0,
    )
    root.add(ring)

    scene = compile_component_scene(root, width=160.0, height=140.0)

    assert scene is not None
    ring_node = next(node for node in scene.walk() if node.key == "ring")
    segments = [node for node in ring_node.children if node.kind is SceneNodeKind.PATH]
    assert len(segments) == 16
    assert all(segment.path is not None for segment in segments)
    assert all(segment.hit_testable is False for segment in segments)


def test_full_thickness_progress_ring_uses_valid_center_triangles() -> None:
    ring = ProgressRing(
        key="solid-ring",
        bounds=Rect(0.0, 0.0, 40.0, 40.0),
        value=75.0,
        thickness=40.0,
        segments=8,
    )

    node = ring.build_scene_node()

    assert len(node.children) == 8
    assert all(child.path is not None for child in node.children)
    assert all(child.path.triangle_count == 1 for child in node.children if child.path is not None)


def test_progress_widgets_validate_configuration() -> None:
    invalid = [
        lambda: ProgressBar(bounds=Rect(0.0, 0.0, 100.0, 10.0), maximum=0.0),
        lambda: ProgressRing(
            bounds=Rect(0.0, 0.0, 40.0, 40.0),
            thickness=0.0,
        ),
        lambda: ProgressRing(
            bounds=Rect(0.0, 0.0, 40.0, 40.0),
            segments=4,
        ),
    ]
    for build in invalid:
        try:
            build()
        except ValueError:
            pass
        else:
            raise AssertionError("invalid progress configuration must raise ValueError")
