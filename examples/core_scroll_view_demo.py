"""Interactive retained ScrollView demo for SwirUI 0.4."""

from swirui import App, Button, Component, Label, ScrollView, Window, mount
from swirui.rendering import Color, Rect


def main() -> int:
    app = App("SwirUI ScrollView")
    window = app.add_window(Window(title="SwirUI — ScrollView", width=760, height=520))
    root = Component("ScrollView demo")

    root.add(
        Label(
            "ScrollView — click the viewport, then use arrows / Page Up / Page Down",
            key="instructions",
            bounds=Rect(48.0, 24.0, 650.0, 30.0),
            font_size=16.0,
            color=Color.from_hex("#D8F4FF"),
        )
    )

    scroll = ScrollView(
        key="demo-scroll",
        bounds=Rect(48.0, 72.0, 520.0, 360.0),
        content_height=760.0,
        accessible_name="Core widget examples",
    )
    for index in range(10):
        y = 18.0 + (index * 70.0)
        scroll.add(
            Button(
                f"Retained GPU item {index + 1}",
                key=f"item-{index + 1}",
                bounds=Rect(18.0, y, 330.0, 48.0),
            ),
            Label(
                f"content y = {y:.0f} DIP",
                key=f"detail-{index + 1}",
                bounds=Rect(366.0, y + 12.0, 130.0, 24.0),
                font_size=13.0,
                color=Color.from_hex("#8DA8B8"),
            ),
        )

    root.add(scroll)
    mount(window, root)
    return app.run()


if __name__ == "__main__":
    raise SystemExit(main())
