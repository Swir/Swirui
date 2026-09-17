"""Retained Row/Column layout demo for SwirUI 0.5."""

from swirui import (
    App,
    Button,
    Column,
    CrossAxisAlignment,
    Insets,
    Label,
    Row,
    Window,
    mount,
)
from swirui.rendering import Color, Rect


def main() -> int:
    app = App("SwirUI layout")
    window = app.add_window(Window(title="SwirUI — Row + Column", width=960, height=620))

    title = Label(
        "SwirUI Layout Engine",
        bounds=Rect(0.0, 0.0, 320.0, 42.0),
        font_size=28.0,
        color=Color.from_hex("#62E5FF"),
    )
    subtitle = Label(
        "Retained Row/Column layout with constraints, grow and viewport reflow.",
        bounds=Rect(0.0, 0.0, 620.0, 28.0),
        color=Color.from_hex("#D7E8F2"),
    )

    actions = Row(
        bounds=Rect(0.0, 0.0, 760.0, 56.0),
        spacing=14.0,
        cross_alignment=CrossAxisAlignment.STRETCH,
    )
    primary = Button("Build", bounds=Rect(0.0, 0.0, 180.0, 48.0))
    secondary = Button("Preview", bounds=Rect(0.0, 0.0, 180.0, 48.0))
    primary.set_layout_grow(1.0)
    secondary.set_layout_grow(1.0)
    actions.add(primary, secondary)

    root = Column(
        bounds=Rect(0.0, 0.0, 1.0, 1.0),
        fill_viewport=True,
        padding=Insets.symmetric(horizontal=64.0, vertical=56.0),
        spacing=24.0,
        cross_alignment=CrossAxisAlignment.CENTER,
    )
    root.add(title, subtitle, actions)
    mount(window, root)

    app.start()
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
