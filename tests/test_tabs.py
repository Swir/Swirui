from __future__ import annotations

import pytest

from swirui import Panel, TabItem, Tabs
from swirui.core import AccessibilityRole
from swirui.rendering import Rect


def _panel(name: str) -> Panel:
    return Panel(bounds=Rect(0.0, 0.0, 20.0, 20.0), accessible_name=name)


def test_tabs_selects_one_page_and_arranges_active_content() -> None:
    overview = _panel("Overview page")
    logs = _panel("Logs page")
    tabs = Tabs(
        (
            TabItem("overview", "Overview", overview),
            TabItem("logs", "Logs", logs),
        ),
        bounds=Rect(10.0, 20.0, 420.0, 260.0),
        key="workspace-tabs",
        header_height=44.0,
    )

    assert tabs.selected_key == "overview"
    assert overview.visible is True
    assert logs.visible is False

    tabs.prepare_layout(tabs.bounds)
    assert overview.bounds == Rect(10.0, 64.0, 420.0, 216.0)

    tabs.select_key("logs")
    tabs.prepare_layout(tabs.bounds)
    assert tabs.selected_index == 1
    assert overview.visible is False
    assert logs.visible is True
    assert logs.bounds == Rect(10.0, 64.0, 420.0, 216.0)
    assert tabs.accessible_value_text == "Logs selected, 2 of 2"


def test_tabs_preserves_selection_by_stable_key_across_replacement() -> None:
    first = _panel("First")
    selected = _panel("Selected")
    tabs = Tabs(
        (
            TabItem("first", "First", first),
            TabItem("selected", "Selected", selected),
        ),
        bounds=Rect(0.0, 0.0, 320.0, 180.0),
        selected_key="selected",
    )

    replacement_selected = _panel("Selected v2")
    extra = _panel("Extra")
    tabs.set_tabs(
        (
            TabItem("selected", "Selected v2", replacement_selected),
            TabItem("extra", "Extra", extra),
        )
    )

    assert tabs.selected_key == "selected"
    assert tabs.selected_index == 0
    assert replacement_selected.visible is True
    assert extra.visible is False
    assert first.parent is None
    assert selected.parent is None


def test_tabs_skips_disabled_selection_and_rejects_invalid_descriptors() -> None:
    tabs = Tabs(
        (
            TabItem("a", "A", _panel("A")),
            TabItem("b", "B", _panel("B"), disabled=True),
            TabItem("c", "C", _panel("C")),
        ),
        bounds=Rect(0.0, 0.0, 300.0, 180.0),
    )

    tabs.select_index(1)
    assert tabs.selected_key == "a"
    tabs.select_key("c")
    assert tabs.selected_key == "c"

    with pytest.raises(KeyError, match="Unknown tab key"):
        tabs.select_key("missing")

    shared = _panel("Shared")
    with pytest.raises(ValueError, match="distinct content"):
        Tabs(
            (TabItem("one", "One", shared), TabItem("two", "Two", shared)),
            bounds=Rect(0.0, 0.0, 300.0, 180.0),
        )


def test_tabs_scene_and_accessibility_expose_selected_tab() -> None:
    overview = _panel("Overview content")
    settings = _panel("Settings content")
    tabs = Tabs(
        (
            TabItem("overview", "Overview", overview),
            TabItem("settings", "Settings", settings),
        ),
        bounds=Rect(0.0, 0.0, 400.0, 220.0),
        key="tabs",
        selected_key="settings",
    )

    scene = tabs.build_scene_node()
    header_nodes = [child for child in scene.children if child.key.startswith("tabs:tab:")]
    assert len(header_nodes) == 2
    assert any(
        grandchild.key == "tabs:tab:1:accent"
        for child in header_nodes
        for grandchild in child.children
    )

    snapshot = tabs.accessibility_snapshot(focused=tabs)
    assert snapshot.role is AccessibilityRole.GROUP
    assert snapshot.focused is True
    tab_nodes = [child for child in snapshot.children if child.role is AccessibilityRole.BUTTON]
    assert [child.name for child in tab_nodes] == ["Overview", "Settings"]
    assert tab_nodes[0].selected is False
    assert tab_nodes[1].selected is True
    assert tab_nodes[1].active is True
    assert any(child.name == "Settings content" for child in snapshot.children)
