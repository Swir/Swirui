from __future__ import annotations

import pytest

from swirui import DockPane, DockWorkspace, Panel
from swirui.core import AccessibilityRole
from swirui.rendering import Rect


def _panel(name: str) -> Panel:
    return Panel(bounds=Rect(0.0, 0.0, 20.0, 20.0), accessible_name=name)


def test_dock_workspace_carves_edges_and_arranges_center_content() -> None:
    explorer = _panel("Explorer content")
    inspector = _panel("Inspector content")
    console = _panel("Console content")
    editor = _panel("Editor content")
    preview = _panel("Preview content")
    workspace = DockWorkspace(
        (
            DockPane("explorer", "Explorer", explorer, dock="left", extent=200.0),
            DockPane("inspector", "Inspector", inspector, dock="right", extent=220.0),
            DockPane("console", "Console", console, dock="bottom", extent=140.0),
            DockPane("editor", "Editor", editor),
            DockPane("preview", "Preview", preview),
        ),
        bounds=Rect(0.0, 0.0, 1000.0, 600.0),
        key="workspace",
        header_height=32.0,
    )

    assert workspace.pane_bounds("explorer") == Rect(0.0, 0.0, 200.0, 600.0)
    assert workspace.pane_bounds("inspector") == Rect(780.0, 0.0, 220.0, 600.0)
    assert workspace.pane_bounds("console") == Rect(200.0, 460.0, 580.0, 140.0)
    assert workspace.pane_bounds("editor") == Rect(200.0, 0.0, 580.0, 460.0)
    assert workspace.pane_bounds("preview") == Rect(200.0, 0.0, 580.0, 460.0)

    workspace.prepare_layout(workspace.bounds)
    assert explorer.bounds == Rect(0.0, 32.0, 200.0, 568.0)
    assert inspector.bounds == Rect(780.0, 32.0, 220.0, 568.0)
    assert console.bounds == Rect(200.0, 492.0, 580.0, 108.0)
    assert editor.bounds == Rect(200.0, 32.0, 580.0, 428.0)
    assert preview.visible is False


def test_dock_workspace_preserves_center_activation_across_replacement() -> None:
    explorer = _panel("Explorer")
    editor = _panel("Editor")
    preview = _panel("Preview")
    workspace = DockWorkspace(
        (
            DockPane("explorer", "Explorer", explorer, dock="left"),
            DockPane("editor", "Editor", editor),
            DockPane("preview", "Preview", preview),
        ),
        bounds=Rect(0.0, 0.0, 640.0, 360.0),
        active_key="preview",
    )

    replacement_preview = _panel("Preview v2")
    timeline = _panel("Timeline")
    workspace.set_panes(
        (
            DockPane("preview", "Preview v2", replacement_preview),
            DockPane("timeline", "Timeline", timeline, dock="bottom", extent=100.0),
        )
    )

    assert workspace.active_key == "preview"
    assert workspace.active_center_key == "preview"
    assert replacement_preview.visible is True
    assert timeline.visible is True
    assert explorer.parent is None
    assert editor.parent is None
    assert preview.parent is None


def test_dock_workspace_redocks_pane_and_emits_stable_event() -> None:
    explorer = _panel("Explorer")
    editor = _panel("Editor")
    workspace = DockWorkspace(
        (
            DockPane("explorer", "Explorer", explorer, dock="left", extent=180.0),
            DockPane("editor", "Editor", editor),
        ),
        bounds=Rect(0.0, 0.0, 700.0, 400.0),
    )
    events = []
    workspace.on("pane_docked", events.append)

    workspace.dock_pane("explorer", "right", extent=210.0)

    pane = next(pane for pane in workspace.panes if pane.key == "explorer")
    assert pane.dock == "right"
    assert pane.extent == 210.0
    assert workspace.active_key == "explorer"
    assert workspace.pane_bounds("explorer") == Rect(490.0, 0.0, 210.0, 400.0)
    assert events[-1].data["old_dock"] == "left"
    assert events[-1].data["dock"] == "right"


def test_dock_workspace_scene_and_accessibility_cover_center_tabs() -> None:
    editor = _panel("Editor content")
    preview = _panel("Preview content")
    workspace = DockWorkspace(
        (
            DockPane("editor", "Editor", editor),
            DockPane("preview", "Preview", preview),
        ),
        bounds=Rect(0.0, 0.0, 500.0, 280.0),
        key="dock",
        active_key="preview",
    )

    scene = workspace.build_scene_node()
    keys = {node.key for node in scene.walk()}
    assert "dock:pane:editor:header" in keys
    assert "dock:pane:preview:header" in keys
    assert "dock:pane:preview:accent" in keys

    snapshot = workspace.accessibility_snapshot(focused=workspace)
    assert snapshot.role is AccessibilityRole.GROUP
    assert snapshot.focused is True
    pane_nodes = [child for child in snapshot.children if child.role is AccessibilityRole.BUTTON]
    assert [child.name for child in pane_nodes] == ["Editor", "Preview"]
    assert pane_nodes[0].selected is False
    assert pane_nodes[1].selected is True
    assert any(child.name == "Preview content" for child in snapshot.children)
    assert all(child.name != "Editor content" for child in snapshot.children)


def test_dock_workspace_validates_keys_content_and_dock_values() -> None:
    shared = _panel("Shared")
    with pytest.raises(ValueError, match="distinct content"):
        DockWorkspace(
            (
                DockPane("one", "One", shared),
                DockPane("two", "Two", shared),
            ),
            bounds=Rect(0.0, 0.0, 300.0, 200.0),
        )

    with pytest.raises(ValueError, match="keys must be unique"):
        DockWorkspace(
            (
                DockPane("same", "One", _panel("One")),
                DockPane("same", "Two", _panel("Two")),
            ),
            bounds=Rect(0.0, 0.0, 300.0, 200.0),
        )

    with pytest.raises(ValueError, match="dock must be"):
        DockPane("bad", "Bad", _panel("Bad"), dock="floating")  # type: ignore[arg-type]
