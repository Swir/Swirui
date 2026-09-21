"""ContextMenu and CommandPalette demo for the retained SwirUI command layer."""

from swirui import App, CommandItem, CommandPalette, ContextMenu, Window, mount
from swirui.rendering import Rect


def main() -> None:
    commands = (
        CommandItem("open", "Open workspace", "Ctrl+O"),
        CommandItem("save", "Save document", "Ctrl+S"),
        CommandItem("grid", "Toggle Grid", "Ctrl+G"),
        CommandItem("export", "Export image", "Ctrl+E"),
    )

    app = App("SwirUI Context Commands")
    palette_window = app.add_window(
        Window(title="SwirUI Command Palette", width=760, height=420)
    )
    context_window = app.add_window(
        Window(title="SwirUI Context Menu", width=560, height=320)
    )

    palette = CommandPalette(
        commands,
        bounds=Rect(120.0, 70.0, 500.0, 260.0),
        key="demo-palette",
        dismiss_on_invoke=False,
    )
    menu = ContextMenu(
        commands,
        bounds=Rect(80.0, 64.0, 280.0, 156.0),
        key="demo-context",
        dismiss_on_invoke=False,
    )

    palette.on("command_invoked", lambda event: print("Palette:", event.data["key"]))
    menu.on("command_invoked", lambda event: print("Context menu:", event.data["key"]))

    mount(palette_window, palette)
    mount(context_window, menu)
    app.run()


if __name__ == "__main__":
    main()
