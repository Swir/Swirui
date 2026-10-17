"""Native calendar, date/time and color controls with live appearance switching."""

from datetime import date, time

from swirui import (
    FUTURE_DARK,
    FUTURE_LIGHT,
    App,
    Button,
    Calendar,
    ColorPicker,
    DatePicker,
    Label,
    Panel,
    TimePicker,
    Window,
    mount,
    state_transaction,
)
from swirui.rendering import Color, Rect, WgpuRenderer


def main() -> int:
    root = Panel(bounds=Rect(0, 0, 1160, 760), theme=FUTURE_DARK)
    calendar = Calendar(
        bounds=Rect(32, 208, 436, 336), selected_date=date(2026, 10, 16),
        accessible_name="Choose a day",
    )
    day = DatePicker(bounds=Rect(32, 556, 436, 64), value=calendar.selected_date)
    clock = TimePicker(bounds=Rect(32, 636, 436, 64), value=time(10, 30), show_seconds=True)
    color = ColorPicker(bounds=Rect(500, 208, 628, 336), value=Color.from_hex("#B6A0FFCC"))
    summary = Label("", bounds=Rect(520, 586, 588, 100), font_size=20)
    appearance = Button("Light appearance", bounds=Rect(888, 26, 240, 44))

    def refresh() -> None:
        summary.text = (
            f"{day.value:%d %B %Y}  /  {clock.value:%H:%M:%S}\n"
            f"Your color: {color.hex_value}"
        )

    def switch_appearance() -> None:
        with state_transaction():
            root.theme = FUTURE_LIGHT if root.theme == FUTURE_DARK else FUTURE_DARK
            appearance.text = (
                "Dark appearance" if root.theme == FUTURE_LIGHT else "Light appearance"
            )

    calendar.on("date_changed", lambda event: day.set_value(event.data["value"]))
    day.on("date_changed", lambda event: calendar.set_selected_date(event.data["value"]))
    for control, event in (
        (day, "date_changed"), (clock, "time_changed"), (color, "color_changed")
    ):
        control.on(event, lambda _: refresh())
    appearance.on("click", lambda _: switch_appearance())
    root.add(
        Label("swir / details", bounds=Rect(32, 30, 500, 36), font_size=20),
        Label("Your day, your colors.", bounds=Rect(32, 88, 1060, 64), font_size=42),
        Label("A moment in time", bounds=Rect(32, 166, 436, 30), font_size=18),
        Label("Find your shade", bounds=Rect(500, 166, 628, 30), font_size=18),
        calendar, day, clock, color, summary, appearance,
        Label(
            "Tab to explore. Arrow keys to adjust. Drag a color track to make it yours.",
            bounds=Rect(32, 724, 1096, 28), font_size=15,
        ),
    )
    refresh()
    window = Window(
        title="SwirUI — Details", width=1160, height=760, min_width=1160, min_height=760
    )
    mount(window, root)
    window.focus_component(calendar)
    app = App("SwirUI Details", renderer=WgpuRenderer())
    app.add_window(window)
    return app.run()


if __name__ == "__main__":
    raise SystemExit(main())
