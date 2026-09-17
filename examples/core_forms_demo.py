"""Interactive 0.4 retained input and selection-widget demo."""

from swirui import (
    App,
    Checkbox,
    Component,
    Input,
    Label,
    PasswordInput,
    RadioButton,
    Switch,
    TextArea,
    Window,
    mount,
)
from swirui.rendering import Color, Rect


def main() -> int:
    app = App("SwirUI Core Forms")
    window = app.add_window(Window(title="SwirUI — Core Forms", width=860, height=560))
    root = Component("Core forms demo")

    title = Label(
        "SwirUI 0.4 — retained form controls",
        bounds=Rect(36.0, 28.0, 700.0, 40.0),
        font_size=28.0,
        color=Color.from_hex("#62E5FF"),
    )
    name = Input(
        bounds=Rect(36.0, 92.0, 320.0, 46.0),
        placeholder="Display name",
        accessible_name="Display name",
    )
    password = PasswordInput(
        bounds=Rect(376.0, 92.0, 320.0, 46.0),
        placeholder="Password",
    )
    notes = TextArea(
        bounds=Rect(36.0, 158.0, 660.0, 150.0),
        placeholder="Notes — Enter inserts a new line",
        accessible_name="Notes",
    )
    effects = Checkbox(
        "Enable GPU effects",
        bounds=Rect(36.0, 336.0, 220.0, 34.0),
        checked=True,
    )
    performance = RadioButton(
        "Performance",
        group="quality",
        bounds=Rect(36.0, 386.0, 180.0, 34.0),
    )
    quality = RadioButton(
        "Quality",
        group="quality",
        bounds=Rect(228.0, 386.0, 150.0, 34.0),
        checked=True,
    )
    telemetry = Switch(
        bounds=Rect(36.0, 446.0, 56.0, 30.0),
        accessible_name="Frame telemetry",
    )
    telemetry_label = Label(
        "Frame telemetry",
        bounds=Rect(106.0, 448.0, 220.0, 28.0),
        font_size=16.0,
    )
    status = Label(
        "Use pointer, Tab/Shift+Tab, keyboard editing, Space and Enter.",
        bounds=Rect(36.0, 504.0, 760.0, 28.0),
        font_size=15.0,
        color=Color.from_hex("#8DA8B8"),
    )

    root.add(
        title,
        name,
        password,
        notes,
        effects,
        performance,
        quality,
        telemetry,
        telemetry_label,
        status,
    )
    mount(window, root)
    return app.run()


if __name__ == "__main__":
    raise SystemExit(main())
