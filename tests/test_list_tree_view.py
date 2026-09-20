from __future__ import annotations

import pytest

from swirui import ListItem, ListView, TreeNode, TreeView
from swirui.core import AccessibilityRole
from swirui.rendering import Rect


def _items(count: int) -> tuple[ListItem, ...]:
    return tuple(
        ListItem(index, f"Item {index}", secondary=f"meta-{index}")
        for index in range(count)
    )


def test_list_view_preserves_multi_selection_by_stable_key() -> None:
    view = ListView(
        _items(4),
        bounds=Rect(0.0, 0.0, 260.0, 120.0),
        selection_mode="multiple",
    )
    view.select_indices((0, 2), primary_index=2, ensure_visible=False)

    view.set_items(
        (
            ListItem(2, "Item 2 updated"),
            ListItem(0, "Item 0 updated"),
            ListItem(4, "Item 4"),
        )
    )

    assert [item.key for item in view.selected_items] == [2, 0]
    assert view.selected_index == 0
    assert view.selected_item is not None
    assert view.selected_item.key == 2
    assert view.accessible_value_text == "2 items selected of 3"


def test_list_view_virtualizes_large_collection_and_accessibility() -> None:
    view = ListView(
        _items(2_000),
        bounds=Rect(0.0, 0.0, 320.0, 120.0),
        item_height=30.0,
        key="jobs",
    )
    view.select_index(1_999)

    assert view.selected_index == 1_999
    assert view.scroll_offset > 0.0
    assert len(view.visible_item_range) <= 4

    scene = view.build_scene_node()
    rows = [child for child in scene.children if child.key.startswith("jobs:row:")]
    assert len(rows) <= 4

    snapshot = view.accessibility_snapshot(focused=view)
    assert snapshot.role is AccessibilityRole.LIST
    assert snapshot.row_count == 2_000
    assert len(snapshot.children) <= 4
    assert any(child.selected for child in snapshot.children)


def test_list_view_rejects_duplicate_keys_and_skips_disabled_rows() -> None:
    with pytest.raises(ValueError, match="item keys must be unique"):
        ListView(
            (ListItem("same", "A"), ListItem("same", "B")),
            bounds=Rect(0.0, 0.0, 240.0, 120.0),
        )

    view = ListView(
        (
            ListItem(1, "Enabled"),
            ListItem(2, "Disabled", disabled=True),
            ListItem(3, "Enabled 2"),
        ),
        bounds=Rect(0.0, 0.0, 240.0, 120.0),
    )
    view.select_index(1)
    assert view.selected_index is None
    view.select_index(2)
    assert view.selected_item is not None
    assert view.selected_item.key == 3


def _tree() -> tuple[TreeNode, ...]:
    return (
        TreeNode(
            "root",
            "Root",
            (
                TreeNode("child-a", "Child A"),
                TreeNode(
                    "child-b",
                    "Child B",
                    (TreeNode("grandchild", "Grandchild"),),
                ),
            ),
        ),
        TreeNode("other", "Other"),
    )


def test_tree_view_expansion_is_virtualized_and_selection_is_stable() -> None:
    tree = TreeView(
        _tree(),
        bounds=Rect(0.0, 0.0, 320.0, 120.0),
        expanded_keys=("root",),
        key="tree",
    )
    assert [item.key for item in tree.items] == ["root", "child-a", "child-b", "other"]

    tree.select_index(2, ensure_visible=False)
    assert tree.selected_node is not None
    assert tree.selected_node.key == "child-b"

    tree.expand("child-b")
    assert [item.key for item in tree.items] == [
        "root",
        "child-a",
        "child-b",
        "grandchild",
        "other",
    ]
    assert tree.selected_node is not None
    assert tree.selected_node.key == "child-b"

    tree.collapse("root")
    assert [item.key for item in tree.items] == ["root", "other"]
    assert tree.selected_node is None


def test_tree_view_preserves_expansion_and_selection_across_replacement() -> None:
    tree = TreeView(
        _tree(),
        bounds=Rect(0.0, 0.0, 320.0, 160.0),
        expanded_keys=("root",),
    )
    tree.select_index(1, ensure_visible=False)

    tree.set_nodes(
        (
            TreeNode(
                "root",
                "Root v2",
                (
                    TreeNode("child-a", "Child A v2"),
                    TreeNode("child-c", "Child C"),
                ),
            ),
        )
    )

    assert "root" in tree.expanded_keys
    assert tree.selected_node is not None
    assert tree.selected_node.key == "child-a"
    assert tree.selected_node.label == "Child A v2"

    snapshot = tree.accessibility_snapshot(focused=tree)
    child = next(node for node in snapshot.children if node.name == "Child A v2")
    assert child.description == "Level 2"
    assert child.selected is True


def test_tree_view_rejects_duplicate_keys_across_branches() -> None:
    with pytest.raises(ValueError, match="globally unique"):
        TreeView(
            (
                TreeNode("root", "Root", (TreeNode("dup", "Child"),)),
                TreeNode("dup", "Duplicate"),
            ),
            bounds=Rect(0.0, 0.0, 240.0, 120.0),
        )
