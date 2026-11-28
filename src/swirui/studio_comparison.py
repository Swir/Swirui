"""Native appearance previews for Studio designs and saved theme packages."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from . import (
    App,
    Badge,
    Button,
    ButtonVariant,
    Checkbox,
    CommandItem,
    CommandPalette,
    Input,
    Label,
    Modal,
    Panel,
    SilkRibbon,
    ThemePackage,
    ThemeSurface,
    Window,
)
from .core import Event, state_transaction
from .core.state import schedule_reactive_update
from .platforms import PlatformEvent
from .rendering import Rect, WgpuRenderer
from .widgets import mount
from .widgets.measurement import measure_text_block

if TYPE_CHECKING:
    from collections.abc import Mapping

    from .studio import StudioPreview
    from .theme import Theme


_MIN_PANE_WIDTH = 320
# The native backends report Win32 virtual keys, X11 keysyms and Cocoa key codes.
_F5 = {"win32": 0x74, "x11": 0xFFC2, "cocoa": 0x60}


class _AppearancePane(Panel):
    def __init__(self, mode: str, *, selectable: bool) -> None:
        empty = Rect(0, 0, 0, 0)
        super().__init__(bounds=empty, clip_to_bounds=True)
        self.badge = Badge("", bounds=empty, accessible_name="Appearance")
        self.variant_button = Button("", bounds=empty, variant=ButtonVariant.SECONDARY,
                                     text_align="center", padding=5, font_size=13,
                                     accessible_name="Choose variant")
        self.title = Label("", bounds=empty, font_size=31, min_font_size=16, clip_to_bounds=True)
        self.ribbon = SilkRibbon(bounds=empty)
        self.card = ThemeSurface(bounds=empty)
        self.headline = Label("", bounds=empty, font_size=23, min_font_size=15, clip_to_bounds=True)
        self.caption = Label("Project name", bounds=empty, font_size=13)
        self.field = Input("", bounds=empty)
        self.apply = Button("Apply name", bounds=empty, text_align="center")
        self.disable_form = Checkbox("Disable form", bounds=empty, font_size=13)
        self.disable_form.on("changed", self._change_form_state)
        self.card.add(self.headline, self.caption, self.field, self.apply, self.disable_form)
        self.add(self.ribbon, self.badge, self.variant_button, self.title, self.card)
        self.set_mode(mode, selectable=selectable)

    @property
    def mode_label(self) -> Badge | Button:
        return self.variant_button if self.variant_button.visible else self.badge

    def set_mode(self, mode: str, *, selectable: bool) -> None:
        self.variant_button.visible = selectable
        self.badge.visible = not selectable
        self.mode = mode
        short = mode.title() if mode in ("dark", "light") else mode
        full = f"{short} appearance" if mode in ("dark", "light") else mode
        self._short_label = f"{short}  ▾" if selectable else short
        self._full_label = f"{full}  ▾" if selectable else full
        self.mode_label.text = self._full_label
        self.mode_label.accessible_name = f"Choose variant, current {mode}" if selectable else full
        self.field.accessible_name = f"{mode.title()} preview project name"
        self.disable_form.accessible_name = f"Disable {mode} preview form"
        self._badge_width = max(150, measure_text_block(self._full_label, font_size=13).width + 16)
        self._short_badge_width = max(60, measure_text_block(
            self._short_label, font_size=13).width + 16)

    def _change_form_state(self, _event: Event) -> None:
        disabled = self.disable_form.checked
        window = self.mounted_window
        with state_transaction():
            if disabled and window and window.focused_component in (self.field, self.apply):
                window.focus_component(self.disable_form)
            self.field.enabled = self.apply.enabled = not disabled

    def prepare_layout(self, viewport: Rect) -> None:
        self._set_layout_bounds(viewport)
        x, y, w, h = viewport.x, viewport.y, viewport.width, viewport.height
        compact = h < 370
        self.mode_label.text = self._short_label if compact else self._full_label
        self.title.font_size = 21 if compact else 31
        self.headline.font_size = 18 if compact else 23
        if compact:
            self._arrange_short_pane(viewport)
            return
        pad = 20 if w < 400 else 32
        inner = max(0, w - 2 * pad)
        badge_width = min(inner, self._badge_width)
        self.mode_label._set_layout_bounds(Rect(x + pad, y + 20, badge_width, 30))
        self.title._set_layout_bounds(Rect(x + pad, y + 59, inner, 48))
        card_y = y + max(131, (h - 220) * .72)
        self.ribbon._set_layout_bounds(Rect(x + 3, max(y + 94, card_y - 70), max(0, w - 6), 200))
        self.card._set_layout_bounds(Rect(x + pad, card_y, inner, 220))
        left = x + pad + 19
        content = max(0, inner - 38)
        self.headline._set_layout_bounds(Rect(left, card_y + 16, content, 35))
        self.caption._set_layout_bounds(Rect(left, card_y + 63, content, 20))
        self.field._set_layout_bounds(Rect(left, card_y + 88, content, 40))
        check_width = min(content / 2, 120)
        button_width = min(128, max(0, content - check_width - 8))
        self.apply._set_layout_bounds(Rect(left, card_y + 152, button_width, 40))
        self.disable_form._set_layout_bounds(Rect(left + content - check_width, card_y + 152,
                                                  check_width, 40))

    def _arrange_short_pane(self, viewport: Rect) -> None:
        left, top = viewport.x + 16, viewport.y
        inner = max(0, viewport.width - 32)
        badge = min(inner * .43, self._short_badge_width)
        self.mode_label._set_layout_bounds(Rect(left + inner - badge, top + 12, badge, 28))
        self.title._set_layout_bounds(Rect(left, top + 10, max(0, inner - badge - 10), 32))
        card_y = top + 52 + max(0, viewport.height - 195) * .5
        ribbon_y = max(self.title.bounds.bottom, card_y - 34)
        self.ribbon._set_layout_bounds(Rect(viewport.x + 2, ribbon_y,
                                            max(0, viewport.width - 4), 116))
        self.card._set_layout_bounds(Rect(left, card_y, inner, 139))
        content_x, content_w = left + 14, max(0, inner - 28)
        self.headline._set_layout_bounds(Rect(content_x, card_y + 9, content_w, 26))
        self.caption._set_layout_bounds(Rect(content_x, card_y + 40, content_w, 20))
        button = min(112, content_w * .42)
        field = max(0, content_w - button - 8)
        self.field._set_layout_bounds(Rect(content_x, card_y + 64, field, 38))
        self.apply._set_layout_bounds(Rect(content_x + content_w - button, card_y + 64, button, 38))
        self.disable_form._set_layout_bounds(Rect(content_x, card_y + 106, min(120, content_w), 26))


class _VariantDialog(Modal):
    def __init__(self, pane: _AppearancePane, items: list[CommandItem]) -> None:
        unit = Rect(0, 0, 1, 1)
        header, row, rows = 46, 36, min(6, len(items))
        self._natural_height = header + row * rows
        self.search = CommandPalette(items, bounds=unit, header_height=header, row_height=row,
                                     max_visible_rows=rows, empty_message="No matching variants",
                                     accessible_name="Search theme variants")
        self.search.placeholder = "Search variants…"
        super().__init__(bounds=unit, dialog_bounds=unit, content=self.search,
                         theme=pane.theme, accessible_name="Choose a theme variant")
        self.search.on("dismissed", self._search_dismissed)

    def _search_dismissed(self, _event: Event) -> None:
        self.dismiss()

    def prepare_layout(self, viewport: Rect) -> None:
        if not viewport.width or not viewport.height:
            return
        width = min(400, max(1, viewport.width - 32))
        height = min(self._natural_height, max(1, viewport.height - 32))
        self.dialog_bounds = Rect(viewport.x + (viewport.width - width) / 2,
                                  viewport.y + (viewport.height - height) / 2, width, height)
        self.search._set_layout_bounds(Rect(0, 0, width, height))


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
        selectable = len(package.themes) > len(variants)
        self.panes = tuple(self._make_pane(key, selectable=selectable) for key in variants)
        self._variant_dialog: _VariantDialog | None = None
        self.add(*self.panes)
        self.set_design(package, headline)

    def _make_pane(self, mode: str, *, selectable: bool) -> _AppearancePane:
        pane = _AppearancePane(mode, selectable=selectable)
        pane.variant_button.on("click", self._choose_variant)
        pane.field.on("submitted", self._rename)
        pane.apply.on("click", self._rename)
        return pane

    def _reload_package(self, package: ThemePackage, *, pane_limit: int) -> None:
        """Keep the visible forms and their edits when replacing a saved package."""
        count = min(pane_limit, len(package.themes))
        panes = list(self.panes)
        if len(panes) > count:
            # Prefer the surviving variant even when it occupied the second pane.
            panes = sorted(panes, key=lambda p: p.mode not in package.themes)[:count]
        preferred = dict.fromkeys((package.default_theme, *package.themes))
        retained_keys = {p.mode for p in panes}
        available = iter(key for key in preferred if key not in retained_keys)
        selectable = len(package.themes) > count
        window = self.mounted_window
        with state_transaction():
            if self._variant_dialog is not None:
                self._variant_dialog.dismiss()
            focused = window.focused_component if window else None
            restore = None
            for pane in self.panes:
                if pane not in panes:
                    if focused in (pane.field, pane.apply, pane.variant_button, pane.disable_form):
                        restore = panes[0]
                    self.remove(pane)
            for pane in panes:
                if focused is pane.variant_button and not selectable:
                    restore = pane
                mode = pane.mode if pane.mode in package.themes else next(available)
                pane.set_mode(mode, selectable=selectable)
            if len(panes) < count:
                pane = self._make_pane(next(available), selectable=selectable)
                pane.title.text = pane.field.value = panes[0].title.text
                panes.append(pane)
                self.add(pane)
            self.panes = tuple(panes)
            self.set_appearance(package.themes, panes[0].headline.text)
            if window and restore is not None:
                target = restore.field if restore.field.enabled else restore.disable_form
                window.focus_component(target)

    def set_design(self, package: ThemePackage, headline: str) -> None:
        with state_transaction():
            self.set_appearance(package.themes, headline)
            for pane in self.panes:
                pane.title.text = pane.field.value = package.name

    def set_appearance(self, themes: Mapping[str, Theme], headline: str) -> None:
        with state_transaction():
            self._themes = themes
            for pane in self.panes:
                pane.theme = themes[pane.mode]
                pane.headline.text = headline

    def _choose_variant(self, event: Event) -> None:
        if self._variant_dialog is not None:
            return
        pane = next(p for p in self.panes if p.mode_label is event.source)
        other_modes = {p.mode for p in self.panes if p is not pane}
        items = [CommandItem(pane.mode, pane.mode, shortcut="Current")]
        items.extend(CommandItem(key, key) for key in self._themes
                     if key != pane.mode and key not in other_modes)
        dialog = _VariantDialog(pane, items)

        def select(event: Event) -> None:
            key = str(event.data["key"])
            with state_transaction():
                pane.set_mode(key, selectable=True)
                pane.theme = self._themes[key]

        def closed(event: Event) -> None:
            if event.source is dialog:
                self._variant_dialog = None
                self.remove(dialog)
                if self.mounted_window:
                    self.mounted_window.focus_component(pane.mode_label)

        dialog.search.on("command_invoked", select)
        dialog.on("dismissed", closed)
        self._variant_dialog = dialog
        self.add(dialog)
        if self.mounted_window:
            self.mounted_window.focus_component(dialog.search)

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
        if self._variant_dialog is not None:
            self._variant_dialog._set_layout_bounds(viewport)
        count = len(self.panes)
        if count == 2 and viewport.width < 2 * _MIN_PANE_WIDTH:
            height = viewport.height / count
            for index, pane in enumerate(self.panes):
                pane._set_layout_bounds(Rect(viewport.x, viewport.y + index * height,
                                             viewport.width, height))
            return
        width = viewport.width / count
        for index, pane in enumerate(self.panes):
            pane._set_layout_bounds(Rect(viewport.x + index * width, viewport.y, width,
                                         viewport.height))


def bind_package_reload(window: Window, root: AppearanceComparison, source: Path,
                        *, pane_limit: int, backend_name: str = "win32") -> None:
    """Reload a file-backed preview on F5, including when no control has focus."""
    if pane_limit not in (1, 2):
        raise ValueError("Choose one or two preview panes.")
    window.set_title(f"{root.panes[0].title.text} · Theme preview · F5 to reload")
    f5 = _F5.get(backend_name, 0x74)

    def reload(event: Event) -> None:
        key = event.data.get("event")
        if (not isinstance(key, PlatformEvent) or key.key_code != f5 or key.ctrl
                or key.alt or key.shift or key.meta):
            return
        try:
            package = ThemePackage.load(source)
        except (OSError, ValueError) as error:
            window.set_title(f"Could not reload {source.name} · F5 to retry")
            print(f"Could not reload {source}: {error}", file=sys.stderr)
            return
        root._reload_package(package, pane_limit=pane_limit)
        window.set_title(f"{package.name} · Theme reloaded · F5 to reload")

    window.on("key_down", reload)


def run_package_preview(root: AppearanceComparison, *, smoke_test: bool = False,
                        source: Path | None = None, pane_limit: int = 2) -> int:
    """Display an interactive sample without modifying the source package."""
    count = len(root.panes)
    renderer = WgpuRenderer()
    app = App("SwirUI theme preview", renderer=renderer)
    window = app.add_window(Window(title=f"{root.panes[0].title.text} · Theme preview",
                                   width=480 * count, height=460,
                                   min_width=_MIN_PANE_WIDTH, min_height=390))
    mount(window, root)
    if source is not None:
        bind_package_reload(window, root, source, pane_limit=pane_limit,
                            backend_name=app.platform_backend.name)
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
        window = Window(title=title, width=960, height=460, min_width=_MIN_PANE_WIDTH,
                        min_height=390)
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
