"""Live theme changes must preserve professional workspace state and bounded scenes."""

from dataclasses import replace

import pytest

from swirui import (
    FUTURE_DARK,
    FUTURE_LIGHT,
    Component,
    DataGrid,
    DataGridColumn,
    Input,
    ListItem,
    ListView,
    NavigationItem,
    NavigationRail,
    Panel,
    Sidebar,
    TabItem,
    Tabs,
    TreeNode,
    TreeView,
    Window,
    mount,
)
from swirui.rendering import Color, Rect, SceneNodeKind

BOUNDS = Rect(0, 0, 320, 180)


def make_widget(kind, **kwargs):
    if kind in (NavigationRail, Sidebar):
        return kind(
            [NavigationItem("one", "One"), NavigationItem("two", "Two", disabled=True)],
            bounds=BOUNDS,
            **kwargs,
        )
    if kind is Tabs:
        return Tabs(
            [
                TabItem("one", "One", Panel(bounds=BOUNDS)),
                TabItem("two", "Two", Panel(bounds=BOUNDS), disabled=True),
            ],
            bounds=BOUNDS,
            **kwargs,
        )
    if kind is TreeView:
        return TreeView([TreeNode("one", "One"), TreeNode("two", "Two")], bounds=BOUNDS, **kwargs)
    if kind is ListView:
        return ListView(
            [ListItem("one", "One", "Metadata"), ListItem("two", "Two")], bounds=BOUNDS, **kwargs
        )
    return DataGrid(
        [DataGridColumn("name", "Name", width=300)],
        [{"name": "One"}, {"name": "Two"}],
        bounds=BOUNDS,
        **kwargs,
    )


@pytest.mark.parametrize("kind", [NavigationRail, Sidebar, Tabs, ListView, TreeView, DataGrid])
def test_professional_controls_support_inheritance_local_scope_and_legacy_reset(kind):
    control = make_widget(kind)
    legacy = [
        (n.key, n.fill, n.font_family, n.corner_radius) for n in control.build_scene_node().walk()
    ]
    root = Component(theme=FUTURE_DARK).add(control)
    for theme in (FUTURE_LIGHT, FUTURE_DARK):
        root.theme = theme
        node = control.build_scene_node()
        assert node.fill == theme.surface_color("surface")
        assert node.corner_radius.top_left == theme.control_radius
        assert all(
            n.font_family == theme.font_family for n in node.walk() if n.kind is SceneNodeKind.TEXT
        )
    control.theme = FUTURE_LIGHT
    root.theme = None
    assert control.build_scene_node().fill == FUTURE_LIGHT.surface_color("surface")
    control.theme = None
    assert [
        (n.key, n.fill, n.font_family, n.corner_radius) for n in control.build_scene_node().walk()
    ] == legacy


@pytest.mark.parametrize("kind", [NavigationRail, Tabs, ListView, TreeView, DataGrid])
def test_explicit_style_overrides_and_font_normalization_survive_switch(kind):
    color = Color(0.2, 0.3, 0.4)
    widget = make_widget(
        kind,
        theme=FUTURE_DARK,
        background=color,
        foreground=color,
        corner_radius=0,
        font_family=" Arial ",
    )
    widget.theme = FUTURE_LIGHT
    node = widget.build_scene_node()
    assert node.fill == color and node.corner_radius.top_left == 0
    assert all(n.font_family == "Arial" for n in node.walk() if n.kind is SceneNodeKind.TEXT)
    assert any(n.fill == color for n in node.walk() if n.kind is SceneNodeKind.TEXT)


@pytest.mark.parametrize("kind", [NavigationRail, Sidebar, Tabs, ListView, TreeView, DataGrid])
def test_keyboard_focus_adds_bounded_noninteractive_frame_and_repaints(kind):
    widget = make_widget(kind, theme=FUTURE_DARK)
    window = Window(width=400, height=240)
    runtime = mount(window, widget)
    updates = []
    window.on("scene_changed", updates.append)
    try:
        window.focus_component(widget)
        assert len(updates) == 1
        for theme in (FUTURE_LIGHT, FUTURE_DARK):
            widget.theme = theme
            frames = [n for n in widget.build_scene_node().walk() if ":theme-focus:" in n.key]
            assert len(frames) == 4
            if kind in (NavigationRail, Sidebar, Tabs):
                header_height = widget.header_height if kind is Tabs else widget.item_height
                assert (
                    max(frame.bounds.bottom for frame in frames) <= widget.bounds.y + header_height
                )
            assert all(
                n.fill == theme.surface_color("focus") and not n.hit_testable for n in frames
            )
        window.focus_component(None)
        assert not any(":theme-focus:" in n.key for n in widget.build_scene_node().walk())
    finally:
        runtime.unmount()


def test_large_list_and_tree_keep_scroll_selection_expansion_and_bounded_rendering():
    view = ListView(
        [ListItem(i, f"Item {i}", "Ready") for i in range(10_000)],
        bounds=BOUNDS,
        selection_mode="multiple",
    )
    view.select_indices([100, 9999], primary_index=9999)
    tree = TreeView(
        [TreeNode("root", "Project", tuple(TreeNode(i, f"File {i}") for i in range(2000)))],
        expanded_keys=["root"],
        bounds=BOUNDS,
    )
    tree.select_index(1990)
    root = Component(theme=FUTURE_DARK).add(view, tree)
    before = (
        view.selected_indices,
        view.scroll_offset,
        tree.selected_node,
        tree.expanded_keys,
        tree.scroll_offset,
    )
    for theme in (FUTURE_LIGHT, FUTURE_DARK):
        root.theme = theme
        assert (
            view.selected_indices,
            view.scroll_offset,
            tree.selected_node,
            tree.expanded_keys,
            tree.scroll_offset,
        ) == before
        assert len(list(view.build_scene_node().walk())) < 30
        assert len(list(tree.build_scene_node().walk())) < 25
        selected = next(n for n in view.build_scene_node().walk() if n.key.endswith(":row:9999"))
        assert selected.fill == theme.surface_color("selection")
        assert all(n.fill == theme.text_color("text") for n in selected.children)


def test_grid_theme_preserves_filter_sort_multiselection_two_axis_scroll_and_edit_buffer():
    grid = DataGrid(
        [DataGridColumn("id", "ID", width=80), DataGridColumn("name", "Name", width=320)],
        [{"id": i, "name": f"Project {i}"} for i in range(2000)],
        bounds=BOUNDS,
        row_key="id",
        selection_mode="multiple",
        editable_columns=["name"],
    )

    def predicate(row):
        return row["id"] % 2 == 0

    grid.set_filter(predicate)
    grid.sort_by("id", descending=True)
    grid.select_rows([30, 40], primary_index=40)
    grid.begin_edit(40, "name")
    grid.set_edit_text("An unfinished edit")
    grid.scroll_horizontal_by(60)
    root = Component(theme=FUTURE_DARK).add(grid)
    window = Window(width=400, height=240)
    runtime = mount(window, root)
    window.focus_component(grid)
    before = (
        grid.rows,
        grid.selected_indices,
        grid.scroll_offset,
        grid.horizontal_scroll_offset,
        grid.editing_cell,
    )
    changes = []
    grid.on("cell_edit_cancelled", changes.append)
    grid.on("selection_changed", changes.append)
    try:
        root.theme = FUTURE_LIGHT
        assert window.focused_component is grid
        assert (
            grid.rows,
            grid.selected_indices,
            grid.scroll_offset,
            grid.horizontal_scroll_offset,
            grid.editing_cell,
        ) == before
        assert (
            grid.row_filter is predicate and grid.sort_column_key == "id" and grid.sort_descending
        )
        assert changes == []
        assert len(list(grid.build_scene_node().walk())) < 50
        editor = next(n for n in grid.build_scene_node().walk() if n.key.endswith(":editor:text"))
        assert editor.text == "An unfinished edit│" and editor.fill == FUTURE_LIGHT.text_color(
            "text"
        )
    finally:
        runtime.unmount()


def test_tabs_retheme_hidden_content_without_switching_page_or_replacing_text():
    first, second = Input("First draft", bounds=BOUNDS), Input("Second draft", bounds=BOUNDS)
    tabs = Tabs(
        [TabItem("first", "First", first), TabItem("second", "Second", second)],
        bounds=BOUNDS,
        selected_key="second",
        theme=FUTURE_DARK,
    )
    changes = []
    tabs.on("selection_changed", changes.append)
    tabs.theme = replace(FUTURE_LIGHT, font_family="Arial")
    assert tabs.selected_key == "second" and not first.visible and second.visible
    assert first.value == "First draft" and second.value == "Second draft"
    assert first.effective_theme == second.effective_theme == tabs.theme
    assert first.build_scene_node().fill == FUTURE_LIGHT.surface_color("raised")
    assert changes == []


@pytest.mark.parametrize("width", [48, 180, 320])
def test_list_primary_and_secondary_text_have_separate_bounds(width):
    view = ListView(
        [
            ListItem(
                "item", "A long document title that must not overlap metadata", "Modified today"
            )
        ],
        bounds=Rect(0, 0, width, 50),
        theme=FUTURE_LIGHT,
    )
    texts = [n for n in view.build_scene_node().walk() if n.kind is SceneNodeKind.TEXT]
    label = next(n for n in texts if n.key.endswith(":label"))
    secondary = next(n for n in texts if n.key.endswith(":secondary"))
    assert label.bounds.right <= secondary.bounds.x
    assert label.bounds.width >= 0 and secondary.bounds.right <= width
