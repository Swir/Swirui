"""PropertyGrid and Inspector demo for retained professional SwirUI tooling."""

from swirui import App, Inspector, PropertyItem, Window, mount
from swirui.rendering import Rect


def main() -> None:
    app = App("SwirUI Inspector")
    window = app.add_window(Window(title="SwirUI Property Inspector", width=760, height=460))
    inspector = Inspector(
        (
            PropertyItem("title", "Title", "Hero panel", category="General"),
            PropertyItem("visible", "Visible", True, category="General"),
            PropertyItem("opacity", "Opacity", 0.86, category="Appearance"),
            PropertyItem(
                "object-id",
                "Object ID",
                "panel-hero",
                category="Metadata",
                read_only=True,
            ),
        ),
        bounds=Rect(80.0, 70.0, 560.0, 220.0),
        key="demo-inspector",
    )
    inspector.on(
        "property_changed",
        lambda event: print(event.data["key"], "=", event.data["value"]),
    )
    mount(window, inspector)
    app.run()


if __name__ == "__main__":
    main()
