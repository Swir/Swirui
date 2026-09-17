"""Interactive retained Checkbox / RadioButton / Switch demo."""

from swirui import App, Checkbox, Component, Label, RadioButton, Switch, Window, mount
from swirui.rendering import Color, Rect

app = App("SwirUI retained toggles")
window = app.add_window(Window(title="SwirUI — Core toggles", width=720, height=500))
root = Component("toggle-demo")

heading = Label(
    "SwirUI 0.4 — retained toggle controls",
    bounds=Rect(42.0, 32.0, 560.0, 38.0),
    font_size=24.0,
    color=Color.from_hex("#62E5FF"),
)
telemetry = Checkbox(
    "Enable renderer telemetry",
    key="telemetry",
    bounds=Rect(42.0, 100.0, 330.0, 42.0),
)
quality_balanced = RadioButton(
    "Balanced quality",
    key="balanced",
    bounds=Rect(42.0, 166.0, 300.0, 42.0),
    checked=True,
    group="quality",
)
quality_ultra = RadioButton(
    "Ultra quality",
    key="ultra",
    bounds=Rect(42.0, 216.0, 300.0, 42.0),
    group="quality",
)
high_refresh = Switch(
    "High refresh presentation",
    key="high-refresh",
    bounds=Rect(42.0, 286.0, 360.0, 42.0),
    checked=True,
)
status = Label(
    "Tab to focus • Space or Enter toggles the focused control",
    bounds=Rect(42.0, 374.0, 600.0, 32.0),
    color=Color.from_hex("#8DA8B8"),
)

root.add(heading, telemetry, quality_balanced, quality_ultra, high_refresh, status)
mount(window, root)


def update_status(*_args: object) -> None:
    quality = "Ultra" if quality_ultra.checked else "Balanced"
    status.text = (
        f"Telemetry={telemetry.checked} • Quality={quality} • "
        f"High refresh={high_refresh.checked}"
    )


for control in (telemetry, quality_balanced, quality_ultra, high_refresh):
    control.on("changed", update_status)

app.run()
