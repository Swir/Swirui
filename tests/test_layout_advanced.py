import pytest

from swirui import (
    Button,
    ConstraintLayout,
    ConstraintSpec,
    CrossAxisAlignment,
    Dock,
    DockPanel,
    Flow,
    FlowDirection,
    MainAxisAlignment,
    Overlay,
    OverlayPlacement,
    Window,
    mount,
)
from swirui.rendering import Point, Rect


def test_dock_panel_consumes_edges_in_order_and_fills_remainder() -> None:
    left = Button("Left", key="left", bounds=Rect(0.0, 0.0, 120.0, 48.0))
    top = Button("Top", key="top", bounds=Rect(0.0, 0.0, 80.0, 50.0))
    content = Button("Content", key="content", bounds=Rect(0.0, 0.0, 100.0, 80.0))
    dock = DockPanel(bounds=Rect(10.0, 20.0, 500.0, 300.0), padding=10.0, spacing=8.0)
    dock.add(left, top, content)
    dock.set_dock(left, Dock.LEFT)
    dock.set_dock(top, Dock.TOP)

    scene = mount(Window(width=540, height=360), dock).window.scene

    assert scene is not None
    assert left.bounds == Rect(20.0, 30.0, 120.0, 280.0)
    assert top.bounds == Rect(140.0, 38.0, 360.0, 50.0)
    assert content.bounds == Rect(140.0, 88.0, 360.0, 222.0)
    assert scene.hit_test(Point(300.0, 160.0)) is not None
    assert scene.hit_test(Point(300.0, 160.0)).key == "content"


def test_dock_assignment_change_invalidates_runtime_once() -> None:
    child = Button("Pane", bounds=Rect(0.0, 0.0, 90.0, 40.0))
    dock = DockPanel(bounds=Rect(0.0, 0.0, 320.0, 180.0))
    dock.add(child)
    runtime = mount(Window(width=360, height=220), dock)

    assert runtime.generation == 1

    dock.set_dock(child, Dock.LEFT)

    assert runtime.generation == 2
    assert child.bounds == Rect(0.0, 0.0, 90.0, 180.0)


def test_flow_wraps_horizontally_and_reflows_after_resize() -> None:
    flow = Flow(
        bounds=Rect(0.0, 0.0, 1.0, 1.0),
        fill_viewport=True,
        spacing=10.0,
        line_spacing=6.0,
        main_alignment=MainAxisAlignment.START,
        cross_alignment=CrossAxisAlignment.CENTER,
    )
    first = Button("One", bounds=Rect(0.0, 0.0, 100.0, 30.0))
    second = Button("Two", bounds=Rect(0.0, 0.0, 100.0, 40.0))
    third = Button("Three", bounds=Rect(0.0, 0.0, 100.0, 20.0))
    flow.add(first, second, third)
    window = Window(width=230, height=180)
    runtime = mount(window, flow)

    assert first.bounds == Rect(0.0, 5.0, 100.0, 30.0)
    assert second.bounds == Rect(110.0, 0.0, 100.0, 40.0)
    assert third.bounds == Rect(0.0, 46.0, 100.0, 20.0)

    window.resize(340, 180)

    assert runtime.generation == 2
    assert first.bounds.x == pytest.approx(0.0)
    assert second.bounds.x == pytest.approx(110.0)
    assert third.bounds.x == pytest.approx(220.0)
    assert third.bounds.y == pytest.approx(10.0)


def test_vertical_flow_wraps_into_columns() -> None:
    flow = Flow(
        bounds=Rect(0.0, 0.0, 260.0, 120.0),
        direction=FlowDirection.VERTICAL,
        spacing=6.0,
        line_spacing=12.0,
    )
    one = Button("One", bounds=Rect(0.0, 0.0, 70.0, 50.0))
    two = Button("Two", bounds=Rect(0.0, 0.0, 90.0, 50.0))
    three = Button("Three", bounds=Rect(0.0, 0.0, 80.0, 50.0))
    flow.add(one, two, three)

    flow.prepare_layout(flow.bounds)

    assert one.bounds == Rect(0.0, 0.0, 70.0, 50.0)
    assert two.bounds == Rect(0.0, 56.0, 90.0, 50.0)
    assert three.bounds == Rect(102.0, 0.0, 80.0, 50.0)


def test_overlay_uses_per_child_alignment_and_offsets() -> None:
    base = Button("Base", bounds=Rect(0.0, 0.0, 120.0, 60.0))
    badge = Button("Badge", bounds=Rect(0.0, 0.0, 60.0, 30.0))
    badge.set_layout_constraints(
        min_width=60.0,
        max_width=60.0,
        min_height=30.0,
        max_height=30.0,
    )
    overlay = Overlay(bounds=Rect(10.0, 20.0, 300.0, 180.0), padding=10.0)
    overlay.add(base, badge)
    overlay.set_placement(
        base,
        OverlayPlacement(
            horizontal=CrossAxisAlignment.STRETCH,
            vertical=CrossAxisAlignment.STRETCH,
        ),
    )
    overlay.set_placement(
        badge,
        OverlayPlacement(
            horizontal=CrossAxisAlignment.END,
            vertical=CrossAxisAlignment.START,
            offset_x=-4.0,
            offset_y=6.0,
        ),
    )

    overlay.prepare_layout(overlay.bounds)

    assert base.bounds == Rect(20.0, 30.0, 280.0, 160.0)
    assert badge.bounds == Rect(236.0, 36.0, 60.0, 30.0)


def test_constraint_layout_stretches_paired_edges_and_centers_with_offsets() -> None:
    stretched = Button("Stretch", bounds=Rect(0.0, 0.0, 80.0, 40.0))
    centered = Button("Center", bounds=Rect(0.0, 0.0, 100.0, 50.0))
    layout = ConstraintLayout(bounds=Rect(10.0, 20.0, 500.0, 300.0), padding=10.0)
    layout.add(stretched, centered)
    layout.set_constraints(
        stretched,
        ConstraintSpec(left=20.0, right=30.0, top=15.0, height=44.0),
    )
    layout.set_constraints(
        centered,
        ConstraintSpec(center_x=12.0, center_y=-8.0, width=120.0, height=60.0),
    )

    layout.prepare_layout(layout.bounds)

    assert stretched.bounds == Rect(40.0, 45.0, 430.0, 44.0)
    assert centered.bounds == Rect(212.0, 132.0, 120.0, 60.0)


def test_constraint_layout_applies_child_min_max_after_anchor_resolution() -> None:
    child = Button("Bounded", bounds=Rect(0.0, 0.0, 50.0, 30.0))
    child.set_layout_constraints(min_width=100.0, max_width=140.0, min_height=40.0)
    layout = ConstraintLayout(bounds=Rect(0.0, 0.0, 300.0, 160.0))
    layout.add(child)
    layout.set_constraints(child, ConstraintSpec(left=10.0, right=10.0, top=12.0, height=20.0))

    layout.prepare_layout(layout.bounds)

    assert child.bounds == Rect(10.0, 12.0, 140.0, 40.0)


def test_constraint_spec_rejects_ambiguous_or_non_finite_values() -> None:
    with pytest.raises(ValueError, match="Horizontal"):
        ConstraintSpec(left=0.0, right=0.0, center_x=0.0)
    with pytest.raises(ValueError, match="width"):
        ConstraintSpec(width=-1.0)
    with pytest.raises(ValueError, match="top"):
        ConstraintSpec(top=float("inf"))
