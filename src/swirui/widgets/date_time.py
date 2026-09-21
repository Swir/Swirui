"""Retained Calendar, DatePicker and TimePicker widgets."""

from __future__ import annotations

import calendar as _calendar
from datetime import date, time, timedelta

from swirui.core import AccessibilityNode, AccessibilityRole, Component, Event
from swirui.platforms import PlatformEvent, PlatformEventKind, PointerButton
from swirui.rendering.geometry import Color, CornerRadius, Rect
from swirui.rendering.scene import SceneNode, SceneNodeKind

from .base import Widget

_VK_RETURN = 0x0D
_VK_SPACE = 0x20
_VK_PRIOR = 0x21
_VK_NEXT = 0x22
_VK_END = 0x23
_VK_HOME = 0x24
_VK_LEFT = 0x25
_VK_UP = 0x26
_VK_RIGHT = 0x27
_VK_DOWN = 0x28

_BACKGROUND = Color.from_hex("#06101A")
_SURFACE = Color.from_hex("#081723")
_SELECTED = Color.from_hex("#0B3550")
_FOREGROUND = Color.from_hex("#DDF5FF")
_MUTED = Color.from_hex("#8DA8B8")
_ACCENT = Color.from_hex("#23C9FF")
_DISABLED = Color.from_hex("#456273")
_BORDER = Color.from_hex("#164D6B")
_WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
_MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)


def _platform_event(event: Event, kind: PlatformEventKind) -> PlatformEvent | None:
    candidate = event.data.get("event")
    if isinstance(candidate, PlatformEvent) and candidate.kind is kind:
        return candidate
    return None


def _text(
    key: str,
    bounds: Rect,
    value: str,
    size: float,
    color: Color,
    family: str,
) -> SceneNode:
    return SceneNode(
        key=key,
        kind=SceneNodeKind.TEXT,
        bounds=bounds,
        fill=color,
        text=value,
        font_size=size,
        font_family=family,
        z_index=4,
        hit_testable=False,
    )


def _days_in_month(year: int, month: int) -> int:
    return _calendar.monthrange(year, month)[1]


def _shift_months(value: date, months: int) -> date:
    absolute = value.year * 12 + value.month - 1 + int(months)
    absolute = min(9999 * 12 + 11, max(12, absolute))
    year, zero_month = divmod(absolute, 12)
    month = zero_month + 1
    return date(year, month, min(value.day, _days_in_month(year, month)))


def _shift_years(value: date, years: int) -> date:
    year = min(9999, max(1, value.year + int(years)))
    return date(year, value.month, min(value.day, _days_in_month(year, value.month)))


def _shift_days(value: date, days: int) -> date:
    try:
        return value + timedelta(days=int(days))
    except OverflowError:
        return date.max if days > 0 else date.min


class Calendar(Widget):
    """Focusable six-week month calendar with bounded date selection."""

    _HEADER_HEIGHT = 42.0
    _WEEKDAY_HEIGHT = 24.0

    def __init__(
        self,
        *,
        bounds: Rect,
        selected_date: date | None = None,
        displayed_month: date | None = None,
        min_date: date | None = None,
        max_date: date | None = None,
        first_weekday: int = 0,
        key: str | None = None,
        font_family: str = "Segoe UI",
        opacity: float = 1.0,
        z_index: int = 0,
        accessible_name: str = "Calendar",
        accessible_description: str | None = None,
    ) -> None:
        if not 0 <= int(first_weekday) <= 6:
            raise ValueError("first_weekday must be between 0 and 6.")
        self._min_date, self._max_date = self._validate_range(min_date, max_date)
        self._first_weekday = int(first_weekday)
        initial = selected_date or date.today()
        self._selected_date = self._clamp(initial)
        month_seed = displayed_month or self._selected_date
        self._displayed_month = date(month_seed.year, month_seed.month, 1)
        self._font_family = self._validate_family(font_family)
        super().__init__(
            bounds=bounds,
            key=key,
            opacity=opacity,
            z_index=z_index,
            clip_to_bounds=True,
            focusable=True,
            accessibility_role=AccessibilityRole.TABLE,
            accessible_name=accessible_name,
            accessible_description=accessible_description,
        )
        self.on("pointer_down", self._on_pointer_down)
        self.on("key_down", self._on_key_down)
        self._sync_accessibility()

    @property
    def selected_date(self) -> date:
        return self._selected_date

    @property
    def displayed_month(self) -> date:
        return self._displayed_month

    @property
    def first_weekday(self) -> int:
        return self._first_weekday

    def set_selected_date(self, value: date, *, ensure_visible: bool = True) -> Calendar:
        if not isinstance(value, date):
            raise TypeError("value must be datetime.date.")
        if not self._selectable(value):
            raise ValueError("Date is outside the selectable range.")
        if value == self._selected_date:
            if ensure_visible:
                self._show_selected_month()
            return self
        previous = self._selected_date
        self._selected_date = value
        if ensure_visible:
            self._show_selected_month()
        self._sync_accessibility()
        self.invalidate(reason="selected_date")
        self.emit("date_changed", value=value, previous=previous)
        return self

    def set_displayed_month(self, value: date) -> Calendar:
        if not isinstance(value, date):
            raise TypeError("value must be datetime.date.")
        normalized = date(value.year, value.month, 1)
        if normalized == self._displayed_month:
            return self
        previous = self._displayed_month
        self._displayed_month = normalized
        self.invalidate(reason="displayed_month")
        self.emit("month_changed", value=normalized, previous=previous)
        return self

    def previous_month(self) -> Calendar:
        return self.set_displayed_month(_shift_months(self._displayed_month, -1))

    def next_month(self) -> Calendar:
        return self.set_displayed_month(_shift_months(self._displayed_month, 1))

    def activate_selected(self) -> Calendar:
        self.emit("date_activated", value=self._selected_date)
        return self

    def visible_dates(self) -> tuple[date, ...]:
        offset = (self._displayed_month.weekday() - self._first_weekday) % 7
        first = _shift_days(self._displayed_month, -offset)
        return tuple(_shift_days(first, index) for index in range(42))

    def date_at_cell(self, row: int, column: int) -> date:
        row = int(row)
        column = int(column)
        if not 0 <= row < 6 or not 0 <= column < 7:
            raise IndexError("Calendar cell is out of range.")
        return self.visible_dates()[row * 7 + column]

    def cell_bounds(self, row: int, column: int) -> Rect:
        row = int(row)
        column = int(column)
        if not 0 <= row < 6 or not 0 <= column < 7:
            raise IndexError("Calendar cell is out of range.")
        grid_y = self.bounds.y + self._HEADER_HEIGHT + self._WEEKDAY_HEIGHT
        width = self.bounds.width / 7.0
        remaining = self.bounds.height - self._HEADER_HEIGHT - self._WEEKDAY_HEIGHT
        height = max(0.0, remaining) / 6.0
        return Rect(
            self.bounds.x + column * width,
            grid_y + row * height,
            width,
            height,
        )

    def build_scene_node(self) -> SceneNode:
        root = SceneNode(
            key=self.key,
            kind=SceneNodeKind.RECTANGLE,
            bounds=self.bounds,
            opacity=self.opacity,
            z_index=self.z_index,
            fill=_BACKGROUND,
            corner_radius=CornerRadius.uniform(8.0),
            clip_to_bounds=True,
            hit_testable=self.enabled,
        )
        root.add(
            SceneNode(
                key=f"{self.key}:header",
                kind=SceneNodeKind.RECTANGLE,
                bounds=Rect(
                    self.bounds.x,
                    self.bounds.y,
                    self.bounds.width,
                    self._HEADER_HEIGHT,
                ),
                fill=_SURFACE,
                z_index=1,
                hit_testable=False,
            )
        )
        title = f"{_MONTHS[self._displayed_month.month - 1]} {self._displayed_month.year}"
        root.add(
            _text(
                f"{self.key}:month-title",
                Rect(
                    self.bounds.x + 48.0,
                    self.bounds.y + 9.0,
                    max(0.0, self.bounds.width - 96.0),
                    24.0,
                ),
                title,
                15.0,
                _FOREGROUND,
                self._font_family,
            )
        )
        root.add(
            _text(
                f"{self.key}:prev",
                Rect(self.bounds.x + 12.0, self.bounds.y + 10.0, 24.0, 22.0),
                "‹",
                20.0,
                _ACCENT,
                self._font_family,
            )
        )
        root.add(
            _text(
                f"{self.key}:next",
                Rect(self.bounds.right - 36.0, self.bounds.y + 10.0, 24.0, 22.0),
                "›",
                20.0,
                _ACCENT,
                self._font_family,
            )
        )
        weekday_width = self.bounds.width / 7.0
        weekday_y = self.bounds.y + self._HEADER_HEIGHT
        for column in range(7):
            weekday = _WEEKDAYS[(self._first_weekday + column) % 7]
            root.add(
                _text(
                    f"{self.key}:weekday:{column}",
                    Rect(
                        self.bounds.x + column * weekday_width + 6.0,
                        weekday_y + 4.0,
                        max(0.0, weekday_width - 12.0),
                        17.0,
                    ),
                    weekday,
                    11.0,
                    _MUTED,
                    self._font_family,
                )
            )
        for index, current in enumerate(self.visible_dates()):
            row, column = divmod(index, 7)
            cell = self.cell_bounds(row, column)
            selected = current == self._selected_date
            if selected:
                root.add(
                    SceneNode(
                        key=f"{self.key}:cell:{index}:selected",
                        kind=SceneNodeKind.RECTANGLE,
                        bounds=Rect(
                            cell.x + 3.0,
                            cell.y + 3.0,
                            max(0.0, cell.width - 6.0),
                            max(0.0, cell.height - 6.0),
                        ),
                        fill=_SELECTED,
                        corner_radius=CornerRadius.uniform(6.0),
                        z_index=2,
                        hit_testable=False,
                    )
                )
            if not self._selectable(current):
                color = _DISABLED
            elif selected:
                color = _ACCENT
            elif current.month != self._displayed_month.month:
                color = _MUTED
            else:
                color = _FOREGROUND
            root.add(
                _text(
                    f"{self.key}:cell:{index}:label",
                    Rect(
                        cell.x + 8.0,
                        cell.y + max(4.0, cell.height * 0.28),
                        max(0.0, cell.width - 16.0),
                        20.0,
                    ),
                    str(current.day),
                    13.0,
                    color,
                    self._font_family,
                )
            )
        return root

    def accessibility_snapshot(
        self,
        *,
        focused: Component | None = None,
    ) -> AccessibilityNode:
        children = tuple(
            AccessibilityNode(
                key=f"{self.key}:a11y:{current.isoformat()}",
                role=AccessibilityRole.CELL,
                name=current.strftime("%A, %B %d, %Y"),
                description="Date",
                enabled=self.enabled and self._selectable(current),
                focusable=False,
                focused=False,
                selected=current == self._selected_date,
                active=current == self._selected_date,
                row_index=index // 7,
                column_index=index % 7,
                row_count=6,
                column_count=7,
                value_text=current.isoformat(),
            )
            for index, current in enumerate(self.visible_dates())
        )
        return AccessibilityNode(
            key=self.key,
            role=AccessibilityRole.TABLE,
            name=self.accessible_name or self.name,
            description=self.accessible_description,
            enabled=self.enabled,
            focusable=self.focusable,
            focused=focused is self,
            value_text=self.accessible_value_text,
            row_count=6,
            column_count=7,
            children=children,
        )

    def _on_pointer_down(self, event: Event) -> None:
        platform = _platform_event(event, PlatformEventKind.POINTER_DOWN)
        if not self._valid_pointer(platform):
            return
        assert platform is not None
        assert platform.x is not None and platform.y is not None
        local_x = platform.x - self.bounds.x
        local_y = platform.y - self.bounds.y
        if local_y < self._HEADER_HEIGHT:
            if local_x < 48.0:
                self.previous_month()
                event.prevent_default()
            elif local_x >= self.bounds.width - 48.0:
                self.next_month()
                event.prevent_default()
            return
        grid_start = self._HEADER_HEIGHT + self._WEEKDAY_HEIGHT
        if local_y < grid_start:
            return
        cell_width = self.bounds.width / 7.0
        cell_height = max(0.0, self.bounds.height - grid_start) / 6.0
        if cell_width <= 0.0 or cell_height <= 0.0:
            return
        column = min(6, max(0, int(local_x // cell_width)))
        row = min(5, max(0, int((local_y - grid_start) // cell_height)))
        current = self.date_at_cell(row, column)
        if self._selectable(current):
            self.set_selected_date(current)
            event.prevent_default()

    def _on_key_down(self, event: Event) -> None:
        platform = _platform_event(event, PlatformEventKind.KEY_DOWN)
        if platform is None or not self.enabled:
            return
        if platform.alt or platform.ctrl or platform.meta:
            return
        key_code = platform.key_code
        if key_code in {_VK_RETURN, _VK_SPACE}:
            self.activate_selected()
            event.prevent_default()
            return
        target: date | None = None
        if key_code == _VK_LEFT:
            target = _shift_days(self._selected_date, -1)
        elif key_code == _VK_RIGHT:
            target = _shift_days(self._selected_date, 1)
        elif key_code == _VK_UP:
            target = _shift_days(self._selected_date, -7)
        elif key_code == _VK_DOWN:
            target = _shift_days(self._selected_date, 7)
        elif key_code == _VK_HOME:
            target = date(self._selected_date.year, self._selected_date.month, 1)
        elif key_code == _VK_END:
            target = date(
                self._selected_date.year,
                self._selected_date.month,
                _days_in_month(self._selected_date.year, self._selected_date.month),
            )
        elif key_code == _VK_PRIOR:
            target = _shift_months(self._selected_date, -1)
        elif key_code == _VK_NEXT:
            target = _shift_months(self._selected_date, 1)
        if target is not None:
            self.set_selected_date(self._clamp(target))
            event.prevent_default()

    def _valid_pointer(self, platform: PlatformEvent | None) -> bool:
        return bool(
            self.enabled
            and platform is not None
            and platform.button is PointerButton.LEFT
            and platform.x is not None
            and platform.y is not None
            and self.bounds.x <= platform.x < self.bounds.right
            and self.bounds.y <= platform.y < self.bounds.bottom
        )

    def _show_selected_month(self) -> None:
        selected_month = date(self._selected_date.year, self._selected_date.month, 1)
        if selected_month != self._displayed_month:
            self.set_displayed_month(selected_month)

    def _selectable(self, value: date) -> bool:
        return (self._min_date is None or value >= self._min_date) and (
            self._max_date is None or value <= self._max_date
        )

    def _clamp(self, value: date) -> date:
        if self._min_date is not None and value < self._min_date:
            return self._min_date
        if self._max_date is not None and value > self._max_date:
            return self._max_date
        return value

    def _sync_accessibility(self) -> None:
        self.accessible_value_text = self._selected_date.isoformat()

    @staticmethod
    def _validate_range(
        min_date: date | None,
        max_date: date | None,
    ) -> tuple[date | None, date | None]:
        if min_date is not None and not isinstance(min_date, date):
            raise TypeError("min_date must be datetime.date or None.")
        if max_date is not None and not isinstance(max_date, date):
            raise TypeError("max_date must be datetime.date or None.")
        if min_date is not None and max_date is not None and min_date > max_date:
            raise ValueError("min_date must not be after max_date.")
        return min_date, max_date

    @staticmethod
    def _validate_family(value: str) -> str:
        normalized = str(value).strip()
        if not normalized:
            raise ValueError("font_family must not be empty.")
        return normalized


class _SegmentPicker(Widget):
    """Shared retained segmented-picker interaction and rendering contract."""

    def __init__(
        self,
        *,
        bounds: Rect,
        segments: tuple[str, ...],
        active_segment: int,
        key: str | None,
        font_family: str,
        opacity: float,
        z_index: int,
        accessible_name: str,
        accessible_description: str | None,
    ) -> None:
        self._segments = segments
        self._active_segment = active_segment
        self._font_family = Calendar._validate_family(font_family)
        super().__init__(
            bounds=bounds,
            key=key,
            opacity=opacity,
            z_index=z_index,
            clip_to_bounds=True,
            focusable=True,
            accessibility_role=AccessibilityRole.GROUP,
            accessible_name=accessible_name,
            accessible_description=accessible_description,
        )
        self.on("pointer_down", self._on_pointer_down)
        self.on("key_down", self._on_key_down)

    @property
    def active_segment(self) -> str:
        return self._segments[self._active_segment]

    def build_scene_node(self) -> SceneNode:
        root = SceneNode(
            key=self.key,
            kind=SceneNodeKind.RECTANGLE,
            bounds=self.bounds,
            opacity=self.opacity,
            z_index=self.z_index,
            fill=_BACKGROUND,
            corner_radius=CornerRadius.uniform(8.0),
            clip_to_bounds=True,
            hit_testable=self.enabled,
        )
        width = self.bounds.width / len(self._segments)
        for index, (label, value) in enumerate(
            zip(self._segments, self._value_texts(), strict=True)
        ):
            cell = Rect(
                self.bounds.x + index * width,
                self.bounds.y,
                width,
                self.bounds.height,
            )
            if index == self._active_segment:
                root.add(
                    SceneNode(
                        key=f"{self.key}:segment:{index}:active",
                        kind=SceneNodeKind.RECTANGLE,
                        bounds=Rect(
                            cell.x + 3.0,
                            cell.y + 3.0,
                            max(0.0, cell.width - 6.0),
                            max(0.0, cell.height - 6.0),
                        ),
                        fill=_SELECTED,
                        corner_radius=CornerRadius.uniform(6.0),
                        z_index=2,
                        hit_testable=False,
                    )
                )
            if index:
                root.add(
                    SceneNode(
                        key=f"{self.key}:divider:{index}",
                        kind=SceneNodeKind.RECTANGLE,
                        bounds=Rect(
                            cell.x,
                            cell.y + 8.0,
                            1.0,
                            max(0.0, cell.height - 16.0),
                        ),
                        fill=_BORDER,
                        z_index=3,
                        hit_testable=False,
                    )
                )
            root.add(
                _text(
                    f"{self.key}:segment:{index}:label",
                    Rect(
                        cell.x + 8.0,
                        cell.y + 7.0,
                        max(0.0, cell.width - 16.0),
                        15.0,
                    ),
                    label.upper(),
                    9.0,
                    _MUTED,
                    self._font_family,
                )
            )
            root.add(
                _text(
                    f"{self.key}:segment:{index}:value",
                    Rect(
                        cell.x + 8.0,
                        cell.y + 24.0,
                        max(0.0, cell.width - 16.0),
                        24.0,
                    ),
                    value,
                    16.0,
                    _ACCENT if index == self._active_segment else _FOREGROUND,
                    self._font_family,
                )
            )
        return root

    def accessibility_snapshot(
        self,
        *,
        focused: Component | None = None,
    ) -> AccessibilityNode:
        values = self._value_texts()
        children = tuple(
            AccessibilityNode(
                key=f"{self.key}:a11y:{segment}",
                role=AccessibilityRole.CELL,
                name=segment.capitalize(),
                description="Editable picker segment",
                enabled=self.enabled,
                focusable=False,
                focused=False,
                selected=index == self._active_segment,
                active=index == self._active_segment,
                column_index=index,
                column_count=len(self._segments),
                value_text=values[index],
            )
            for index, segment in enumerate(self._segments)
        )
        return AccessibilityNode(
            key=self.key,
            role=AccessibilityRole.GROUP,
            name=self.accessible_name or self.name,
            description=self.accessible_description,
            enabled=self.enabled,
            focusable=self.focusable,
            focused=focused is self,
            value_text=self.accessible_value_text,
            column_count=len(self._segments),
            children=children,
        )

    def _on_pointer_down(self, event: Event) -> None:
        platform = _platform_event(event, PlatformEventKind.POINTER_DOWN)
        if (
            platform is None
            or not self.enabled
            or platform.button is not PointerButton.LEFT
            or platform.x is None
            or platform.y is None
            or not self.bounds.x <= platform.x < self.bounds.right
            or not self.bounds.y <= platform.y < self.bounds.bottom
        ):
            return
        width = self.bounds.width / len(self._segments)
        self._active_segment = min(
            len(self._segments) - 1,
            max(0, int((platform.x - self.bounds.x) // width)),
        )
        direction = 1 if platform.y < self.bounds.y + self.bounds.height * 0.5 else -1
        self._adjust_active(direction)
        self.invalidate(reason="active_segment")
        event.prevent_default()

    def _on_key_down(self, event: Event) -> None:
        platform = _platform_event(event, PlatformEventKind.KEY_DOWN)
        if platform is None or not self.enabled:
            return
        if platform.alt or platform.ctrl or platform.meta:
            return
        key_code = platform.key_code
        if key_code in {_VK_RETURN, _VK_SPACE}:
            self._activate()
        elif key_code == _VK_LEFT:
            self._active_segment = (self._active_segment - 1) % len(self._segments)
            self.invalidate(reason="active_segment")
        elif key_code == _VK_RIGHT:
            self._active_segment = (self._active_segment + 1) % len(self._segments)
            self.invalidate(reason="active_segment")
        elif key_code == _VK_UP:
            self._adjust_active(1)
        elif key_code == _VK_DOWN:
            self._adjust_active(-1)
        elif key_code in {_VK_PRIOR, _VK_NEXT, _VK_HOME, _VK_END}:
            if not self._special_key(key_code):
                return
        else:
            return
        event.prevent_default()

    def _value_texts(self) -> tuple[str, ...]:
        raise NotImplementedError

    def _adjust_active(self, amount: int) -> None:
        raise NotImplementedError

    def _activate(self) -> None:
        raise NotImplementedError

    def _special_key(self, key_code: int) -> bool:
        del key_code
        return False


class DatePicker(_SegmentPicker):
    """Segmented retained date picker with bounded year/month/day editing."""

    def __init__(
        self,
        *,
        bounds: Rect,
        value: date | None = None,
        min_date: date | None = None,
        max_date: date | None = None,
        key: str | None = None,
        font_family: str = "Segoe UI",
        opacity: float = 1.0,
        z_index: int = 0,
        accessible_name: str = "Date picker",
        accessible_description: str | None = None,
    ) -> None:
        self._min_date, self._max_date = Calendar._validate_range(min_date, max_date)
        self._value = self._clamp(value or date.today())
        super().__init__(
            bounds=bounds,
            segments=("year", "month", "day"),
            active_segment=2,
            key=key,
            font_family=font_family,
            opacity=opacity,
            z_index=z_index,
            accessible_name=accessible_name,
            accessible_description=accessible_description,
        )
        self._sync_accessibility()

    @property
    def value(self) -> date:
        return self._value

    def set_value(self, value: date) -> DatePicker:
        if not isinstance(value, date):
            raise TypeError("value must be datetime.date.")
        value = self._clamp(value)
        if value == self._value:
            return self
        previous = self._value
        self._value = value
        self._sync_accessibility()
        self.invalidate(reason="date_value")
        self.emit("date_changed", value=value, previous=previous)
        return self

    def adjust_active(self, amount: int) -> DatePicker:
        self._adjust_active(amount)
        return self

    def activate(self) -> DatePicker:
        self._activate()
        return self

    def _value_texts(self) -> tuple[str, ...]:
        return (
            f"{self._value.year:04d}",
            f"{self._value.month:02d}",
            f"{self._value.day:02d}",
        )

    def _adjust_active(self, amount: int) -> None:
        step = int(amount)
        if step == 0:
            return
        if self.active_segment == "year":
            target = _shift_years(self._value, step)
        elif self.active_segment == "month":
            target = _shift_months(self._value, step)
        else:
            target = _shift_days(self._value, step)
        self.set_value(target)

    def _activate(self) -> None:
        self.emit("date_activated", value=self._value)

    def _special_key(self, key_code: int) -> bool:
        if key_code == _VK_PRIOR:
            self.set_value(_shift_months(self._value, -1))
        elif key_code == _VK_NEXT:
            self.set_value(_shift_months(self._value, 1))
        elif key_code == _VK_HOME and self._min_date is not None:
            self.set_value(self._min_date)
        elif key_code == _VK_END and self._max_date is not None:
            self.set_value(self._max_date)
        else:
            return False
        return True

    def _clamp(self, value: date) -> date:
        if self._min_date is not None and value < self._min_date:
            return self._min_date
        if self._max_date is not None and value > self._max_date:
            return self._max_date
        return value

    def _sync_accessibility(self) -> None:
        self.accessible_value_text = self._value.isoformat()


class TimePicker(_SegmentPicker):
    """Segmented 24-hour retained time picker with deterministic stepping."""

    def __init__(
        self,
        *,
        bounds: Rect,
        value: time | None = None,
        minute_step: int = 1,
        show_seconds: bool = False,
        second_step: int = 1,
        key: str | None = None,
        font_family: str = "Segoe UI",
        opacity: float = 1.0,
        z_index: int = 0,
        accessible_name: str = "Time picker",
        accessible_description: str | None = None,
    ) -> None:
        self._minute_step = self._validate_step(minute_step, "minute_step")
        self._second_step = self._validate_step(second_step, "second_step")
        self._show_seconds = bool(show_seconds)
        self._value = self._normalize(value or time(0, 0))
        segments = ("hour", "minute", "second") if self._show_seconds else ("hour", "minute")
        super().__init__(
            bounds=bounds,
            segments=segments,
            active_segment=1,
            key=key,
            font_family=font_family,
            opacity=opacity,
            z_index=z_index,
            accessible_name=accessible_name,
            accessible_description=accessible_description,
        )
        self._sync_accessibility()

    @property
    def value(self) -> time:
        return self._value

    @property
    def show_seconds(self) -> bool:
        return self._show_seconds

    def set_value(self, value: time) -> TimePicker:
        if not isinstance(value, time):
            raise TypeError("value must be datetime.time.")
        value = self._normalize(value)
        if value == self._value:
            return self
        previous = self._value
        self._value = value
        self._sync_accessibility()
        self.invalidate(reason="time_value")
        self.emit("time_changed", value=value, previous=previous)
        return self

    def adjust_active(self, amount: int) -> TimePicker:
        self._adjust_active(amount)
        return self

    def activate(self) -> TimePicker:
        self._activate()
        return self

    def _value_texts(self) -> tuple[str, ...]:
        values = [f"{self._value.hour:02d}", f"{self._value.minute:02d}"]
        if self._show_seconds:
            values.append(f"{self._value.second:02d}")
        return tuple(values)

    def _adjust_active(self, amount: int) -> None:
        direction = 1 if int(amount) > 0 else -1 if int(amount) < 0 else 0
        if direction == 0:
            return
        seconds = self._value.hour * 3600 + self._value.minute * 60 + self._value.second
        if self.active_segment == "hour":
            delta = 3600 * direction
        elif self.active_segment == "minute":
            delta = self._minute_step * 60 * direction
        else:
            delta = self._second_step * direction
        seconds = (seconds + delta) % 86400
        hour, remainder = divmod(seconds, 3600)
        minute, second = divmod(remainder, 60)
        self.set_value(time(hour, minute, second))

    def _activate(self) -> None:
        self.emit("time_activated", value=self._value)

    def _special_key(self, key_code: int) -> bool:
        if key_code == _VK_HOME:
            self.set_value(time(0, 0, 0))
        elif key_code == _VK_END:
            second = 59 if self._show_seconds else 0
            self.set_value(time(23, 59, second))
        else:
            return False
        return True

    def _normalize(self, value: time) -> time:
        minute = (value.minute // self._minute_step) * self._minute_step
        if self._show_seconds:
            second = (value.second // self._second_step) * self._second_step
        else:
            second = 0
        return time(value.hour, minute, second, fold=value.fold)

    @staticmethod
    def _validate_step(value: int, name: str) -> int:
        value = int(value)
        if value <= 0 or value >= 60 or 60 % value != 0:
            raise ValueError(f"{name} must be a positive divisor of 60 smaller than 60.")
        return value

    def _sync_accessibility(self) -> None:
        timespec = "seconds" if self._show_seconds else "minutes"
        self.accessible_value_text = self._value.isoformat(timespec=timespec)
