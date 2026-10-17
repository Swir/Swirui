"""Interactive native core-widget gallery. Install the native wheel before running."""

from swirui import (
    FUTURE_DARK,
    FUTURE_LIGHT,
    App,
    Badge,
    Button,
    ButtonVariant,
    Card,
    Chip,
    Component,
    Dialog,
    Expander,
    GlassCard,
    Input,
    Label,
    Panel,
    ProgressBar,
    ProgressRing,
    Slider,
    SplitView,
    Toast,
    Tooltip,
    Window,
    mount,
    state_transaction,
)
from swirui.rendering import Rect, WgpuRenderer


class Gallery(Panel):
    """Retained controls share one scope; mode changes never recreate content."""

    def __init__(self) -> None:
        super().__init__(bounds=Rect(0, 0, 1200, 820), theme=FUTURE_DARK)
        self.mode = Button(
            "Light theme", bounds=Rect(1016, 32, 152, 40), variant=ButtonVariant.SECONDARY
        )
        self.mode.on("click", lambda _: self.toggle_theme())
        self.add(
            Label("swir / component gallery", bounds=Rect(32, 38, 600, 36), font_size=21),
            self.mode,
            Label("Built for every detail.", bounds=Rect(32, 108, 960, 56), font_size=38),
            Label(
                "Real controls. Shared colors. Your state, preserved.",
                bounds=Rect(34, 172, 980, 30),
                font_size=16,
            ),
        )
        for x, width in ((32, 352), (408, 352), (784, 384)):
            self.add(Card(bounds=Rect(x, 232, width, 536), show_shadow=False, border_width=1))
        self.add(Label("01 / SIGNAL", bounds=Rect(56, 256, 290, 28), font_size=13))
        self.progress = ProgressBar(bounds=Rect(56, 330, 304, 12), value=64)
        self.ring = ProgressRing(bounds=Rect(56, 370, 88, 88), value=64, thickness=7)
        self.percent = Label("64%", bounds=Rect(168, 385, 180, 40), font_size=30)
        self.slider = Slider(bounds=Rect(56, 496, 304, 32), value=64)
        self.slider.on("changed", lambda _: self.set_progress())
        self.chip = Chip("Pinned", bounds=Rect(56, 566, 138, 40), selected=True)
        self.add(
            Label("Progress, with purpose", bounds=Rect(56, 296, 300, 28), font_size=18),
            self.progress,
            self.ring,
            self.percent,
            self.slider,
            self.chip,
            Badge("Native GPU", bounds=Rect(208, 572, 150, 30)),
            Label("Drag the slider. Toggle the chip.", bounds=Rect(56, 640, 298, 50), font_size=14),
        )
        self.add(Label("02 / STRUCTURE", bounds=Rect(432, 256, 304, 28), font_size=13))
        self.field = Input("A place for your ideas", bounds=Rect(432, 358, 304, 44))
        self.expander = Expander(
            "Workspace details", bounds=Rect(432, 304, 304, 44), content=self.field, expanded=True
        )
        first = GlassCard(bounds=Rect(0, 0, 310, 160))
        first.add(Label("Canvas", bounds=Rect(14, 18, 200, 24), font_size=16))
        second = Panel(bounds=Rect(0, 0, 310, 160))
        second.add(Label("Inspector", bounds=Rect(14, 18, 200, 24), font_size=16))
        self.split = SplitView(
            bounds=Rect(432, 448, 304, 160),
            first=first,
            second=second,
            split_ratio=0.5,
            divider_size=6,
        )
        self.add(
            self.expander,
            self.split,
            Label(
                "Resize the divider, or use arrow keys.\n"
                "Collapse details without losing your text.",
                bounds=Rect(432, 640, 304, 80),
                font_size=14,
            ),
        )
        self.add(Label("03 / FEEDBACK", bounds=Rect(808, 256, 336, 28), font_size=13))
        self.toast = Toast(
            "Your workspace is ready.",
            title="Looking good",
            kind="success",
            bounds=Rect(808, 304, 336, 100),
            dismiss_on_click=False,
            z_index=0,
        )
        self.notice = Button(
            "Next status", bounds=Rect(808, 428, 158, 40), variant=ButtonVariant.SECONDARY
        )
        self.notice.on("click", lambda _: self.next_status())
        self.help = Button(
            "Focus for help", bounds=Rect(978, 428, 166, 40), variant=ButtonVariant.GHOST
        )
        self.tip = Tooltip(
            "Your work stays right here.", bounds=Rect(808, 488, 336, 44), target=self.help
        )
        self.open_dialog = Button("Open dialog", bounds=Rect(808, 566, 336, 44))
        self.open_dialog.on("click", lambda _: self.show_dialog())
        self.add(
            self.toast,
            self.notice,
            self.help,
            self.tip,
            self.open_dialog,
            Label(
                "Try another theme at any moment.\nValues, text and selection stay intact.",
                bounds=Rect(808, 640, 336, 80),
                font_size=14,
            ),
        )
        self.window: Window | None = None
        content = Component()
        self.close_dialog = Button("Back to the gallery", bounds=Rect(32, 166, 416, 44))
        self.close_dialog.on("click", lambda _: self.hide_dialog())
        content.add(
            Label("Room to focus.", bounds=Rect(32, 28, 416, 44), font_size=30),
            Label(
                "This dialog inherits the same visual language.",
                bounds=Rect(32, 98, 416, 44),
                font_size=16,
            ),
            self.close_dialog,
        )
        self.dialog = Dialog(
            bounds=self.bounds,
            dialog_bounds=Rect(360, 280, 480, 244),
            content=content,
            open=False,
            dismiss_on_backdrop=False,
        )
        self.dialog.on("dismissed", lambda _: self.restore_focus())
        self.add(
            self.dialog,
            Label(
                "SWIRUI / NATIVE PYTHON      •      Tab to explore. Enter to activate.",
                bounds=Rect(34, 788, 1120, 26),
                font_size=12,
            ),
        )

    def toggle_theme(self) -> None:
        with state_transaction():
            self.theme = FUTURE_LIGHT if self.theme == FUTURE_DARK else FUTURE_DARK
            self.mode.text = "Dark theme" if self.theme == FUTURE_LIGHT else "Light theme"

    def set_progress(self) -> None:
        with state_transaction():
            self.progress.value = self.ring.value = self.slider.value
            self.percent.text = f"{self.slider.value:.0f}%"

    def next_status(self) -> None:
        kinds = ("success", "info", "warning", "error")
        self.toast.kind = kinds[(kinds.index(self.toast.kind) + 1) % len(kinds)]
        self.toast.title = {
            "success": "Looking good",
            "info": "A little update",
            "warning": "Worth a look",
            "error": "Let's try again",
        }[self.toast.kind]

    def show_dialog(self) -> None:
        self.dialog.show()
        if self.window:
            self.window.focus_component(self.close_dialog)

    def hide_dialog(self) -> None:
        self.dialog.dismiss()

    def restore_focus(self) -> None:
        if self.window:
            self.window.focus_component(self.open_dialog)


def main() -> int:
    app = App("SwirUI component gallery", renderer=WgpuRenderer())
    window = Window(
        title="SwirUI — Component gallery", width=1200, height=820, min_width=1200, min_height=820
    )
    gallery = Gallery()
    gallery.window = window
    mount(window, gallery)
    app.add_window(window)
    return app.run()


if __name__ == "__main__":
    raise SystemExit(main())
