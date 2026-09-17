from swirui import Component, ProgressBar, ProgressRing, build_accessibility_tree
from swirui.core import AccessibilityRole, Event
from swirui.rendering import Rect, SceneNodeKind
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
