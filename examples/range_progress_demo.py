"""Interactive retained slider and progress controls demo."""

from swirui import (
    App,
    Component,
    Label,
    ProgressBar,
    ProgressRing,
    RangeSlider,
    Slider,
    Window,
    mount,
)
from swirui.rendering import Color, Rect

app = App("SwirUI range and progress controls")
window = app.add_window(Window(title="SwirUI — Range + progress", width=760, height=520))
root = Component("range-progress-demo")

heading = Label(
    "SwirUI 0.4 — retained range + progress controls",
    bounds=Rect(42.0, 28.0, 640.0, 38.0),
    font_size=24.0,
    color=Color.from_hex("#62E5FF"),
)
volume = Slider(
    key="volume",
    bounds=Rect(42.0, 100.0, 420.0, 46.0),
    value=42.0,
    step=1.0,
    accessible_name="Demo progress",
)
progress = ProgressBar(
    key="progress",
    bounds=Rect(42.0, 172.0, 420.0, 14.0),
    value=volume.value,
    accessible_name="Demo progress bar",
)
ring = ProgressRing(
    key="ring",
    bounds=Rect(520.0, 92.0, 112.0, 112.0),
    value=volume.value,
    thickness=9.0,
    segments=64,
    accessible_name="Demo progress ring",
)
allowed = RangeSlider(
    key="allowed-range",
    bounds=Rect(42.0, 246.0, 520.0, 46.0),
    lower_value=20.0,
    upper_value=80.0,
    step=5.0,
    accessible_name="Allowed range",
)
status = Label(
    "Arrow keys adjust the focused thumb • Home / End jump to limits",
    bounds=Rect(42.0, 350.0, 650.0, 32.0),
    color=Color.from_hex("#8DA8B8"),
)

root.add(heading, volume, progress, ring, allowed, status)
mount(window, root)


def update_progress(*_args: object) -> None:
    progress.value = volume.value
    ring.value = volume.value
    status.text = (
        f"Progress={volume.value:g}% • "
        f"Range={allowed.lower_value:g}–{allowed.upper_value:g}"
    )


volume.on("changed", update_progress)
allowed.on("changed", update_progress)

app.run()
