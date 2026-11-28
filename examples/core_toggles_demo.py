"""Try locked radio, switch and checkbox settings in two authored palettes."""

from dataclasses import replace

from swirui import (
    FUTURE_DARK,
    FUTURE_LIGHT,
    App,
    Checkbox,
    Label,
    Panel,
    RadioButton,
    SilkRibbon,
    SurfaceStyle,
    Switch,
    ThemeSurface,
    Window,
    mount,
    state_transaction,
)
from swirui.rendering import Rect

app = App("SwirUI retained toggles")
window = app.add_window(Window(title="SwirUI — Rendering preferences", width=640, height=374,
                               min_width=640, min_height=374))
dark = FUTURE_DARK.with_accent("#AFC3FF")
light = FUTURE_LIGHT.with_accent("#4A61B0")
dark = replace(dark, palette=replace(dark.palette, disabled="#29354C", disabled_text="#B5C3DE"))
light = replace(light, palette=replace(light.palette, disabled="#E0E6F4", disabled_text="#4F607C"))
root = Panel(bounds=Rect(0, 0, 640, 374), theme=dark)
card = ThemeSurface(bounds=Rect(28, 92, 584, 176),
                    style=SurfaceStyle(kind="glass", tint_opacity=.90, elevation=4))
telemetry = Checkbox("Renderer telemetry", key="telemetry", bounds=Rect(305, 150, 275, 40))
quality_balanced = RadioButton("Balanced", key="balanced", bounds=Rect(52, 150, 210, 40),
                               checked=True, group="quality")
quality_ultra = RadioButton("Ultra", key="ultra", bounds=Rect(52, 204, 210, 40), group="quality")
high_refresh = Switch("High refresh rate", key="high-refresh", bounds=Rect(305, 204, 275, 40),
                      checked=True)
locked = Checkbox("Lock settings", key="lock", bounds=Rect(32, 278, 204, 40))
appearance = Switch("Light appearance", key="appearance", bounds=Rect(305, 278, 275, 40))
status = Label("Tab to a setting. Use arrows for quality or Space to toggle.",
               bounds=Rect(32, 329, 580, 32),
               font_size=14)

card.add(Label("Render quality", bounds=Rect(52, 111, 210, 32), font_size=20),
         quality_balanced, quality_ultra,
         Label("Presentation", bounds=Rect(305, 111, 275, 32), font_size=20),
         telemetry, high_refresh)
root.add(SilkRibbon(bounds=Rect(347, 0, 290, 162)),
         Label("Rendering preferences", bounds=Rect(30, 23, 375, 50), font_size=30),
         card, locked, appearance, status)
mount(window, root)


def update_status(*_args: object) -> None:
    quality = "Ultra" if quality_ultra.checked else "Balanced"
    status.text = (f"{quality} quality  ·  Telemetry {'on' if telemetry.checked else 'off'}"
                   f"  ·  High refresh {'on' if high_refresh.checked else 'off'}")


settings = (quality_balanced, quality_ultra, telemetry, high_refresh)


def set_locked(*_args: object) -> None:
    with state_transaction():
        for control in settings:
            control.enabled = not locked.checked
        update_status()


def set_appearance(*_args: object) -> None:
    root.theme = light if appearance.checked else dark


for control in settings:
    control.on("changed", update_status)
locked.on("changed", set_locked)
appearance.on("changed", set_appearance)
app.run()
