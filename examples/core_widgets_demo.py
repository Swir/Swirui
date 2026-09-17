"""Interactive 0.4 core-widget demo using the retained GPU renderer path."""

from swirui import App, Button, Component, IconButton, Label, Window, mount
from swirui.rendering import Color, Rect


def main() -> int:
    app = App("SwirUI Core Widgets")
    window = app.add_window(Window(title="SwirUI — Core Widgets", width=760, height=420))

    root = Component("Core widgets demo")
    title = Label(
        "SwirUI 0.4 — retained core widgets",
        bounds=Rect(36.0, 32.0, 620.0, 42.0),
        font_size=28.0,
        color=Color.from_hex("#62E5FF"),
    )
    status = Label(
        "Use pointer, Tab, Enter or Space.",
        bounds=Rect(36.0, 92.0, 560.0, 30.0),
        font_size=18.0,
        color=Color.from_hex("#F4FAFF"),
    )
    action = Button(
        "Activate SwirUI",
        bounds=Rect(36.0, 154.0, 220.0, 54.0),
        accessible_description="Updates the retained status label.",
    )
    favorite = IconButton(
        "★",
        bounds=Rect(276.0, 154.0, 54.0, 54.0),
        accessible_name="Favorite",
        font_size=24.0,
    )

    def activate(_event: object) -> None:
        status.text = "Button activated through routed SwirUI input."

    def favorite_clicked(_event: object) -> None:
        status.text = "IconButton activated — keyboard focus remains native."

    action.on("click", activate)
    favorite.on("click", favorite_clicked)
    root.add(title, status, action, favorite)
    mount(window, root)

    return app.run()


if __name__ == "__main__":
    raise SystemExit(main())
