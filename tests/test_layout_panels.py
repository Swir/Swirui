import pytest

from swirui import (
    Button,
    CrossAxisAlignment,
    Grid,
    Insets,
    Stack,
    Window,
    Wrap,
    mount,
)
from swirui.rendering import Rect


def test_stack_overlays_children_with_independent_axis_alignment() -> None:
    small = Button("Small", key="small", bounds=Rect(0.0, 0.0, 80.0, 30.0))
    wide = Button("Wide", key="wide", bounds=Rect(0.0, 0.0, 180.0, 40.0))
    stack = Stack(
        bounds=Rect(20.0, 30.0, 300.0, 160.0),
        padding=10.0,
        horizontal_alignment=CrossAxisAlignment.CENTER,
        vertical_alignment=CrossAxisAlignment.END,
    )
    stack.add(small, wide)

    mount(Window(width=360, height=220), stack)

    assert small.bounds == Rect(130.0, 150.0, 80.0, 30.0)
    assert wide.bounds == Rect(80.0, 140.0, 180.0, 40.0)


def test_grid_uses_weighted_columns_row_major_cells_and_spacing() -> None:
    one = Button("One", bounds=Rect(0.0, 0.0, 80.0, 30.0))
    two = Button("Two", bounds=Rect(0.0, 0.0, 100.0, 40.0))
    three = Button("Three", bounds=Rect(0.0, 0.0, 90.0, 28.0))
    grid = Grid(
        bounds=Rect(10.0, 20.0, 430.0, 180.0),
        columns=2,
        column_weights=(1.0, 2.0),
        column_spacing=12.0,
        row_spacing=8.0,
        padding=Insets.symmetric(horizontal=10.0, vertical=10.0),
    )
    grid.add(one, two, three)

    mount(Window(width=480, height=240), grid)

    assert one.bounds.x == pytest.approx(20.0)
    assert one.bounds.y == pytest.approx(30.0)
    assert one.bounds.width == pytest.approx(132.6666666667)
    assert two.bounds.x == pytest.approx(164.6666666667)
    assert two.bounds.width == pytest.approx(265.3333333333)
    assert three.bounds.x == pytest.approx(20.0)
    assert three.bounds.y == pytest.approx(78.0)
    assert three.bounds.width == pytest.approx(132.6666666667)


def test_grid_column_change_rebuilds_retained_scene_once() -> None:
    grid = Grid(bounds=Rect(0.0, 0.0, 300.0, 120.0), columns=2)
    grid.add(
        Button("A", bounds=Rect(0.0, 0.0, 80.0, 32.0)),
        Button("B", bounds=Rect(0.0, 0.0, 80.0, 32.0)),
    )
    runtime = mount(Window(width=320, height=160), grid)

    assert runtime.generation == 1

    grid.columns = 1

    assert runtime.generation == 2
    assert grid.children[1].bounds.y == pytest.approx(32.0)


def test_wrap_breaks_complete_items_and_reflows_after_viewport_resize() -> None:
    wrap = Wrap(
        bounds=Rect(0.0, 0.0, 1.0, 1.0),
        fill_viewport=True,
        padding=10.0,
        spacing=8.0,
        run_spacing=6.0,
        run_alignment=CrossAxisAlignment.CENTER,
    )
    first = Button("One", bounds=Rect(0.0, 0.0, 100.0, 30.0))
    second = Button("Two", bounds=Rect(0.0, 0.0, 100.0, 40.0))
    third = Button("Three", bounds=Rect(0.0, 0.0, 100.0, 20.0))
    wrap.add(first, second, third)
    window = Window(width=250, height=180)
    runtime = mount(window, wrap)

    assert first.bounds == Rect(10.0, 15.0, 100.0, 30.0)
    assert second.bounds == Rect(118.0, 10.0, 100.0, 40.0)
    assert third.bounds == Rect(10.0, 56.0, 100.0, 20.0)

    window.resize(360, 180)

    assert runtime.generation == 2
    assert first.bounds.y == pytest.approx(15.0)
    assert second.bounds.x == pytest.approx(118.0)
    assert third.bounds.x == pytest.approx(226.0)
    assert third.bounds.y == pytest.approx(20.0)
