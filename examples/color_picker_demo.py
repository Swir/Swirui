"""Interactive retained ColorPicker demo."""

from swirui import App, ColorPicker, Panel, Window, mount
from swirui.rendering import Color, Rect


def main() -> None:
    app = App("SwirUI Color Picker")
    window = app.add_window(Window(title="SwirUI Professional Color Picker", width=760, height=500))
    root = Panel(bounds=Rect(0.0, 0.0, 760.0, 500.0), key="color-picker-demo")
    picker = ColorPicker(
        bounds=Rect(80.0, 70.0, 600.0, 330.0),
        value=Color.from_hex("#0088FFFF"),
        key="demo-color-picker",
    )
    picker.on(
        "color_changed",
        lambda event: print("Color:", event.data["hex_value"]),
    )
    root.add(picker)
    mount(window, root)
    app.run()


if __name__ == "__main__":
    main()
