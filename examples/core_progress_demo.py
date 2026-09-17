"""Retained ProgressBar / ProgressRing demo driven by ordinary Python state."""

from swirui import App, Component, Label, ProgressBar, ProgressRing, Window, mount
from swirui.rendering import Color, Rect

app = App("SwirUI retained progress")
window = app.add_window(Window(title="SwirUI — Core progress", width=720, height=460))
root = Component("progress-demo")

heading = Label(
    "SwirUI 0.4 — retained progress widgets",
    bounds=Rect(42.0, 34.0, 580.0, 38.0),
    font_size=24.0,
    color=Color.from_hex("#62E5FF"),
)
bar = ProgressBar(
    key="build-progress",
    bounds=Rect(42.0, 116.0, 470.0, 18.0),
    value=68.0,
    accessible_name="Build progress",
)
bar_label = Label(
    "Build pipeline — 68%",
    bounds=Rect(42.0, 82.0, 300.0, 24.0),
    color=Color.from_hex("#F4FAFF"),
)
ring = ProgressRing(
    key="sync-progress",
    bounds=Rect(42.0, 180.0, 128.0, 128.0),
    value=43.0,
    thickness=10.0,
    accessible_name="Asset sync progress",
)
ring_label = Label(
    "Asset sync — 43%",
    bounds=Rect(202.0, 226.0, 260.0, 28.0),
    color=Color.from_hex("#8DA8B8"),
)
status = Label(
    "Values are retained logical-DIP geometry and rebuild through WidgetRuntime invalidation.",
    bounds=Rect(42.0, 358.0, 620.0, 28.0),
    color=Color.from_hex("#8DA8B8"),
)

root.add(heading, bar_label, bar, ring, ring_label, status)
mount(window, root)
app.run()
