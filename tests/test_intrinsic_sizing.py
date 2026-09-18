import pytest

from swirui import (
    Button,
    Column,
    ConstraintLayout,
    ConstraintSpec,
    Flow,
    Grid,
    Input,
    Label,
    PasswordInput,
    Row,
    Stack,
    TextArea,
)
from swirui.rendering import Rect, Size
from swirui.widgets.measurement import measure_text_block


def test_unicode_text_measurement_is_deterministic_and_wraps_to_available_width() -> None:
    text = "SwirUI – Zażółć gęślą jaźń 漢字"

    natural = measure_text_block(text, font_size=20.0)
    wrapped = measure_text_block(text, font_size=20.0, available_width=120.0)

    assert natural.width > 120.0
    assert natural.height == pytest.approx(25.0)
    assert 0.0 < wrapped.width <= 120.0
    assert wrapped.height > natural.height
    assert wrapped == measure_text_block(text, font_size=20.0, available_width=120.0)


def test_label_measurement_grows_from_authored_baseline_and_reflows_when_constrained() -> None:
    label = Label(
        "A retained label with enough content to wrap across several lines",
        bounds=Rect(0.0, 0.0, 20.0, 10.0),
        font_size=16.0,
    )

    natural = label.measure()
    constrained = label.measure(Size(100.0, 300.0))

    assert natural.width > 20.0
    assert natural.height >= 20.0
    assert constrained.width <= 100.0
    assert constrained.height > natural.height


def test_button_intrinsic_width_includes_label_and_horizontal_padding() -> None:
    button = Button(
        "Launch SwirUI",
        bounds=Rect(0.0, 0.0, 32.0, 18.0),
        font_size=18.0,
        padding=14.0,
    )

    measured = button.measure()
    label = measure_text_block("Launch SwirUI", font_size=18.0, wrap=False)

    assert measured.width >= label.width + 28.0
    assert measured.height >= label.height
    assert measured.width > button.preferred_size.width


def test_inputs_measure_visible_value_placeholder_and_masked_content() -> None:
    empty = Input(
        bounds=Rect(0.0, 0.0, 30.0, 18.0),
        placeholder="Type a longer project name",
        font_size=16.0,
        padding=10.0,
    )
    filled = Input(
        "SwirUI desktop application",
        bounds=Rect(0.0, 0.0, 30.0, 18.0),
        font_size=16.0,
        padding=10.0,
    )
    password = PasswordInput(
        "secret-value",
        bounds=Rect(0.0, 0.0, 30.0, 18.0),
        font_size=16.0,
        padding=10.0,
    )

    assert empty.measure().width > 30.0
    assert filled.measure().width > 30.0
    assert password.measure().width > 30.0
    assert empty.measure().height >= (16.0 * 1.3) + 20.0


def test_text_area_intrinsic_height_tracks_multiline_content_and_width_constraint() -> None:
    area = TextArea(
        "First retained line with enough words to wrap\nSecond line\nThird line",
        bounds=Rect(0.0, 0.0, 40.0, 24.0),
        font_size=16.0,
        padding=8.0,
    )

    natural = area.measure()
    constrained = area.measure(Size(130.0, 500.0))

    assert natural.width > 40.0
    assert natural.height > 24.0
    assert constrained.width <= 130.0
    assert constrained.height >= natural.height


def test_row_remeasures_cross_axis_after_children_are_shrunk() -> None:
    first = Label(
        "Alpha beta gamma delta epsilon",
        bounds=Rect(0.0, 0.0, 20.0, 20.0),
        font_size=16.0,
    )
    second = Label(
        "One two three four five six",
        bounds=Rect(0.0, 0.0, 20.0, 20.0),
        font_size=16.0,
    )
    row = Row(bounds=Rect(0.0, 0.0, 170.0, 140.0), spacing=10.0)
    row.add(first, second)

    row.prepare_layout(row.bounds)

    assert first.bounds.right + 10.0 == pytest.approx(second.bounds.x)
    assert second.bounds.right == pytest.approx(170.0)
    assert first.bounds.height > 20.0
    assert second.bounds.height > 20.0
    assert first.bounds.height == first.measure(Size(first.bounds.width, 140.0)).height
    assert second.bounds.height == second.measure(Size(second.bounds.width, 140.0)).height


def test_nested_column_measurement_propagates_content_driven_child_size() -> None:
    title = Label(
        "Intrinsic title that is wider than its authored placeholder",
        bounds=Rect(0.0, 0.0, 24.0, 12.0),
        font_size=18.0,
    )
    action = Button(
        "Continue with SwirUI",
        bounds=Rect(0.0, 0.0, 40.0, 20.0),
        font_size=16.0,
    )
    column = Column(bounds=Rect(0.0, 0.0, 1.0, 1.0), spacing=8.0, padding=10.0)
    column.add(title, action)

    measured = column.measure(Size(500.0, 500.0))

    assert measured.width > 100.0
    assert measured.height > 40.0
    assert measured.width >= action.measure(Size(500.0, 500.0)).width + 20.0


def test_panel_and_advanced_layout_measurement_propagate_intrinsic_children() -> None:
    label = Label(
        "Content-driven child measurement must propagate through retained containers.",
        bounds=Rect(0.0, 0.0, 20.0, 16.0),
        font_size=16.0,
    )
    stack = Stack(bounds=Rect(0.0, 0.0, 1.0, 1.0), padding=12.0)
    stack.add(label)
    stack_size = stack.measure(Size(500.0, 500.0))

    assert stack_size.width >= label.measure(Size(500.0, 500.0)).width + 24.0
    assert stack_size.height >= label.measure(Size(500.0, 500.0)).height + 24.0

    grid = Grid(
        bounds=Rect(0.0, 0.0, 1.0, 1.0),
        columns=2,
        column_spacing=10.0,
        padding=8.0,
    )
    grid.add(
        Label("A much wider first cell", bounds=Rect(0.0, 0.0, 10.0, 12.0)),
        Button("Measured action", bounds=Rect(0.0, 0.0, 20.0, 18.0)),
    )
    grid_size = grid.measure(Size(600.0, 400.0))
    assert grid_size.width > 100.0
    assert grid_size.height > 30.0

    flow = Flow(bounds=Rect(0.0, 0.0, 1.0, 1.0), spacing=8.0, line_spacing=6.0)
    flow.add(
        Label("First flowing item", bounds=Rect(0.0, 0.0, 10.0, 12.0)),
        Label("Second flowing item", bounds=Rect(0.0, 0.0, 10.0, 12.0)),
    )
    flow_size = flow.measure(Size(150.0, 300.0))
    assert flow_size.width <= 150.0
    assert flow_size.height > 20.0

    constrained_child = Label(
        "Constraint child content",
        bounds=Rect(0.0, 0.0, 10.0, 12.0),
    )
    constraint = ConstraintLayout(bounds=Rect(0.0, 0.0, 1.0, 1.0), padding=5.0)
    constraint.add(constrained_child)
    constraint.set_constraints(constrained_child, ConstraintSpec(left=12.0, top=7.0))
    constraint_size = constraint.measure(Size(500.0, 500.0))
    assert constraint_size.width >= constrained_child.measure().width + 22.0
    assert constraint_size.height >= constrained_child.measure().height + 17.0


def test_arrangement_still_preserves_explicit_preferred_size_baseline() -> None:
    label = Label("Short", bounds=Rect(5.0, 6.0, 140.0, 36.0))

    label._set_layout_bounds(Rect(0.0, 0.0, 60.0, 24.0))

    assert label.preferred_size == Size(140.0, 36.0)
    assert label.measure() == Size(140.0, 36.0)
