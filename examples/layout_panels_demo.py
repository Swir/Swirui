"""Retained Stack, Grid and Wrap layout demo for SwirUI 0.5."""

from swirui import (
    App,
    Button,
    Grid,
    Insets,
    Label,
    Stack,
    Window,
    Wrap,
    mount,
)
from swirui.rendering import Color, Rect


def main() -> int:
    app = App("SwirUI layout panels")
    window = app.add_window(Window(title="SwirUI — Grid + Wrap + Stack", width=1040, height=680))

    badges = Wrap(
        bounds=Rect(0.0, 0.0, 1.0, 1.0),
        spacing=10.0,
        run_spacing=10.0,
        padding=12.0,
    )
    for label in ("GPU-first", "Retained", "Rust + wgpu", "HiDPI", "Python API"):
        badges.add(Button(label, bounds=Rect(0.0, 0.0, 150.0, 42.0)))

    hero = Stack(
        bounds=Rect(0.0, 0.0, 1.0, 1.0),
        padding=18.0,
    )
    hero.add(
        Label(
            "SwirUI 0.5 Layout Engine",
            bounds=Rect(0.0, 0.0, 360.0, 44.0),
            font_size=28.0,
            color=Color.from_hex("#62E5FF"),
        )
    )

    grid = Grid(
        bounds=Rect(0.0, 0.0, 1.0, 1.0),
        fill_viewport=True,
        columns=2,
        column_weights=(2.0, 3.0),
        column_spacing=22.0,
        row_spacing=18.0,
        padding=Insets.symmetric(horizontal=56.0, vertical=48.0),
    )
    grid.add(hero, badges)
    mount(window, grid)

    app.start()
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
