import pytest

from swirui import (
    Button,
    Column,
    Component,
    CrossAxisAlignment,
    Insets,
    Label,
    LayoutConstraints,
    MainAxisAlignment,
    Row,
    Window,
    mount,
)
from swirui.rendering import Point, Rect, Scene, SceneNode


def _node(scene: Scene, key: str) -> SceneNode:
    return next(node for node in scene.walk() if node.key == key)


def test_layout_constraints_validate_and_constrain_preferred_widget_size() -> None:
    button = Button("Action", bounds=Rect(0.0, 0.0, 240.0, 20.0))
    button.layout_constraints = LayoutConstraints(
        min_width=80.0,
        min_height=32.0,
        max_width=160.0,
        max_height=48.0,
    )

    measured = button.measure()

    assert measured.width == 160.0
    assert measured.height == 32.0

    with pytest.raises(ValueError, match="Minimum"):
        LayoutConstraints(min_width=100.0, max_width=50.0)


def test_row_arranges_spacing_padding_grow_constraints_and_cross_stretch() -> None:
    first = Button("First", key="first", bounds=Rect(0.0, 0.0, 80.0, 30.0))
    second = Button("Second", key="second", bounds=Rect(0.0, 0.0, 100.0, 40.0))
    first.set_layout_grow(1.0).set_layout_constraints(max_width=260.0, max_height=60.0)
    second.set_layout_grow(2.0).set_layout_constraints(max_width=160.0, max_height=60.0)
    row = Row(
        key="row",
        bounds=Rect(20.0, 30.0, 400.0, 80.0),
        padding=Insets.symmetric(horizontal=10.0, vertical=10.0),
        spacing=10.0,
        cross_alignment=CrossAxisAlignment.STRETCH,
    )
    row.add(first, second)

    scene = mount(Window(width=500, height=200), row).window.scene

    assert scene is not None
    assert first.bounds == Rect(30.0, 40.0, 210.0, 60.0)
    assert second.bounds == Rect(250.0, 40.0, 160.0, 60.0)
    assert _node(scene, "first").bounds == first.bounds
    assert _node(scene, "second").bounds == second.bounds
    assert scene.hit_test(Point(270.0, 60.0)) is _node(scene, "second")


def test_row_shrinks_children_to_minimum_constraints_without_overflowing_slot() -> None:
    first = Button("One", bounds=Rect(0.0, 0.0, 160.0, 32.0))
    second = Button("Two", bounds=Rect(0.0, 0.0, 160.0, 32.0))
    first.set_layout_constraints(min_width=100.0)
    second.set_layout_constraints(min_width=80.0)
    row = Row(bounds=Rect(0.0, 0.0, 220.0, 50.0), spacing=10.0)
    row.add(first, second)

    row.prepare_layout(row.bounds)

    assert first.bounds.width == pytest.approx(112.8571428571)
    assert second.bounds.width == pytest.approx(97.1428571429)
    assert second.bounds.right == pytest.approx(220.0)


def test_column_fills_window_and_reflows_once_per_runtime_resize() -> None:
    title = Label("Layout", key="title", bounds=Rect(0.0, 0.0, 160.0, 28.0))
    button = Button("Continue", key="continue", bounds=Rect(0.0, 0.0, 180.0, 44.0))
    column = Column(
        key="column",
        bounds=Rect(0.0, 0.0, 1.0, 1.0),
        fill_viewport=True,
        padding=20.0,
        spacing=12.0,
        main_alignment=MainAxisAlignment.CENTER,
        cross_alignment=CrossAxisAlignment.CENTER,
    )
    column.add(title, button)
    window = Window(width=480, height=320)
    runtime = mount(window, column)

    assert runtime.generation == 1
    assert column.bounds == Rect(0.0, 0.0, 480.0, 320.0)
    assert title.bounds.x == pytest.approx(160.0)
    assert button.bounds.x == pytest.approx(150.0)
    assert title.bounds.y == pytest.approx(118.0)
    assert button.bounds.y == pytest.approx(158.0)

    window.resize(640, 400)

    assert runtime.generation == 2
    assert column.bounds == Rect(0.0, 0.0, 640.0, 400.0)
    assert title.bounds.x == pytest.approx(240.0)
    assert button.bounds.x == pytest.approx(230.0)
    assert title.bounds.y == pytest.approx(158.0)
    assert button.bounds.y == pytest.approx(198.0)


def test_nested_row_and_column_compile_using_arranged_child_viewports() -> None:
    nested = Column(
        key="nested",
        bounds=Rect(0.0, 0.0, 120.0, 100.0),
        fill_viewport=True,
        spacing=8.0,
    )
    nested.add(
        Label("A", key="a", bounds=Rect(0.0, 0.0, 60.0, 24.0)),
        Label("B", key="b", bounds=Rect(0.0, 0.0, 60.0, 24.0)),
    )
    nested.set_layout_grow(1.0)
    side = Button("Side", key="side", bounds=Rect(0.0, 0.0, 80.0, 40.0))
    root = Component("root")
    row = Row(
        bounds=Rect(10.0, 10.0, 360.0, 140.0),
        spacing=12.0,
        cross_alignment=CrossAxisAlignment.STRETCH,
    )
    row.add(nested, side)
    root.add(row)

    scene = mount(Window(width=400, height=180), root).window.scene

    assert scene is not None
    assert nested.bounds == Rect(10.0, 10.0, 268.0, 140.0)
    assert _node(scene, "a").bounds.x == pytest.approx(10.0)
    assert _node(scene, "b").bounds.y == pytest.approx(42.0)


def test_layout_property_change_invalidates_once_and_rebuilds_scene() -> None:
    row = Row(bounds=Rect(0.0, 0.0, 300.0, 80.0), spacing=8.0)
    row.add(
        Button("One", bounds=Rect(0.0, 0.0, 80.0, 40.0)),
        Button("Two", bounds=Rect(0.0, 0.0, 80.0, 40.0)),
    )
    runtime = mount(Window(width=320, height=100), row)

    assert runtime.generation == 1

    row.spacing = 20.0

    assert runtime.generation == 2
