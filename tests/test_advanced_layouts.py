import math

import pytest

from swirui import (
    Button,
    CrossAxisAlignment,
    Dock,
    DockSide,
    Flow,
    FlowOrientation,
    Insets,
    Overlay,
    OverlayAnchor,
    Window,
    mount,
)
from swirui.rendering import Point, Rect, Scene, SceneNode


def _node(scene: Scene, key: str) -> SceneNode:
    return next(node for node in scene.walk() if node.key == key)


def test_dock_consumes_edges_in_child_order_and_reflows_on_side_change() -> None:
    top = Button("Top", key="top", bounds=Rect(0.0, 0.0, 100.0, 36.0))
    left = Button("Left", key="left", bounds=Rect(0.0, 0.0, 80.0, 40.0))
    fill = Button("Fill", key="fill", bounds=Rect(0.0, 0.0, 160.0, 80.0))
    dock = Dock(bounds=Rect(10.0, 20.0, 500.0, 280.0), padding=10.0)
    dock.add_docked(top, DockSide.TOP)
    dock.add_docked(left, DockSide.LEFT)
    dock.add_docked(fill, DockSide.FILL)
    runtime = mount(Window(width=540, height=340), dock)

    assert top.bounds == Rect(20.0, 30.0, 480.0, 36.0)
    assert left.bounds == Rect(20.0, 66.0, 80.0, 224.0)
    assert fill.bounds == Rect(100.0, 66.0, 400.0, 224.0)
    assert dock.dock_for(fill) is DockSide.FILL

    dock.set_dock(left, DockSide.RIGHT)

    assert runtime.generation == 2
    assert left.bounds == Rect(420.0, 66.0, 80.0, 224.0)
    assert fill.bounds == Rect(20.0, 66.0, 400.0, 224.0)


def test_flow_wraps_horizontally_and_supports_vertical_reverse_order() -> None:
    horizontal = Flow(
        bounds=Rect(10.0, 20.0, 250.0, 160.0),
        padding=10.0,
        spacing=8.0,
        run_spacing=6.0,
        run_alignment=CrossAxisAlignment.CENTER,
    )
    first = Button("One", bounds=Rect(0.0, 0.0, 100.0, 30.0))
    second = Button("Two", bounds=Rect(0.0, 0.0, 100.0, 40.0))
    third = Button("Three", bounds=Rect(0.0, 0.0, 100.0, 20.0))
    horizontal.add(first, second, third)
    mount(Window(width=300, height=220), horizontal)

    assert first.bounds == Rect(20.0, 25.0, 100.0, 30.0)
    assert second.bounds == Rect(128.0, 20.0, 100.0, 40.0)
    assert third.bounds == Rect(20.0, 66.0, 100.0, 20.0)

    vertical = Flow(
        bounds=Rect(0.0, 0.0, 200.0, 210.0),
        orientation=FlowOrientation.VERTICAL,
        reverse=True,
        spacing=8.0,
        run_spacing=12.0,
    )
    a = Button("A", bounds=Rect(0.0, 0.0, 60.0, 90.0))
    b = Button("B", bounds=Rect(0.0, 0.0, 70.0, 90.0))
    c = Button("C", bounds=Rect(0.0, 0.0, 80.0, 90.0))
    vertical.add(a, b, c)
    mount(Window(width=240, height=240), vertical)

    assert c.bounds == Rect(0.0, 0.0, 80.0, 90.0)
    assert b.bounds == Rect(0.0, 98.0, 70.0, 90.0)
    assert a.bounds == Rect(92.0, 0.0, 60.0, 90.0)


def test_flow_property_mutation_rebuilds_once() -> None:
    flow = Flow(bounds=Rect(0.0, 0.0, 300.0, 100.0), spacing=4.0, wrap=False)
    flow.add(
        Button("A", bounds=Rect(0.0, 0.0, 80.0, 32.0)),
        Button("B", bounds=Rect(0.0, 0.0, 80.0, 32.0)),
    )
    runtime = mount(Window(width=320, height=120), flow)

    flow.spacing = 12.0

    assert runtime.generation == 2
    assert flow.children[1].bounds.x == pytest.approx(92.0)


def test_overlay_anchors_children_with_offsets_and_preserves_hit_testing() -> None:
    center = Button("Center", key="center", bounds=Rect(0.0, 0.0, 100.0, 60.0))
    action = Button(
        "Action",
        key="action",
        bounds=Rect(0.0, 0.0, 80.0, 40.0),
        z_index=2,
    )
    overlay = Overlay(
        key="overlay",
        bounds=Rect(20.0, 30.0, 300.0, 200.0),
        padding=10.0,
    )
    overlay.add_overlay(center, anchor=OverlayAnchor.CENTER)
    overlay.add_overlay(
        action,
        anchor=OverlayAnchor.BOTTOM_RIGHT,
        offset_x=-5.0,
        offset_y=-7.0,
    )
    runtime = mount(Window(width=360, height=260), overlay)
    scene = runtime.window.scene

    assert center.bounds == Rect(120.0, 100.0, 100.0, 60.0)
    assert action.bounds == Rect(225.0, 173.0, 80.0, 40.0)
    assert scene is not None
    assert scene.hit_test(Point(250.0, 190.0)) is _node(scene, "action")

    overlay.set_overlay(action, anchor=OverlayAnchor.TOP_RIGHT, offset_x=-2.0, offset_y=3.0)

    assert runtime.generation == 2
    assert action.bounds == Rect(228.0, 43.0, 80.0, 40.0)


def test_overlay_validates_direct_children_and_finite_offsets() -> None:
    overlay = Overlay(bounds=Rect(0.0, 0.0, 200.0, 120.0))
    child = Button("Child", bounds=Rect(0.0, 0.0, 80.0, 32.0))

    with pytest.raises(ValueError, match="direct child"):
        overlay.set_overlay(child, anchor=OverlayAnchor.CENTER)

    with pytest.raises(ValueError, match="finite"):
        overlay.add_overlay(child, offset_x=math.inf)

    dock = Dock(bounds=Rect(0.0, 0.0, 200.0, 120.0))
    with pytest.raises(ValueError, match="direct child"):
        dock.set_dock(child, DockSide.LEFT)
