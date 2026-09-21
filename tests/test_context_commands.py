from __future__ import annotations

import pytest

from swirui import CommandItem, CommandPalette, ContextMenu
from swirui.core import AccessibilityRole
from swirui.rendering import Rect


def test_context_menu_preserves_active_command_by_stable_key() -> None:
    menu = ContextMenu(
        (
            CommandItem("open", "Open", "Ctrl+O"),
            CommandItem("rename", "Rename", "F2"),
            CommandItem("delete", "Delete", "Del"),
        ),
        bounds=Rect(10.0, 12.0, 240.0, 120.0),
        key="context",
        dismiss_on_invoke=False,
    )

    menu.activate_key("rename")
    assert menu.active_item is not None
    assert menu.active_item.key == "rename"

    menu.set_items(
        (
            CommandItem("rename", "Rename item", "F2"),
            CommandItem("copy", "Copy", "Ctrl+C"),
        )
    )
    assert menu.active_index == 0
    assert menu.active_item is not None
    assert menu.active_item.label == "Rename item"
    assert menu.accessible_value_text == "Rename item, command 1 of 2"


def test_context_menu_open_close_scene_and_accessibility() -> None:
    menu = ContextMenu(
        (
            CommandItem("copy", "Copy", "Ctrl+C"),
            CommandItem("locked", "Locked", disabled=True),
        ),
        bounds=Rect(0.0, 0.0, 220.0, 76.0),
        key="context",
        dismiss_on_invoke=False,
    )

    menu.open_at(32.0, 44.0)
    assert menu.bounds.x == 32.0
    assert menu.bounds.y == 44.0
    assert menu.visible is True

    scene = menu.build_scene_node()
    labels = [node.text for node in scene.walk() if node.kind.value == "text"]
    assert labels == ["Copy", "Ctrl+C", "Locked"]
    assert any(node.key == "context:item:0:accent" for node in scene.walk())

    snapshot = menu.accessibility_snapshot(focused=menu)
    assert snapshot.role is AccessibilityRole.MENU
    assert snapshot.focused is True
    assert snapshot.children[0].role is AccessibilityRole.MENU_ITEM
    assert snapshot.children[1].enabled is False

    menu.close()
    assert menu.visible is False


def test_context_menu_validates_commands() -> None:
    with pytest.raises(ValueError, match="Duplicate command key"):
        ContextMenu(
            (CommandItem("same", "A"), CommandItem("same", "B")),
            bounds=Rect(0.0, 0.0, 200.0, 80.0),
        )

    menu = ContextMenu(
        (CommandItem("only", "Only"),),
        bounds=Rect(0.0, 0.0, 200.0, 40.0),
    )
    with pytest.raises(KeyError, match="Unknown context-menu command key"):
        menu.activate_key("missing")


def test_command_palette_filters_and_preserves_stable_identity() -> None:
    palette = CommandPalette(
        (
            CommandItem("open", "Open workspace", "Ctrl+O"),
            CommandItem("grid", "Toggle Grid", "Ctrl+G"),
            CommandItem("guide", "Toggle Guides"),
            CommandItem("locked", "Grid locked", disabled=True),
        ),
        bounds=Rect(20.0, 20.0, 420.0, 260.0),
        key="palette",
        dismiss_on_invoke=False,
    )

    palette.activate_key("grid")
    palette.set_query("grid")
    assert [item.key for item in palette.filtered_items] == ["grid", "locked"]
    assert palette.active_item is not None
    assert palette.active_item.key == "grid"

    palette.set_items(
        (
            CommandItem("grid", "Toggle editor grid", "Ctrl+G"),
            CommandItem("open", "Open workspace", "Ctrl+O"),
            CommandItem("guide", "Toggle Guides"),
        )
    )
    assert [item.key for item in palette.filtered_items] == ["grid"]
    assert palette.active_item is not None
    assert palette.active_item.label == "Toggle editor grid"


def test_command_palette_scene_and_accessibility_follow_query() -> None:
    palette = CommandPalette(
        (
            CommandItem("open", "Open workspace", "Ctrl+O"),
            CommandItem("export", "Export image", "Ctrl+E"),
            CommandItem("settings", "Settings"),
        ),
        bounds=Rect(8.0, 10.0, 420.0, 220.0),
        key="palette",
        query="ex",
        dismiss_on_invoke=False,
    )

    assert [item.key for item in palette.filtered_items] == ["export"]
    scene = palette.build_scene_node()
    texts = [node.text for node in scene.walk() if node.kind.value == "text"]
    assert "ex" in texts
    assert "Export image" in texts
    assert "Ctrl+E" in texts
    assert "Open workspace" not in texts

    snapshot = palette.accessibility_snapshot(focused=palette)
    assert snapshot.role is AccessibilityRole.DIALOG
    assert snapshot.focused is True
    assert len(snapshot.children) == 1
    assert snapshot.children[0].name == "Export image"
    assert snapshot.children[0].active is True
    assert palette.accessible_value_text == "1 matching commands; Export image, result 1"


def test_command_palette_multi_token_search_and_missing_key() -> None:
    palette = CommandPalette(
        (
            CommandItem("open-folder", "Open Folder", "Ctrl+Shift+O"),
            CommandItem("open-file", "Open File", "Ctrl+O"),
        ),
        bounds=Rect(0.0, 0.0, 360.0, 200.0),
    )

    palette.set_query("open shift")
    assert [item.key for item in palette.filtered_items] == ["open-folder"]

    with pytest.raises(KeyError, match="Unknown visible command key"):
        palette.activate_key("open-file")
