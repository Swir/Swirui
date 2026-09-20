from __future__ import annotations

import pytest

from swirui import CommandItem, MenuBar, Ribbon, RibbonGroup, Toolbar
from swirui.core import AccessibilityRole
from swirui.rendering import Rect


def test_toolbar_preserves_active_command_by_stable_key() -> None:
    toolbar = Toolbar(
        (
            CommandItem("new", "New", "Ctrl+N"),
            CommandItem("save", "Save", "Ctrl+S"),
        ),
        bounds=Rect(8.0, 10.0, 260.0, 52.0),
        key="toolbar",
    )

    toolbar.activate_key("save")
    assert toolbar.active_item is not None
    assert toolbar.active_item.key == "save"

    toolbar.set_items(
        (
            CommandItem("save", "Save document", "Ctrl+S"),
            CommandItem("export", "Export", "Ctrl+E"),
        )
    )
    assert toolbar.active_index == 0
    assert toolbar.active_item is not None
    assert toolbar.active_item.label == "Save document"
    assert toolbar.accessible_value_text == "Save document, command 1 of 2"


def test_toolbar_skips_disabled_commands_and_validates_identity() -> None:
    toolbar = Toolbar(
        (
            CommandItem("open", "Open"),
            CommandItem("locked", "Locked", disabled=True),
        ),
        bounds=Rect(0.0, 0.0, 220.0, 48.0),
    )

    toolbar.activate_index(1)
    assert toolbar.active_item is not None
    assert toolbar.active_item.key == "open"

    with pytest.raises(KeyError, match="Unknown command key"):
        toolbar.activate_key("missing")

    with pytest.raises(ValueError, match="Duplicate command key"):
        Toolbar(
            (CommandItem("same", "A"), CommandItem("same", "B")),
            bounds=Rect(0.0, 0.0, 220.0, 48.0),
        )


def test_menubar_scene_and_accessibility_semantics() -> None:
    menu = MenuBar(
        (
            CommandItem("file", "File", "Alt+F"),
            CommandItem("edit", "Edit", "Alt+E"),
        ),
        bounds=Rect(0.0, 0.0, 220.0, 46.0),
        key="menu",
    )

    scene = menu.build_scene_node()
    labels = [node.text for node in scene.walk() if node.kind.value == "text"]
    assert labels == ["File", "Alt+F", "Edit", "Alt+E"]
    assert any(node.key == "menu:item:0:accent" for node in scene.walk())

    snapshot = menu.accessibility_snapshot(focused=menu)
    assert snapshot.role is AccessibilityRole.MENU
    assert snapshot.focused is True
    assert [child.role for child in snapshot.children] == [
        AccessibilityRole.MENU_ITEM,
        AccessibilityRole.MENU_ITEM,
    ]
    assert snapshot.children[0].description == "Alt+F"


def test_ribbon_selects_groups_and_exposes_active_commands() -> None:
    ribbon = Ribbon(
        (
            RibbonGroup(
                "home",
                "Home",
                (
                    CommandItem("paste", "Paste"),
                    CommandItem("copy", "Copy"),
                ),
            ),
            RibbonGroup(
                "view",
                "View",
                (
                    CommandItem("zoom", "Zoom"),
                    CommandItem("grid", "Grid", disabled=True),
                ),
            ),
        ),
        bounds=Rect(0.0, 0.0, 480.0, 118.0),
        key="ribbon",
    )

    assert ribbon.selected_key == "home"
    assert ribbon.active_command is not None
    assert ribbon.active_command.key == "paste"

    ribbon.select_group("view")
    assert ribbon.selected_key == "view"
    assert ribbon.active_command is not None
    assert ribbon.active_command.key == "zoom"
    ribbon.activate_command("grid")
    assert ribbon.active_command.key == "zoom"

    scene = ribbon.build_scene_node()
    keys = {node.key for node in scene.walk()}
    assert "ribbon:group:1" in keys
    assert "ribbon:command:0" in keys

    snapshot = ribbon.accessibility_snapshot(focused=ribbon)
    assert snapshot.role is AccessibilityRole.GROUP
    assert snapshot.children[1].selected is True
    assert snapshot.children[1].children[0].active is True
    assert snapshot.children[1].children[1].enabled is False


def test_ribbon_validates_group_identity_and_selection() -> None:
    group = RibbonGroup("home", "Home", (CommandItem("paste", "Paste"),))

    with pytest.raises(ValueError, match="Duplicate ribbon group key"):
        Ribbon(
            (group, RibbonGroup("home", "Home 2", (CommandItem("copy", "Copy"),))),
            bounds=Rect(0.0, 0.0, 480.0, 118.0),
        )

    with pytest.raises(KeyError, match="Unknown selected ribbon group key"):
        Ribbon((group,), bounds=Rect(0.0, 0.0, 480.0, 118.0), selected_key="missing")
