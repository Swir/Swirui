"""Calendar, DatePicker and TimePicker demo for professional SwirUI applications."""

from datetime import date, time

from swirui import App, Calendar, DatePicker, Panel, TimePicker, Window, mount
from swirui.rendering import Rect


def main() -> None:
    app = App("SwirUI Date and Time")
    window = app.add_window(
        Window(title="SwirUI Professional Date / Time", width=820, height=620)
    )
    root = Panel(
        bounds=Rect(0.0, 0.0, 820.0, 620.0),
        key="date-time-demo",
    )

    calendar = Calendar(
        bounds=Rect(90.0, 55.0, 640.0, 390.0),
        selected_date=date.today(),
        key="demo-calendar",
    )
    date_picker = DatePicker(
        bounds=Rect(90.0, 475.0, 350.0, 66.0),
        value=date.today(),
        key="demo-date-picker",
    )
    time_picker = TimePicker(
        bounds=Rect(470.0, 475.0, 260.0, 66.0),
        value=time(10, 30),
        minute_step=5,
        key="demo-time-picker",
    )

    calendar.on(
        "date_changed",
        lambda event: print("Calendar:", event.data["value"]),
    )
    date_picker.on(
        "date_changed",
        lambda event: print("Date picker:", event.data["value"]),
    )
    time_picker.on(
        "time_changed",
        lambda event: print("Time picker:", event.data["value"]),
    )

    root.add(calendar, date_picker, time_picker)
    mount(window, root)
    app.run()


if __name__ == "__main__":
    main()
