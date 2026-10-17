"""Live application appearance choices with read-only Windows synchronization."""

from swirui import (
    FUTURE_DARK,
    App,
    Button,
    ButtonVariant,
    Card,
    Input,
    Label,
    Panel,
    Switch,
    ThemeController,
    ThemeMode,
    Window,
    mount,
    state_transaction,
)
from swirui.core import Event
from swirui.rendering import Rect, WgpuRenderer


def main() -> int:
    root = Panel(bounds=Rect(0, 0, 1000, 700))
    window = Window(title="SwirUI — Appearance", width=1000, height=700,
                    min_width=1000, min_height=700)
    choices = {
        mode: Button(label, bounds=Rect(40 + index * 200, 188, 180, 48),
                     variant=ButtonVariant.SECONDARY)
        for index, (mode, label) in enumerate([
            (ThemeMode.SYSTEM, "Use system"), (ThemeMode.LIGHT, "Light"), (ThemeMode.DARK, "Dark")
        ])
    }
    status = Label("", bounds=Rect(40, 252, 900, 28), font_size=16)
    draft = Input("Aurora workspace", bounds=Rect(64, 388, 512, 48), font_size=19)
    preview = Card(bounds=Rect(40, 320, 560, 290), show_shadow=False)
    preview.add(
        Label("Your workspace", bounds=Rect(64, 340, 512, 36), font_size=24), draft,
        Switch("Keep notifications on", bounds=Rect(64, 462, 430, 44), checked=True),
        Button("Create something", bounds=Rect(64, 534, 220, 48)),
    )
    pinned = Card(bounds=Rect(632, 320, 328, 290), theme=FUTURE_DARK, show_shadow=False)
    pinned.add(
        Label("A space of its own", bounds=Rect(656, 344, 280, 40), font_size=23),
        Label("This panel keeps its dark theme.", bounds=Rect(656, 400, 280, 60), font_size=16),
        Label("Your app can mix local styles\nwith a shared appearance.",
              bounds=Rect(656, 466, 280, 70), font_size=16),
    )
    root.add(
        Label("swir / appearance", bounds=Rect(40, 30, 800, 36), font_size=20),
        Label("Make yourself at home.", bounds=Rect(40, 90, 900, 64), font_size=40),
        *choices.values(), status, preview, pinned,
        Label("Edit your workspace name. Switch looks. Your draft stays with you.",
              bounds=Rect(40, 644, 920, 32), font_size=16),
    )
    mount(window, root)
    controller = ThemeController(window)

    def update_labels(event: Event | None = None) -> None:
        with state_transaction():
            for mode, button in choices.items():
                button.variant = (ButtonVariant.PRIMARY if mode is controller.mode
                                  else ButtonVariant.SECONDARY)
            detected = controller.system_scheme
            if controller.mode is ThemeMode.SYSTEM:
                status.text = (
                    f"Following Windows · {controller.effective_scheme.value.title()}"
                    if detected is not None else
                    f"System appearance unavailable · {controller.fallback.value.title()}"
                )
            else:
                status.text = f"Your choice · {controller.effective_scheme.value.title()}"

    for mode, button in choices.items():
        button.on("click", lambda _, mode=mode: setattr(controller, "mode", mode))
    controller.on("changed", update_labels)
    update_labels()
    window.focus_component(draft)
    app = App("SwirUI Appearance", renderer=WgpuRenderer())
    app.add_window(window)
    return app.run()


if __name__ == "__main__":
    raise SystemExit(main())
