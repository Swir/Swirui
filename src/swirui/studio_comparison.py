"""Native appearance previews for Studio designs and saved theme packages."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from . import (
    App,
    Badge,
    Button,
    Input,
    Label,
    Panel,
    SilkRibbon,
    ThemePackage,
    ThemeSurface,
    Window,
)
from .core import Event, state_transaction
from .core.state import schedule_reactive_update
from .rendering import Rect, WgpuRenderer
from .widgets import mount
from .widgets.measurement import measure_text_block

if TYPE_CHECKING:
    from collections.abc import Mapping

    from .studio import StudioPreview
    from .theme import Theme


class _AppearancePane(Panel):
    def __init__(self, mode: str) -> None:
        empty = Rect(0, 0, 0, 0)
        super().__init__(bounds=empty, clip_to_bounds=True)
        self.mode = mode
        label = f"{mode.title()} appearance" if mode in ("dark", "light") else mode
        self.mode_label = Badge(label, bounds=empty)
        self._badge_width = max(150, measure_text_block(label, font_size=13).width + 16)
        self.title = Label("", bounds=empty, font_size=31)
        self.ribbon = SilkRibbon(bounds=empty)
        self.card = ThemeSurface(bounds=empty)
        self.headline = Label("", bounds=empty, font_size=23)
        self.caption = Label("Project name", bounds=empty, font_size=13)
        self.field = Input("", bounds=empty, accessible_name=f"{mode.title()} preview project name")
        self.apply = Button("Apply name", bounds=empty)
        self.card.add(self.headline, self.caption, self.field, self.apply)
        self.add(self.ribbon, self.mode_label, self.title, self.card)

    def prepare_layout(self, viewport: Rect) -> None:
        self._set_layout_bounds(viewport)
        x, y, w, h = viewport.x, viewport.y, viewport.width, viewport.height
        pad = 20 if w < 400 else 32
        inner = max(0, w - 2 * pad)
        self.mode_label._set_layout_bounds(Rect(x + pad, y + 20, min(inner, self._badge_width), 30))
        self.title._set_layout_bounds(Rect(x + pad, y + 59, inner, 48))
        card_y = y + max(131, (h - 220) * .72)
        self.ribbon._set_layout_bounds(Rect(x + 3, max(y + 94, card_y - 70), max(0, w - 6), 200))
        self.card._set_layout_bounds(Rect(x + pad, card_y, inner, 220))
        left = x + pad + 19
        content = max(0, inner - 38)
        self.headline._set_layout_bounds(Rect(left, card_y + 16, content, 35))
        self.caption._set_layout_bounds(Rect(left, card_y + 63, content, 20))
        self.field._set_layout_bounds(Rect(left, card_y + 88, content, 40))
        self.apply._set_layout_bounds(Rect(left, card_y + 152, min(content, 128), 40))


class AppearanceComparison(Panel):
    """One or two interactive instances of the same form using authored themes."""

    def __init__(self, package: ThemePackage, headline: str, *,
                 variants: tuple[str, ...] = ("dark", "light")) -> None:
        if len(variants) not in (1, 2) or len(set(variants)) != len(variants):
            raise ValueError("Choose one or two distinct variant keys.")
        for key in variants:
            if key not in package.themes:
                raise ValueError(f"Unknown variant {key!r}. Available: {', '.join(package.themes)}")
        super().__init__(bounds=Rect(0, 0, 960, 460))
        self.panes = tuple(_AppearancePane(key) for key in variants)
        self.add(*self.panes)
        for pane in self.panes:
            pane.field.on("submitted", self._rename)
            pane.apply.on("click", self._rename)
        self.set_design(package, headline)

    def set_design(self, package: ThemePackage, headline: str) -> None:
        with state_transaction():
            self.set_appearance(package.themes, headline)
            for pane in self.panes:
                pane.title.text = pane.field.value = package.name

    def set_appearance(self, themes: Mapping[str, Theme], headline: str) -> None:
        with state_transaction():
            for pane in self.panes:
                pane.theme = themes[pane.mode]
                pane.headline.text = headline

    def _rename(self, event: Event) -> None:
        source = next(p for p in self.panes if event.source in (p.field, p.apply))
        name = source.field.value.strip()
        if name:
            with state_transaction():
                for pane in self.panes:
                    pane.title.text = pane.field.value = name
        else:
            source.field.value = source.title.text

    def prepare_layout(self, viewport: Rect) -> None:
        self._set_layout_bounds(viewport)
        width = viewport.width / len(self.panes)
        for index, pane in enumerate(self.panes):
            pane._set_layout_bounds(Rect(viewport.x + index * width, viewport.y, width,
                                         viewport.height))


def run_package_preview(root: AppearanceComparison, *, smoke_test: bool = False) -> int:
    """Display an interactive sample without modifying the source package."""
    count = len(root.panes)
    renderer = WgpuRenderer()
    app = App("SwirUI theme preview", renderer=renderer)
    window = app.add_window(Window(title=f"{root.panes[0].title.text} · Theme preview",
                                   width=480 * count, height=460,
                                   min_width=320 * count, min_height=390))
    mount(window, root)
    try:
        if not smoke_test:
            return app.run()
        app.start()
        app.process_events()
        if renderer.frames_rendered < 1 or not renderer.adapter_name:
            raise RuntimeError("No native theme preview frame was rendered")
        print(json.dumps({"rendered": True, "adapter": renderer.adapter_name,
                          "backend": renderer.graphics_backend,
                          "variants": [pane.mode for pane in root.panes]}))
        return 0
    finally:
        app.stop()


def bind_comparison(app: App, owner: Window, preview: StudioPreview) -> None:
    """Open at most one comparison window for this Studio session."""
    child: Window | None = None

    def closed(event: Event) -> None:
        nonlocal child
        if child is not None and event.source is child:
            window, child = child, None
            if window in app.windows:
                app.remove_window(window)

    def launch(_event: Event) -> None:
        nonlocal child
        try:
            package = preview.theme_package()
        except ValueError:
            preview.result.text = "Use a valid project name (up to 120 characters)."
            return
        title = f"{package.name} · Appearance comparison"
        if child is not None and isinstance(child.root, AppearanceComparison):
            child.root.set_design(package, preview.heading.text)
            child.set_title(title)
            if child.visible and child.native_handle is not None:
                app.platform_backend.show_window(child.native_handle)
            else:
                child.show()
            preview.result.text = "Comparison updated."
            return
        window = Window(title=title, width=960, height=460, min_width=640, min_height=390)
        mount(window, AppearanceComparison(package, preview.heading.text))
        try:
            app.add_window(window)
        except (OSError, RuntimeError):
            if window in app.windows:
                app.remove_window(window)
            preview.result.text = "Could not open the comparison window. Try again."
            return
        window.on("closed", closed)
        child = window
        preview.result.text = "Comparison opened."

    def refresh() -> None:
        if child is not None and isinstance(child.root, AppearanceComparison):
            child.root.set_appearance(preview.appearance_themes(), preview.heading.text)

    def design_changed(_event: Event) -> None:
        if child is not None:
            schedule_reactive_update(refresh, refresh)

    stop_launch = preview.on("launch_requested", launch)
    stop_updates = preview.on("design_changed", design_changed)

    def owner_closed(_event: Event) -> None:
        stop_launch()
        stop_updates()
        if child is not None:
            child.close()

    owner.on("closed", owner_closed)
