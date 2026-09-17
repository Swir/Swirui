"""Dock, Flow and Overlay retained-layout demo."""

from swirui import (
    Button,
    Dock,
    DockSide,
    Flow,
    Insets,
    Label,
    Overlay,
    OverlayAnchor,
    Window,
    mount,
)
from swirui.rendering import Rect


window = Window(title="SwirUI advanced layouts", width=900, height=560)
root = Dock(
    bounds=Rect(0.0, 0.0, 1.0, 1.0),
    fill_viewport=True,
    padding=24.0,
)

toolbar = Flow(
    bounds=Rect(0.0, 0.0, 600.0, 48.0),
    padding=Insets.symmetric(horizontal=8.0, vertical=4.0),
    spacing=12.0,
    wrap=False,
)
toolbar.add(
    Button("Dashboard", bounds=Rect(0.0, 0.0, 130.0, 40.0)),
    Button("Projects", bounds=Rect(0.0, 0.0, 120.0, 40.0)),
    Button("Settings", bounds=Rect(0.0, 0.0, 120.0, 40.0)),
)

sidebar = Flow(
    bounds=Rect(0.0, 0.0, 170.0, 300.0),
    orientation="vertical",
    spacing=10.0,
    wrap=False,
)
sidebar.add(
    Label("SWIRUI", bounds=Rect(0.0, 0.0, 150.0, 32.0), font_size=22.0),
    Button("Components", bounds=Rect(0.0, 0.0, 150.0, 42.0)),
    Button("Layouts", bounds=Rect(0.0, 0.0, 150.0, 42.0)),
    Button("Effects", bounds=Rect(0.0, 0.0, 150.0, 42.0)),
)

workspace = Overlay(bounds=Rect(0.0, 0.0, 1.0, 1.0), clip_to_bounds=True)
workspace.add_overlay(
    Label(
        "GPU-first workspace",
        bounds=Rect(0.0, 0.0, 300.0, 44.0),
        font_size=28.0,
    ),
    anchor=OverlayAnchor.CENTER,
)
workspace.add_overlay(
    Button("Run preview", bounds=Rect(0.0, 0.0, 150.0, 44.0)),
    anchor=OverlayAnchor.BOTTOM_RIGHT,
    offset_x=-16.0,
    offset_y=-16.0,
)

root.add_docked(toolbar, DockSide.TOP)
root.add_docked(sidebar, DockSide.LEFT)
root.add_docked(workspace, DockSide.FILL)
mount(window, root)

print("Mounted advanced layout scene:", window.scene)
