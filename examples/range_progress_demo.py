"""Interactive retained slider and progress controls demo."""

from dataclasses import replace

from swirui import (
    NEON_BLUE,
    App,
    Label,
    Panel,
    ProgressBar,
    ProgressRing,
    RangeSlider,
    SilkRibbon,
    Slider,
    SurfaceStyle,
    ThemeSurface,
    Window,
    mount,
)
from swirui.rendering import Color, GradientStop, LinearGradient, Point, Rect

app = App("SwirUI range and progress controls")
window = app.add_window(Window(title="SwirUI — Range and progress", width=700, height=420,
                               min_width=700, min_height=420))
theme = replace(NEON_BLUE.with_accent("#83E6C2"), control_radius=16,
                surface_style=SurfaceStyle(kind="glass", tint_opacity=.83, elevation=6))
root = Panel(bounds=Rect(0, 0, 700, 420), theme=theme)
card = ThemeSurface(bounds=Rect(30, 88, 640, 250))
scale = LinearGradient(
    Point(0, .5), Point(1, .5),
    (GradientStop(0, Color.from_hex("#9234ED")),
     GradientStop(.48, Color.from_hex("#187BD8")),
     GradientStop(1, Color.from_hex("#14D789"))),
)

volume = Slider(
    key="volume",
    bounds=Rect(54, 148, 398, 40),
    value=42.0,
    step=1.0,
    fill_gradient=scale,
    accessible_name="Demo progress",
)
progress = ProgressBar(
    key="progress",
    bounds=Rect(54, 198, 398, 6),
    value=volume.value,
    fill_gradient=scale,
    accessible_name="Demo progress bar",
)
ring = ProgressRing(
    key="ring",
    bounds=Rect(512, 105, 108, 108),
    value=volume.value,
    thickness=9.0,
    segments=64,
    accessible_name="Demo progress ring",
)
allowed = RangeSlider(
    key="allowed-range",
    bounds=Rect(54, 274, 570, 44),
    lower_value=20.0,
    upper_value=80.0,
    step=5.0,
    fill_gradient=scale,
    accessible_name="Allowed range",
)
progress_value = Label("", bounds=Rect(545, 145, 63, 34), font_size=20)
range_value = Label("", bounds=Rect(541, 239, 108, 32), font_size=18)
card.add(Label("Preview progress", bounds=Rect(54, 112, 350, 34), font_size=21),
         volume, progress, ring, progress_value,
         Label("Allowed range", bounds=Rect(54, 237, 350, 34), font_size=21), range_value, allowed)
root.add(SilkRibbon(bounds=Rect(298, 0, 383, 186)),
         Label("Range and progress", bounds=Rect(30, 22, 390, 52), font_size=32),
         card,
         Label("Tab selects the next handle. Use the arrow keys to adjust its value.",
               bounds=Rect(32, 360, 636, 36), font_size=16))
mount(window, root)


def update_progress(*_args: object) -> None:
    progress.value = volume.value
    ring.value = volume.value
    progress_value.text = f"{volume.value:g}%"
    range_value.text = f"{allowed.lower_value:g}–{allowed.upper_value:g}%"


volume.on("changed", update_progress)
allowed.on("changed", update_progress)
update_progress()

app.run()
