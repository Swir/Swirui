"""Integrated native SwirUI showcase editor for the installed desktop beta."""

from __future__ import annotations

import json
from dataclasses import replace
from typing import Literal

from . import (
    FUTURE_LIGHT,
    NEON_BLUE,
    App,
    Badge,
    Button,
    ButtonVariant,
    CodeEditor,
    CommandItem,
    CommandPalette,
    DataGrid,
    DataGridColumn,
    DockPane,
    DockWorkspace,
    Inspector,
    Label,
    ListItem,
    ListView,
    Modal,
    Panel,
    PropertyItem,
    SurfaceStyle,
    TabItem,
    Tabs,
    Terminal,
    ThemeSurface,
    TreeNode,
    TreeView,
    Window,
    mount,
    state_transaction,
)
from .core import Event
from .platforms import PlatformEvent, PlatformEventKind
from .rendering import Color, Rect, WgpuRenderer


class PreviewPane(Panel):
    """Retained application preview shared with hierarchy and inspector state."""

    def __init__(self) -> None:
        super().__init__(bounds=Rect(0, 0, 1, 1), background=Color.from_hex("#050D19"))
        empty = Rect(0, 0, 0, 0)
        self.selected_key = "hero"
        self.running = False
        self.grid_visible = True
        self.selection = Badge("SELECTED / HERO", bounds=empty)
        self.grid_hint = Label("GRID / 32 DIP / SNAP", bounds=empty, font_size=10)
        self.brand = Label("SWIR", bounds=empty, font_size=24)
        self.nav = Label("Overview\nProjects\nAssets\nSettings", bounds=empty, font_size=14)
        self.eyebrow = Label("NATIVE / REACTIVE / GPU-FIRST", bounds=empty, font_size=11)
        self.headline = Label(
            "Build something unmistakably yours.", bounds=empty, font_size=28
        )
        self.subtitle = Label(
            "One retained workspace for design, code and live application state.",
            bounds=empty,
            font_size=14,
        )
        self.metrics = Label(
            "144 Hz\nframe-aware     1 ctx\npersistent GPU     68%\nroadmap",
            bounds=empty,
            font_size=14,
        )
        self.action = Button("Run live preview", bounds=empty)
        self.card = ThemeSurface(bounds=empty, accessible_name="Showcase hero card")
        self.card.add(self.eyebrow, self.headline, self.subtitle, self.metrics, self.action)
        self.add(self.selection, self.grid_hint, self.brand, self.nav, self.card)

    def prepare_layout(self, viewport: Rect) -> None:
        self._set_layout_bounds(viewport)
        inset = 28.0
        origin_x, origin_y = viewport.x, viewport.y
        sidebar = min(170.0, max(130.0, viewport.width * 0.22))
        self.selection._set_layout_bounds(
            Rect(origin_x + inset, origin_y + inset, min(170, sidebar), 28)
        )
        self.grid_hint._set_layout_bounds(
            Rect(
                origin_x + inset,
                max(origin_y + inset, viewport.bottom - 54),
                sidebar - 18,
                22,
            )
        )
        self.brand._set_layout_bounds(
            Rect(origin_x + inset, origin_y + 76, sidebar - 20, 38)
        )
        self.nav._set_layout_bounds(
            Rect(origin_x + inset, origin_y + 144, sidebar - 26, 180)
        )
        card_x = origin_x + inset + sidebar
        card_y = origin_y + inset
        card_width = max(0.0, viewport.right - card_x - inset)
        card_height = max(0.0, viewport.height - inset * 2)
        self.card._set_layout_bounds(Rect(card_x, card_y, card_width, card_height))
        self.eyebrow._set_layout_bounds(
            Rect(card_x + 28, card_y + 34, card_width - 56, 24)
        )
        self.headline._set_layout_bounds(
            Rect(card_x + 28, card_y + 74, card_width - 56, 74)
        )
        self.subtitle._set_layout_bounds(
            Rect(card_x + 28, card_y + 158, card_width - 56, 50)
        )
        self.metrics._set_layout_bounds(
            Rect(card_x + 28, card_y + 236, card_width - 56, 104)
        )
        self.action._set_layout_bounds(
            Rect(card_x + 28, card_y + 362, min(220, card_width - 56), 46)
        )

    def select(self, key: str) -> None:
        normalized = key if key in {"page", "sidebar", "hero", "metric", "action"} else "hero"
        self.selected_key = normalized
        self.selection.text = f"SELECTED / {normalized.upper()}"

    def set_running(self, running: bool) -> None:
        self.running = bool(running)
        self.action.text = "Preview running" if self.running else "Run live preview"


class ShowcaseEditor(Panel):
    """Hierarchy, assets, design, code, inspector and console in one shell."""

    def __init__(self) -> None:
        theme = replace(
            NEON_BLUE,
            surface_style=SurfaceStyle(
                kind="glass",
                tint_opacity=0.72,
                elevation=12,
                glow_radius=18,
                depth_layers=2,
            ),
        )
        super().__init__(bounds=Rect(0, 0, 1440, 900), theme=theme)
        self.light = False
        self.preview_running = False
        self.compact = False
        empty = Rect(0, 0, 1, 1)
        self.preview = PreviewPane()
        self.editor = CodeEditor(
            "from swirui import App, Button, Label, Window\n\n"
            "def build_dashboard():\n"
            "    title = Label('Build something unmistakably yours.')\n"
            "    launch = Button('Run live preview')\n"
            "    return title, launch\n",
            bounds=empty,
            language="python",
            font_size=16,
            padding=14,
            show_minimap=True,
        )
        self.center_tabs = Tabs(
            [TabItem("design", "Design", self.preview), TabItem("code", "Code", self.editor)],
            bounds=empty,
            header_height=38,
        )
        self.hierarchy = TreeView(
            [
                TreeNode(
                    "page",
                    "DashboardPage",
                    (
                        TreeNode("sidebar", "NavigationRail"),
                        TreeNode(
                            "hero",
                            "HeroCard",
                            (
                                TreeNode("headline", "Headline"),
                                TreeNode("subhead", "Subtitle"),
                            ),
                        ),
                        TreeNode("metric", "MetricCards"),
                        TreeNode("action", "PrimaryAction"),
                    ),
                )
            ],
            bounds=empty,
            expanded_keys=("page", "hero"),
            item_height=38,
            accessible_name="Scene hierarchy",
        )
        self.hierarchy.select_index(2)
        self.hierarchy.on("selection_changed", self._hierarchy_changed)
        self.assets = ListView(
            [
                ListItem("theme", "Neon Blue", "Theme preset"),
                ListItem("glass", "Frosted glass card", "Material"),
                ListItem("chart", "Live performance chart", "Component"),
                ListItem("logo", "SWIR electric mark", "Vector asset"),
                ListItem("motion", "Shared-element motion", "Animation"),
            ],
            bounds=empty,
            item_height=42,
            accessible_name="Project assets",
        )
        self.assets.on("selection_changed", self._asset_changed)
        self.left_tabs = Tabs(
            [
                TabItem("hierarchy", "Hierarchy", self.hierarchy),
                TabItem("assets", "Assets", self.assets),
            ],
            bounds=empty,
            header_height=38,
        )
        self.inspector = Inspector(
            self._inspector_items("hero"), bounds=empty, label_fraction=0.48
        )
        self.inspector.on("property_changed", self._property_changed)
        self.terminal = Terminal(bounds=empty, prompt="swir > ", font_size=14, padding=12)
        self.terminal.writeln(
            "\x1b[36mShowcase ready.\x1b[0m Design and code share one state."
        )
        self.terminal.writeln("Try help, design, code, run, theme, reset or clear.")
        self.terminal.on("submitted", self._terminal_submitted)
        self.output = DataGrid(
            [
                DataGridColumn("source", "SOURCE", width=230),
                DataGridColumn("state", "STATE", width=150),
                DataGridColumn("detail", "DETAIL", width=420),
            ],
            [
                {
                    "id": 1,
                    "source": "Renderer",
                    "state": "Ready",
                    "detail": "wgpu context retained",
                },
                {
                    "id": 2,
                    "source": "Theme",
                    "state": "Live",
                    "detail": "Neon Blue / inherited",
                },
                {
                    "id": 3,
                    "source": "Layout",
                    "state": "Ready",
                    "detail": "responsive docking",
                },
            ],
            bounds=empty,
            row_key="id",
            row_height=38,
            header_height=38,
        )
        self.bottom_tabs = Tabs(
            [
                TabItem("console", "Console", self.terminal),
                TabItem("output", "Output", self.output),
            ],
            bounds=empty,
            header_height=36,
        )
        self.workspace = DockWorkspace(
            self._panes(False),
            bounds=Rect(20, 88, 1400, 754),
            active_key="center",
            header_height=34,
            min_center_extent=300,
            accessible_name="SwirUI showcase workspace",
        )
        self.title = Label("SwirUI / Showcase Editor", bounds=empty, font_size=23)
        self.project = Badge("Aurora dashboard", bounds=empty)
        self.commands = Button(
            "Commands · Ctrl+K", bounds=empty, variant=ButtonVariant.SECONDARY
        )
        self.mode = Button(
            "Light appearance", bounds=empty, variant=ButtonVariant.SECONDARY
        )
        self.run_button = Button("Run preview", bounds=empty)
        self.status = Label("Design active · HeroCard selected", bounds=empty, font_size=12)
        self.commands.on("click", lambda _: self.open_commands())
        self.mode.on("click", lambda _: self.toggle_theme())
        self.run_button.on("click", lambda _: self.toggle_preview())
        self.palette = CommandPalette(
            [
                CommandItem("design", "Show design canvas"),
                CommandItem("code", "Show code editor"),
                CommandItem("hierarchy", "Focus scene hierarchy"),
                CommandItem("assets", "Show project assets"),
                CommandItem("inspector", "Show inspector"),
                CommandItem("console", "Show console"),
                CommandItem("theme", "Switch light / dark appearance"),
                CommandItem("run", "Run or pause live preview"),
                CommandItem("reset", "Reset workspace layout"),
            ],
            bounds=Rect(0, 0, 620, 410),
            max_visible_rows=9,
        )
        self.palette.on("command_invoked", self._command_invoked)
        self.dialog = Modal(
            bounds=self.bounds,
            dialog_bounds=Rect(410, 190, 620, 410),
            content=self.palette,
            open=False,
            accessible_name="Showcase commands",
        )
        self.palette.on("dismissed", self._dismiss_palette)
        self.dialog.on("dismissed", self._command_dismissed)
        self.add(
            self.title,
            self.project,
            self.commands,
            self.mode,
            self.run_button,
            self.workspace,
            self.status,
            self.dialog,
        )

    def on_mount(self, window: Window) -> None:
        window.on("key_down", self._window_key_down)

    def on_unmount(self, window: Window) -> None:
        window.off("key_down", self._window_key_down)

    def _panes(self, compact: bool) -> tuple[DockPane, ...]:
        inspector_dock: Literal["center", "right"] = "center" if compact else "right"
        return (
            DockPane("explorer", "Project", self.left_tabs, dock="left", extent=246),
            DockPane(
                "inspector",
                "Inspector",
                self.inspector,
                dock=inspector_dock,
                extent=304,
            ),
            DockPane(
                "console", "Console / Output", self.bottom_tabs, dock="bottom", extent=210
            ),
            DockPane("center", "Design / Code", self.center_tabs),
        )

    def prepare_layout(self, viewport: Rect) -> None:
        self._set_layout_bounds(viewport)
        width, height = viewport.width, viewport.height
        self.title._set_layout_bounds(Rect(24, 20, max(260, width - 740), 38))
        self.project._set_layout_bounds(Rect(24, 58, 176, 26))
        self.commands._set_layout_bounds(Rect(max(24, width - 556), 24, 194, 40))
        self.mode._set_layout_bounds(Rect(max(24, width - 348), 24, 156, 40))
        self.run_button._set_layout_bounds(Rect(max(24, width - 178), 24, 154, 40))
        self.workspace._set_layout_bounds(
            Rect(20, 88, max(0, width - 40), max(0, height - 146))
        )
        self.status._set_layout_bounds(
            Rect(24, max(88, height - 42), max(0, width - 48), 24)
        )
        self.dialog._set_layout_bounds(viewport)
        dialog_width = min(620, max(420, width - 80))
        dialog_height = min(410, max(300, height - 120))
        self.dialog.dialog_bounds = Rect(
            max(20, (width - dialog_width) * 0.5),
            max(70, (height - dialog_height) * 0.5),
            dialog_width,
            dialog_height,
        )
        self.palette._set_layout_bounds(Rect(0, 0, dialog_width, dialog_height))
        compact = width < 1120
        if compact != self.compact:
            self.compact = compact
            self.workspace.set_panes(self._panes(compact))
        self.workspace.prepare_layout(self.workspace.bounds)
        self.center_tabs.prepare_layout(self.center_tabs.bounds)
        self.preview.prepare_layout(self.preview.bounds)

    def toggle_theme(self) -> None:
        with state_transaction():
            self.light = not self.light
            base = FUTURE_LIGHT if self.light else NEON_BLUE
            self.theme = replace(
                base,
                surface_style=SurfaceStyle(
                    kind="glass",
                    tint_opacity=0.82 if self.light else 0.72,
                    elevation=10 if self.light else 12,
                    glow_radius=8 if self.light else 18,
                    depth_layers=1 if self.light else 2,
                ),
            )
            self.mode.text = "Dark appearance" if self.light else "Light appearance"
            self.status.text = "Appearance updated without replacing retained state"

    def toggle_preview(self) -> None:
        self.preview_running = not self.preview_running
        self.preview.set_running(self.preview_running)
        self.run_button.text = "Pause preview" if self.preview_running else "Run preview"
        state = "running" if self.preview_running else "paused"
        self.status.text = f"Live preview {state} · retained GPU scene"
        self.terminal.writeln(f"\x1b[32mPreview {state}.\x1b[0m")

    def reset_layout(self) -> None:
        self.workspace.set_panes(self._panes(self.compact))
        self.workspace.activate_pane("center")
        self.center_tabs.select_key("design")
        self.left_tabs.select_key("hierarchy")
        self.bottom_tabs.select_key("console")
        self.status.text = "Workspace layout restored"

    def open_commands(self) -> None:
        self.palette.clear_query()
        self.palette.visible = True
        self.dialog.show()
        if self.mounted_window:
            self.mounted_window.focus_component(self.palette)

    def _dismiss_palette(self, _event: Event) -> None:
        self.dialog.dismiss()

    def _command_dismissed(self, event: Event) -> None:
        if event.source is self.dialog and self.mounted_window:
            self.mounted_window.focus_component(self.commands)

    def _window_key_down(self, event: Event) -> None:
        routed = event.data.get("routed_event")
        if event.default_prevented or isinstance(routed, Event) and routed.default_prevented:
            return
        native = event.data.get("event")
        if not isinstance(native, PlatformEvent) or native.kind is not PlatformEventKind.KEY_DOWN:
            return
        if native.ctrl and not native.alt and not native.meta and native.key_code == 0x4B:
            if self.dialog.is_open:
                self.dialog.dismiss()
            else:
                self.open_commands()
            event.prevent_default()

    def _command_invoked(self, event: Event) -> None:
        key = str(event.data["key"])
        if key in {"design", "code"}:
            self.workspace.activate_pane("center")
            self.center_tabs.select_key(key)
        elif key == "inspector":
            self.workspace.activate_pane("inspector")
        elif key in {"hierarchy", "assets"}:
            self.left_tabs.select_key(key)
        elif key == "console":
            self.bottom_tabs.select_key("console")
            self.workspace.activate_pane("console")
        elif key == "theme":
            self.toggle_theme()
        elif key == "run":
            self.toggle_preview()
        elif key == "reset":
            self.reset_layout()

    def _hierarchy_changed(self, event: Event) -> None:
        item = event.data.get("item")
        key = "page" if item is None else str(item.key)
        self.preview.select(key)
        self.inspector.set_items(self._inspector_items(self.preview.selected_key))
        self.status.text = f"Design active · {key} selected"

    def _asset_changed(self, event: Event) -> None:
        item = event.data.get("item")
        if item is not None:
            self.status.text = f"Asset selected · {item.label}"

    def _property_changed(self, event: Event) -> None:
        key, value = str(event.data["key"]), event.data["value"]
        if key == "title":
            self.preview.headline.text = str(value)
        elif key == "visible":
            self.preview.card.visible = bool(value)
        elif key == "grid":
            self.preview.grid_visible = bool(value)
            self.preview.grid_hint.visible = bool(value)
        elif key == "running" and bool(value) != self.preview_running:
            self.toggle_preview()
        self.status.text = f"Inspector updated · {key} = {value}"

    def _terminal_submitted(self, event: Event) -> None:
        command = str(event.data["command"]).strip().lower()
        if command == "clear":
            self.terminal.clear_buffer()
        elif command == "help":
            self.terminal.writeln("design / code / run / theme / reset / clear")
        elif command in {"design", "code"}:
            self.workspace.activate_pane("center")
            self.center_tabs.select_key(command)
        elif command == "run":
            self.toggle_preview()
        elif command == "theme":
            self.toggle_theme()
        elif command == "reset":
            self.reset_layout()
        elif command:
            self.terminal.writeln("\x1b[33mUnknown command. Try help.\x1b[0m")

    def _inspector_items(self, key: str) -> tuple[PropertyItem, ...]:
        return (
            PropertyItem("name", "Name", key.title(), category="Identity", read_only=True),
            PropertyItem("visible", "Visible", True, category="Layout"),
            PropertyItem("grid", "Show grid", self.preview.grid_visible, category="Canvas"),
            PropertyItem("running", "Live preview", self.preview_running, category="Canvas"),
            PropertyItem("title", "Headline", self.preview.headline.text, category="Content"),
        )


def run(*, smoke_test: bool = False) -> int:
    renderer = WgpuRenderer()
    app = App("SwirUI showcase editor", renderer=renderer)
    window = Window(
        title="SwirUI / Showcase Editor",
        width=1440,
        height=900,
        min_width=960,
        min_height=680,
    )
    root = ShowcaseEditor()
    window.on(
        "resized", lambda _: root.prepare_layout(Rect(0, 0, window.width, window.height))
    )
    mount(window, root)
    app.add_window(window)
    try:
        if not smoke_test:
            return app.run()
        app.start()
        app.process_events()
        if renderer.frames_rendered < 1 or not renderer.adapter_name:
            raise RuntimeError("No native showcase frame was rendered")
        print(
            json.dumps(
                {
                    "rendered": True,
                    "frames": renderer.frames_rendered,
                    "adapter": renderer.adapter_name,
                    "backend": renderer.graphics_backend,
                    "workspace": root.workspace.accessible_value_text,
                }
            )
        )
        return 0
    finally:
        app.stop()
