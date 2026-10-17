"""Editable notes and code using the native multiline text path."""

from swirui import (
    FUTURE_DARK,
    FUTURE_LIGHT,
    App,
    Autocomplete,
    Button,
    CodeEditor,
    Label,
    Panel,
    TextArea,
    Window,
    mount,
    state_transaction,
)
from swirui.rendering import Rect, WgpuRenderer


def main() -> int:
    root = Panel(bounds=Rect(0, 0, 1200, 760), theme=FUTURE_DARK)
    notes = TextArea(
        "A little space for a big idea.\n\n"
        "Build something clear, useful and beautiful.\n"
        "Every letter should feel at home.\n\n"
        "Zażółć gęślą jaźń. Café, déjà vu.\n\n"
        "Narrow letters: iiiii   Wide letters: WWWWW\n"
        "A longer line stays intact as the caret moves across the page, "
        "keeping every word in the right place.",
        bounds=Rect(32, 190, 548, 480),
        font_size=21,
        padding=18,
        accessible_name="Notes",
    )
    code = CodeEditor(
        "from swirui import App, Button\n\n"
        "def create_something():\n"
        '    title = "A fresh start"\n'
        '    palette = ["violet", "sky", "mint"]\n'
        "    # Small details. Better experiences.\n"
        "    for color in palette:\n"
        '        print(f"Hello, {color}!")\n\n'
        "    return title\n",
        bounds=Rect(604, 190, 564, 480),
        language="python",
        font_size=18,
        show_minimap=True,
        minimap_width=36,
        padding=16,
        accessible_name="Code",
    )
    ideas = Autocomplete(
        bounds=Rect(604, 24, 304, 44),
        placeholder="Find an idea...",
        items=("Build a new workspace", "Design a calmer canvas", "Explore a fresh direction"),
        minimum_prefix_length=0,
        open_on_focus=True,
        accessible_name="Ideas",
        z_index=20,
    )
    appearance = Button("Light appearance", bounds=Rect(928, 24, 240, 44))

    def toggle_appearance() -> None:
        with state_transaction():
            root.theme = FUTURE_LIGHT if root.theme == FUTURE_DARK else FUTURE_DARK
            appearance.text = (
                "Dark appearance" if root.theme == FUTURE_LIGHT else "Light appearance"
            )

    appearance.on("click", lambda _: toggle_appearance())
    root.add(
        Label("swir / compose", bounds=Rect(32, 26, 400, 34), font_size=20),
        Label("Make room for ideas.", bounds=Rect(32, 78, 900, 64), font_size=42),
        Label("Notes", bounds=Rect(32, 150, 300, 30), font_size=18),
        Label("Code", bounds=Rect(604, 150, 300, 30), font_size=18),
        notes,
        code,
        ideas,
        appearance,
        Label(
            "Click to write. Shift + arrows to select. Ctrl + Z to undo in code.",
            bounds=Rect(32, 700, 1100, 32),
            font_size=15,
        ),
    )
    window = Window(
        title="SwirUI — Compose", width=1200, height=760, min_width=1200, min_height=760
    )
    mount(window, root)
    notes.select(0, 0)
    window.focus_component(notes)
    app = App("SwirUI Compose", renderer=WgpuRenderer())
    app.add_window(window)
    return app.run()


if __name__ == "__main__":
    raise SystemExit(main())
