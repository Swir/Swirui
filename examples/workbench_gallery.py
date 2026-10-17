"""Docked editor, inspector and application-owned console; no shell execution."""

import argparse

from swirui import (
    FUTURE_DARK,
    FUTURE_LIGHT,
    App,
    Button,
    CodeEditor,
    DockPane,
    DockWorkspace,
    Inspector,
    Label,
    Panel,
    PropertyItem,
    Terminal,
    TextArea,
    ThemePackage,
    Window,
    mount,
    state_transaction,
)
from swirui.core import Event
from swirui.rendering import Rect, WgpuRenderer


def main(theme_package: ThemePackage | None = None) -> int:
    variants = [FUTURE_DARK, FUTURE_LIGHT]
    if theme_package is not None:
        variants = [theme_package.default] + [
            value for key, value in theme_package.themes.items()
            if key != theme_package.default_theme
        ]
    appearance_index = 0
    root = Panel(bounds=Rect(0, 0, 1200, 760), theme=variants[0])
    heading = Label("A place to make things.", bounds=Rect(32, 80, 1120, 64), font_size=40)
    editor = CodeEditor(
        'from swirui import App, Button\n\n'
        'def build():\n'
        '    title = "A fresh start"\n'
        '    # Start small. Make it yours.\n'
        '    return title\n',
        bounds=Rect(0, 0, 1, 1), language="python", font_size=18, padding=14,
    )
    notes = TextArea(
        "Keep the useful ideas close.\n\nYour notes stay here while switching tabs.",
        bounds=Rect(0, 0, 1, 1), font_size=18, padding=14,
    )
    inspector = Inspector([
        PropertyItem("title", "Title", "A place to make things.", category="App"),
        PropertyItem("numbers", "Line numbers", True, category="Code"),
        PropertyItem("minimap", "Minimap", False, category="Code"),
        PropertyItem("mode", "Mode", "Local example", category="App", read_only=True),
    ], bounds=Rect(0, 0, 1, 1), label_fraction=0.46)
    terminal = Terminal(bounds=Rect(0, 0, 1, 1), prompt="swir > ", font_size=16, padding=14)
    terminal.writeln("\x1b[32mReady.\x1b[0m Your workspace is local.")
    terminal.writeln("Try help, status or clear. No shell commands are executed.")
    workspace = DockWorkspace([
        DockPane("properties", "Properties", inspector, dock="left", extent=350),
        DockPane("console", "Console", terminal, dock="bottom", extent=190),
        DockPane("code", "Code", editor), DockPane("notes", "Notes", notes),
    ], bounds=Rect(32, 164, 1136, 536), active_key="code", header_height=36)
    appearance = Button("Light appearance", bounds=Rect(928, 24, 240, 44))
    if theme_package is not None:
        appearance.text = "Next appearance"
        appearance.enabled = len(variants) > 1
        terminal.writeln(f"Appearance package: {theme_package.name}")

    def switch_appearance() -> None:
        nonlocal appearance_index
        with state_transaction():
            appearance_index = (appearance_index + 1) % len(variants)
            root.theme = variants[appearance_index]
            if theme_package is None:
                appearance.text = (
                    "Dark appearance" if appearance_index == 1 else "Light appearance"
                )

    def property_changed(event: Event) -> None:
        if event.data["key"] == "title":
            heading.text = str(event.data["value"])
        elif event.data["key"] == "numbers":
            editor.show_line_numbers = bool(event.data["value"])
        elif event.data["key"] == "minimap":
            editor.show_minimap = bool(event.data["value"])

    def submitted(event: Event) -> None:
        command = event.data["command"].strip().lower()
        if command == "clear":
            terminal.clear_buffer()
        elif command == "status":
            terminal.writeln("\x1b[32mReady\x1b[0m / editor, notes and inspector retained.")
        elif command == "help":
            terminal.writeln("status: workspace state / clear: clear local console")
        elif command:
            terminal.writeln("\x1b[33mTry help, status or clear.\x1b[0m")

    appearance.on("click", lambda _: switch_appearance())
    inspector.on("property_changed", property_changed)
    terminal.on("submitted", submitted)
    root.add(
        Label("swir / workbench", bounds=Rect(32, 28, 600, 36), font_size=20),
        heading, workspace, appearance,
        Label("Tab to explore. Enter to edit a property. Switch Code and Notes above the editor.",
              bounds=Rect(32, 720, 1136, 30), font_size=15),
    )
    window = Window(title="SwirUI — Workbench", width=1200, height=760,
                    min_width=1200, min_height=760)
    mount(window, root)
    window.focus_component(editor)
    app = App("SwirUI Workbench", renderer=WgpuRenderer())
    app.add_window(window)
    return app.run()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--theme-package", help="UTF-8 SwirUI theme-package JSON file")
    args = parser.parse_args()
    package = None
    if args.theme_package:
        try:
            package = ThemePackage.load(args.theme_package)
        except (OSError, ValueError) as error:
            parser.error(str(error))
    raise SystemExit(main(package))
