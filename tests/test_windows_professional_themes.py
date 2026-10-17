"""Professional palette and focus colors verified in the real native GPU scene."""

import sys

import pytest

from swirui import (
    FUTURE_DARK,
    FUTURE_LIGHT,
    App,
    DataGrid,
    DataGridColumn,
    ListItem,
    ListView,
    NavigationItem,
    Panel,
    Sidebar,
    TabItem,
    Tabs,
    TreeNode,
    TreeView,
    Window,
    mount,
)
from swirui.platforms.windows import Win32PlatformBackend
from swirui.rendering import Rect, WgpuRenderer


@pytest.mark.skipif(sys.platform != "win32", reason="Real Windows GPU required")
def test_professional_palette_and_focus_present_without_replacing_controls():
    root = Panel(bounds=Rect(0, 0, 900, 480), theme=FUTURE_DARK)
    nav = Sidebar([NavigationItem("one", "One")], bounds=Rect(20, 20, 180, 200))
    tabs = Tabs(
        [TabItem("one", "One", Panel(bounds=Rect(0, 0, 400, 200)))], bounds=Rect(240, 20, 400, 200)
    )
    view = ListView([ListItem(i, f"Item {i}") for i in range(20)], bounds=Rect(20, 260, 240, 180))
    view.select_index(1)
    tree = TreeView(
        [TreeNode("root", "Root", (TreeNode("child", "Child"),))],
        expanded_keys=["root"],
        bounds=Rect(280, 260, 220, 180),
    )
    tree.select_index(1)
    grid = DataGrid(
        [DataGridColumn("name", "Name", width=330)],
        [{"name": f"Project {i}"} for i in range(20)],
        bounds=Rect(540, 260, 330, 180),
    )
    grid.select_row(1)
    controls = [nav, tabs, view, tree, grid]
    root.add(*controls)
    renderer = WgpuRenderer()
    app = App(platform_backend=Win32PlatformBackend(), renderer=renderer)
    window = app.add_window(Window(width=900, height=480))
    mount(window, root)
    window.focus_component(grid)
    try:
        app.start()
        assert window.native_handle is not None
        context = renderer._contexts[window.native_handle.value]
        for theme in (FUTURE_LIGHT, FUTURE_DARK):
            root.theme = theme
            scheduler = app._frame_schedulers[window]
            app.render_pending(scheduler.stats.last_frame_time + 2 * scheduler.frame_interval)
            width, _height, pixels = context.read_scene_rgba()
            for x, y, role in (
                (100, 23, "selection"),
                (21, 40, "accent"),
                (340, 23, "selection"),
                (200, 303, "selection"),
                (450, 303, "selection"),
                (800, 338, "selection"),
                (800, 265, "raised"),
                (541, 350, "focus"),
            ):
                expected = theme.text_color(role)
                offset = (round(y * window.scale) * width + round(x * window.scale)) * 4
                assert tuple(pixels[offset : offset + 3]) == pytest.approx(
                    (round(expected.r * 255), round(expected.g * 255), round(expected.b * 255)),
                    abs=1,
                ), (x, y, role)
            assert (
                window.focused_component is grid
                and grid.selected_index == view.selected_index == tree.selected_index == 1
            )
            assert renderer._contexts[window.native_handle.value] is context
            assert root.children == controls
    finally:
        app.stop()
