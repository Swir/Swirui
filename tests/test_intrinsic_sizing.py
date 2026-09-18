import pytest

from swirui import Button, Column, Label, Row
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


def test_arrangement_still_preserves_explicit_preferred_size_baseline() -> None:
    label = Label("Short", bounds=Rect(5.0, 6.0, 140.0, 36.0))

    label._set_layout_bounds(Rect(0.0, 0.0, 60.0, 24.0))

    assert label.preferred_size == Size(140.0, 36.0)
    assert label.measure() == Size(140.0, 36.0)
