from __future__ import annotations

from datetime import date, time

import pytest

from swirui import Calendar, DatePicker, TimePicker
from swirui.core import AccessibilityRole
from swirui.rendering import Rect


def test_calendar_visible_grid_selection_and_month_navigation() -> None:
    calendar = Calendar(
        bounds=Rect(0.0, 0.0, 420.0, 360.0),
        selected_date=date(2026, 9, 21),
        displayed_month=date(2026, 9, 1),
        key="calendar",
    )

    visible = calendar.visible_dates()
    assert len(visible) == 42
    assert visible[0] == date(2026, 8, 31)
    assert calendar.date_at_cell(0, 0) == date(2026, 8, 31)
    assert calendar.cell_bounds(5, 6).right == pytest.approx(420.0)

    changes: list[date] = []
    calendar.on("date_changed", lambda event: changes.append(event.data["value"]))
    calendar.set_selected_date(date(2026, 10, 2))
    assert calendar.selected_date == date(2026, 10, 2)
    assert calendar.displayed_month == date(2026, 10, 1)
    assert changes == [date(2026, 10, 2)]

    calendar.previous_month()
    assert calendar.displayed_month == date(2026, 9, 1)
    calendar.next_month()
    assert calendar.displayed_month == date(2026, 10, 1)


def test_calendar_scene_and_accessibility_contract() -> None:
    calendar = Calendar(
        bounds=Rect(12.0, 20.0, 490.0, 380.0),
        selected_date=date(2026, 9, 21),
        min_date=date(2026, 9, 10),
        max_date=date(2026, 10, 15),
        key="schedule",
    )

    scene = calendar.build_scene_node()
    keys = {node.key for node in scene.walk()}
    texts = [node.text for node in scene.walk() if node.kind.value == "text"]
    assert "schedule:month-title" in keys
    assert "schedule:cell:21:label" in keys
    assert "September 2026" in texts
    assert "21" in texts

    snapshot = calendar.accessibility_snapshot(focused=calendar)
    assert snapshot.role is AccessibilityRole.TABLE
    assert snapshot.focused is True
    assert snapshot.row_count == 6
    assert snapshot.column_count == 7
    assert len(snapshot.children) == 42
    selected = next(child for child in snapshot.children if child.selected)
    assert selected.value_text == "2026-09-21"
    assert selected.role is AccessibilityRole.CELL
    disabled = next(child for child in snapshot.children if child.value_text == "2026-09-01")
    assert disabled.enabled is False


def test_calendar_range_validation_and_clamping() -> None:
    with pytest.raises(ValueError, match="min_date"):
        Calendar(
            bounds=Rect(0.0, 0.0, 420.0, 360.0),
            min_date=date(2026, 10, 1),
            max_date=date(2026, 9, 1),
        )

    calendar = Calendar(
        bounds=Rect(0.0, 0.0, 420.0, 360.0),
        selected_date=date(2026, 9, 1),
        min_date=date(2026, 9, 10),
        max_date=date(2026, 9, 30),
    )
    assert calendar.selected_date == date(2026, 9, 10)
    with pytest.raises(ValueError, match="outside"):
        calendar.set_selected_date(date(2026, 10, 1))
    with pytest.raises(IndexError, match="cell"):
        calendar.date_at_cell(6, 0)


def test_date_picker_adjustment_scene_and_accessibility() -> None:
    picker = DatePicker(
        bounds=Rect(0.0, 0.0, 300.0, 62.0),
        value=date(2024, 2, 29),
        min_date=date(2020, 1, 1),
        max_date=date(2030, 12, 31),
        key="date-picker",
    )
    assert picker.active_segment == "day"
    picker.adjust_active(1)
    assert picker.value == date(2024, 3, 1)

    scene = picker.build_scene_node()
    texts = [node.text for node in scene.walk() if node.kind.value == "text"]
    assert "2024" in texts
    assert "03" in texts
    assert "01" in texts

    snapshot = picker.accessibility_snapshot(focused=picker)
    assert snapshot.role is AccessibilityRole.GROUP
    assert snapshot.value_text == "2024-03-01"
    assert snapshot.children[2].selected is True
    assert snapshot.children[2].name == "Day"


def test_time_picker_steps_wraps_and_accessibility() -> None:
    picker = TimePicker(
        bounds=Rect(0.0, 0.0, 260.0, 62.0),
        value=time(23, 55, 58),
        minute_step=5,
        show_seconds=True,
        second_step=2,
        key="time-picker",
    )
    assert picker.value == time(23, 55, 58)
    assert picker.active_segment == "minute"
    picker.adjust_active(1)
    assert picker.value == time(0, 0, 58)

    scene = picker.build_scene_node()
    texts = [node.text for node in scene.walk() if node.kind.value == "text"]
    assert "00" in texts
    assert "58" in texts

    snapshot = picker.accessibility_snapshot(focused=picker)
    assert snapshot.role is AccessibilityRole.GROUP
    assert snapshot.value_text == "00:00:58"
    assert snapshot.column_count == 3
    assert snapshot.children[1].selected is True


def test_time_picker_validates_steps() -> None:
    with pytest.raises(ValueError, match="minute_step"):
        TimePicker(bounds=Rect(0.0, 0.0, 240.0, 60.0), minute_step=7)
    with pytest.raises(ValueError, match="second_step"):
        TimePicker(
            bounds=Rect(0.0, 0.0, 240.0, 60.0),
            show_seconds=True,
            second_step=11,
        )
