from __future__ import annotations

import pytest

from swirui import NavigationItem, NavigationRail, Sidebar
from swirui.core import AccessibilityRole
from swirui.rendering import Rect


def test_navigation_rail_selects_and_preserves_stable_key() -> None:
    rail = NavigationRail(
        (
            NavigationItem("home", "Home", "HM"),
            NavigationItem("settings", "Settings", "ST"),
        ),
        bounds=Rect(8.0, 12.0, 88.0, 240.0),
        key="rail",
    )

    assert rail.selected_key == "home"
    rail.select_key("settings")
    assert rail.selected_index == 1
    assert rail.accessible_value_text == "Settings selected, 2 of 2"

    rail.set_items(
        (
            NavigationItem("settings", "Settings v2", "SV"),
            NavigationItem("logs", "Logs", "LG"),
        )
    )
    assert rail.selected_key == "settings"
    assert rail.selected_index == 0
    assert rail.selected_item is not None
    assert rail.selected_item.label == "Settings v2"


def test_navigation_rail_skips_disabled_items_and_validates_identity() -> None:
    rail = NavigationRail(
        (
            NavigationItem("home", "Home"),
            NavigationItem("disabled", "Disabled", disabled=True),
            NavigationItem("logs", "Logs"),
        ),
        bounds=Rect(0.0, 0.0, 96.0, 240.0),
    )

    rail.select_index(1)
    assert rail.selected_key == "home"
    rail.select_key("logs")
    assert rail.selected_key == "logs"

    with pytest.raises(KeyError, match="Unknown navigation key"):
        rail.select_key("missing")

    with pytest.raises(ValueError, match="Duplicate navigation key"):
        NavigationRail(
            (NavigationItem("same", "A"), NavigationItem("same", "B")),
            bounds=Rect(0.0, 0.0, 96.0, 200.0),
        )


def test_navigation_rail_scene_compact_and_expanded_labels() -> None:
    rail = NavigationRail(
        (NavigationItem("dashboard", "Dashboard", "DB"),),
        bounds=Rect(10.0, 20.0, 92.0, 180.0),
        key="nav",
    )

    compact_scene = rail.build_scene_node()
    compact_labels = [node for node in compact_scene.walk() if node.kind.value == "text"]
    assert [node.text for node in compact_labels] == ["DB"]
    assert any(node.key == "nav:item:0:accent" for node in compact_scene.walk())

    rail.set_expanded(True)
    expanded_scene = rail.build_scene_node()
    expanded_labels = [node for node in expanded_scene.walk() if node.kind.value == "text"]
    assert [node.text for node in expanded_labels] == ["Dashboard"]


def test_navigation_rail_accessibility_and_sidebar_defaults() -> None:
    sidebar = Sidebar(
        (
            NavigationItem("home", "Home"),
            NavigationItem("settings", "Settings", disabled=True),
            NavigationItem("about", "About"),
        ),
        bounds=Rect(0.0, 0.0, 220.0, 260.0),
        key="sidebar",
    )

    assert sidebar.expanded is True
    snapshot = sidebar.accessibility_snapshot(focused=sidebar)
    assert snapshot.role is AccessibilityRole.LIST
    assert snapshot.focused is True
    assert snapshot.row_count == 3
    assert [child.role for child in snapshot.children] == [
        AccessibilityRole.LIST_ITEM,
        AccessibilityRole.LIST_ITEM,
        AccessibilityRole.LIST_ITEM,
    ]
    assert snapshot.children[0].selected is True
    assert snapshot.children[1].enabled is False
    assert snapshot.children[2].selected is False
