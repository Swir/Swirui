"""Interactive retained modal and notification demo for SwirUI 0.4."""

from swirui import App, Button, Component, Label, Modal, Panel, Toast, Window, mount
from swirui.rendering import Color, Rect


def main() -> int:
    app = App("SwirUI overlays")
    window = app.add_window(Window(title="SwirUI — Modal + Toast", width=980, height=620))
    root = Component("Overlay demo")

    root.add(
        Label(
            "Modal blocks background input. Click the backdrop or press Esc to dismiss.",
            key="instructions",
            bounds=Rect(48.0, 28.0, 820.0, 30.0),
            font_size=16.0,
            color=Color.from_hex("#D8F4FF"),
        ),
        Button(
            "Background action",
            key="background-action",
            bounds=Rect(48.0, 92.0, 210.0, 48.0),
        ),
    )

    dialog_content = Panel(
        key="dialog-content",
        bounds=Rect(0.0, 0.0, 430.0, 250.0),
        background=Color.from_hex("#07111C"),
        border_width=0.0,
    )
    dialog_content.add(
        Label(
            "SwirUI retained modal",
            key="dialog-title",
            bounds=Rect(30.0, 28.0, 320.0, 34.0),
            font_size=22.0,
            color=Color.from_hex("#F4FAFF"),
        ),
        Label(
            "GPU-backed overlay, routed input and accessible dialog semantics.",
            key="dialog-copy",
            bounds=Rect(30.0, 82.0, 360.0, 54.0),
            font_size=14.0,
            color=Color.from_hex("#8DA8B8"),
        ),
        Button(
            "Confirm",
            key="dialog-confirm",
            bounds=Rect(30.0, 166.0, 160.0, 48.0),
        ),
    )

    modal = Modal(
        key="demo-modal",
        bounds=Rect(0.0, 0.0, 980.0, 620.0),
        dialog_bounds=Rect(275.0, 175.0, 430.0, 250.0),
        content=dialog_content,
        accessible_name="SwirUI demo dialog",
    )
    toast = Toast(
        "The notification surface uses the same retained shaped-text GPU path.",
        key="demo-toast",
        title="Overlay engine ready",
        kind="success",
        bounds=Rect(600.0, 38.0, 330.0, 94.0),
        duration_seconds=None,
    )
    root.add(modal, toast)

    mount(window, root)
    return app.run()


if __name__ == "__main__":
    raise SystemExit(main())
