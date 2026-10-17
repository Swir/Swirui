"""Nine live appearance presets with optional motion and persistent controls."""

from dataclasses import replace

from swirui import (
    THEME_PRESETS,
    AnimationController,
    App,
    Button,
    ButtonVariant,
    Card,
    Input,
    Label,
    Panel,
    Switch,
    ThemeController,
    Window,
    mount,
    state_transaction,
)
from swirui.core import Event
from swirui.rendering import Rect, WgpuRenderer


def main() -> int:
    app = App("SwirUI Theme Gallery", renderer=WgpuRenderer())
    window = app.add_window(Window(title="SwirUI — Theme Gallery", width=1080, height=760,
                                   min_width=1080, min_height=760))
    root = Panel(bounds=Rect(0, 0, 1080, 760))
    selected = "future_dark"
    choices = {
        key: Button(key.replace("_", " ").title(),
                    bounds=Rect(40 + index % 3 * 336, 180 + index // 3 * 60, 320, 48),
                    variant=ButtonVariant.SECONDARY)
        for index, key in enumerate(THEME_PRESETS)
    }
    status = Label("Future Dark", bounds=Rect(64, 418, 560, 42), font_size=28)
    draft = Input("My next big idea", bounds=Rect(64, 484, 568, 48), font_size=20)
    preview = Card(bounds=Rect(40, 394, 616, 290), show_shadow=False)
    preview.add(status, draft,
                Switch("Keep me in the flow", checked=True, bounds=Rect(64, 550, 560, 44)),
                Button("Make it happen", bounds=Rect(64, 612, 240, 48)))
    details = Card(bounds=Rect(680, 394, 360, 290), show_shadow=False)
    reduced = Switch("Reduce motion", bounds=Rect(704, 484, 312, 44))
    details.add(
        Label("Your rhythm.", bounds=Rect(704, 418, 312, 44), font_size=28),
        reduced,
        Label("Same workspace.\nA different feeling.",
              bounds=Rect(704, 552, 312, 72), font_size=19),
    )
    root.add(
        Label("swir / expressive by design", bounds=Rect(40, 24, 1000, 36), font_size=19),
        Label("Find your signature.", bounds=Rect(40, 78, 1000, 64), font_size=40),
        *choices.values(), preview, details,
        Label("Try a new look. Your ideas stay right where you left them.",
              bounds=Rect(40, 712, 1000, 28), font_size=16),
    )
    mount(window, root)
    animations = AnimationController(app, window)
    controller = ThemeController(window, mode="dark", animations=animations)

    def choose(key: str) -> None:
        nonlocal selected
        selected = key
        theme = replace(THEME_PRESETS[key], reduced_motion=reduced.checked)
        with state_transaction():
            controller.set_themes(light=theme, dark=theme)
            status.text = key.replace("_", " ").title()
            for name, button in choices.items():
                button.variant = (ButtonVariant.PRIMARY if name == key
                                  else ButtonVariant.SECONDARY)

    def motion_changed(event: Event) -> None:
        choose(selected)

    for key, button in choices.items():
        button.on("click", lambda _, key=key: choose(key))
    reduced.on("changed", motion_changed)
    window.on("closed", lambda _: animations.dispose())
    choose(selected)
    window.focus_component(draft)
    return app.run()


if __name__ == "__main__":
    raise SystemExit(main())
