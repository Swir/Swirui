from math import nan

import pytest

from swirui import (
    Component,
    ProgressBar,
    ProgressRing,
    Window,
    build_accessibility_tree,
    mount,
)
from swirui.core import AccessibilityRole, Event
from swirui.rendering import Rect, Scene, SceneNode, SceneNodeKind
from swirui.widgets import compile_component_scene


def _node(scene: Scene, key: str) -> SceneNode:
    return next(node for node in scene.walk() if node.key == key)


def test_progress_bar_compiles_track_and_proportional_fill() -> None:
    root = Component("root")
    progress = ProgressBar(
        key="download",
        bounds=Rect(20.0, 30.0, 320.0, 18.0),
        value=25.0,
        accessible_name="Download",
    )
    root.add(progress)

    scene = compile_component_scene(root, width=420.0, height=160.0)

    assert scene is not None
    assert _node(scene, "download:track").kind is SceneNodeKind.RECTANGLE
    fill = _node(scene, "download:fill")
    assert fill.kind is SceneNodeKind.RECTANGLE
    assert fill.bounds == Rect(20.0, 30.0, 80.0, 18.0)
    assert fill.hit_testable is False
    assert scene.hit_test_xy(40.0, 38.0) is None


def test_progress_value_clamps_emits_change_and_rebuilds_mounted_scene() -> None:
    window = Window(width=440, height=180)
    root = Component("root")
    progress = ProgressBar(
        key="compile",
        bounds=Rect(20.0, 30.0, 300.0, 16.0),
        value=10.0,
        minimum=0.0,
        maximum=50.0,
    )
    root.add(progress)
    runtime = mount(window, root)
    changes: list[Event] = []
    progress.on("changed", changes.append)
    generation = runtime.generation

    progress.value = 80.0

    assert progress.value == 50.0
    assert progress.progress == 1.0
    assert progress.accessible_value == "100%"
    assert runtime.generation > generation
    assert len(changes) == 1
    assert changes[0].data["old_value"] == 10.0
    assert changes[0].data["value"] == 50.0
    assert changes[0].data["progress"] == 1.0
    assert window.scene is not None
    assert _node(window.scene, "compile:fill").bounds.width == 300.0


def test_progress_semantics_expose_role_name_and_percentage() -> None:
    root = Component("root")
    progress = ProgressRing(
        key="sync",
        bounds=Rect(20.0, 20.0, 96.0, 96.0),
        value=0.375,
        minimum=0.0,
        maximum=1.0,
        accessible_name="Sync progress",
    )
    root.add(progress)

    tree = build_accessibility_tree(root)

    assert tree is not None
    semantics = tree.find("sync")
    assert semantics is not None
    assert semantics.role is AccessibilityRole.PROGRESS_BAR
    assert semantics.name == "Sync progress"
    assert semantics.value == "38%"
    assert semantics.focusable is False


def test_progress_ring_builds_cached_path_geometry_for_track_and_fill() -> None:
    root = Component("root")
    ring = ProgressRing(
        key="ring",
        bounds=Rect(20.0, 10.0, 120.0, 100.0),
        value=72.0,
        thickness=8.0,
    )
    root.add(ring)

    scene = compile_component_scene(root, width=220.0, height=160.0)

    assert scene is not None
    track = _node(scene, "ring:track")
    fill = _node(scene, "ring:fill")
    assert track.kind is SceneNodeKind.PATH
    assert fill.kind is SceneNodeKind.PATH
    assert track.bounds == Rect(30.0, 10.0, 100.0, 100.0)
    assert track.path is not None
    assert fill.path is not None
    assert track.path.triangle_count > fill.path.triangle_count > 0
    assert track.hit_testable is False
    assert fill.hit_testable is False


def test_zero_progress_ring_omits_fill_and_full_ring_remains_valid() -> None:
    empty = ProgressRing(key="empty", bounds=Rect(0.0, 0.0, 80.0, 80.0), value=0.0)
    full = ProgressRing(key="full", bounds=Rect(100.0, 0.0, 80.0, 80.0), value=100.0)
    root = Component("root").add(empty, full)

    scene = compile_component_scene(root, width=220.0, height=120.0)

    assert scene is not None
    keys = {node.key for node in scene.walk()}
    assert "empty:fill" not in keys
    assert "full:fill" in keys
    assert _node(scene, "full:fill").path is not None


def test_progress_ranges_and_geometry_reject_non_finite_inputs() -> None:
    with pytest.raises(ValueError, match="maximum must be greater"):
        ProgressBar(bounds=Rect(0.0, 0.0, 100.0, 10.0), minimum=5.0, maximum=5.0)
    with pytest.raises(ValueError, match="value must be finite"):
        ProgressBar(bounds=Rect(0.0, 0.0, 100.0, 10.0), value=nan)
    with pytest.raises(ValueError, match="thickness"):
        ProgressRing(bounds=Rect(0.0, 0.0, 80.0, 80.0), thickness=0.0)
    with pytest.raises(ValueError, match="corner_radius"):
        ProgressBar(bounds=Rect(0.0, 0.0, 100.0, 10.0), corner_radius=-1.0)
