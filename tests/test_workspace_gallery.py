import runpy
from pathlib import Path

from swirui import FUTURE_LIGHT, Window, mount
from swirui.platforms import NativeWindowHandle, PlatformEvent, PlatformEventKind

Workspace = runpy.run_path(str(Path(__file__).parents[1] / "examples/workspace_gallery.py"))[
    "Workspace"
]


def test_workspace_filters_navigates_and_switches_theme_with_persistent_state():
    workspace = Workspace()
    window = Window(width=1280, height=840)
    runtime = mount(window, workspace)
    try:
        workspace.search.value = "aurora"
        assert len(workspace.grid.rows) == 10
        workspace.grid.begin_edit(2, "name")
        workspace.grid.set_edit_text("My unfinished project")
        workspace.mode.emit("click")
        assert workspace.theme == FUTURE_LIGHT and workspace.search.value == "aurora"
        assert workspace.grid.editing_cell == (2, "name", "My unfinished project")
        workspace.sidebar.select_key("assets")
        assert workspace.tabs.selected_key == "assets" and workspace.assets.visible
        assert not workspace.search.visible and "Home / End" in workspace.hint.text
        window.focus_component(workspace.assets)
        window._apply_platform_event(
            PlatformEvent(PlatformEventKind.KEY_DOWN, NativeWindowHandle(1), key_code=0x23)
        )
        assert workspace.tabs.selected_key == "assets"
        assert workspace.assets.selected_index == 1999
        offset = workspace.assets.scroll_offset
        workspace.tabs.select_key("files")
        assert workspace.sidebar.selected_key == "files"
        workspace.tabs.select_key("assets")
        assert workspace.assets.selected_index == 1999 and workspace.assets.scroll_offset == offset
    finally:
        runtime.unmount()


def test_workspace_command_palette_restores_focus_and_invokes_last_asset_bookmark():
    workspace = Workspace()
    window = Window(width=1280, height=840)
    runtime = mount(window, workspace)
    try:
        # Window-wide shortcuts must also work before any child has focus.
        assert window.focused_component is None
        window._apply_platform_event(
            PlatformEvent(
                PlatformEventKind.KEY_DOWN, NativeWindowHandle(1), key_code=0x4B, ctrl=True
            )
        )
        assert workspace.command_dialog.is_open and window.focused_component is workspace.palette
        for char in "open asset":
            window._apply_platform_event(
                PlatformEvent(PlatformEventKind.TEXT_INPUT, NativeWindowHandle(1), text=char)
            )
        assert len(workspace.palette.filtered_items) == 50
        for code in (0x23, 0x0D):
            window._apply_platform_event(
                PlatformEvent(PlatformEventKind.KEY_DOWN, NativeWindowHandle(1), key_code=code)
            )
        assert workspace.assets.selected_index == 1960 and workspace.tabs.selected_key == "assets"
        assert (
            not workspace.command_dialog.is_open and window.focused_component is workspace.commands
        )
        workspace.open_commands()
        window._apply_platform_event(
            PlatformEvent(PlatformEventKind.KEY_DOWN, NativeWindowHandle(1), key_code=0x09)
        )
        assert window.focused_component is workspace.palette
        window._apply_platform_event(
            PlatformEvent(PlatformEventKind.KEY_DOWN, NativeWindowHandle(1), key_code=0x1B)
        )
        assert (
            not workspace.command_dialog.is_open and window.focused_component is workspace.commands
        )
    finally:
        runtime.unmount()
