"""Integrated native SwirUI studio combining preview, code, hierarchy and tooling."""

from __future__ import annotations

import json
from dataclasses import replace
from typing import Literal, cast

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
    Input,
    Inspector,
    Label,
    Modal,
    Panel,
    PropertyItem,
    SurfaceStyle,
    Switch,
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

MaterialKind = Literal["solid", "glass", "acrylic"]


class StudioPreview(Panel):
    """Interactive application canvas retained inside the integrated studio."""

    def __init__(self) -> None:
        super().__init__(bounds=Rect(0, 0, 760, 540), theme=NEON_BLUE)
        empty = Rect(0, 0, 0, 0)
        self.material: MaterialKind = "glass"
        self.depth = 3
        self.light = False
        self.status = Badge("LIVE PREVIEW", bounds=empty)
        self.blob = Panel(
            bounds=empty,
            background=Color(0.02, 0.22, 0.42, 0.9),
            corner_radius=120,
        )
        self.surface = ThemeSurface(bounds=empty)
        self.heading = Label("Build beyond ordinary.", bounds=empty, font_size=30)
        self.subtitle = Label(
            "Native Python UI with a retained Rust + wgpu core.",
            bounds=empty,
            font_size=15,
        )
        self.project = Input("Neon workspace", bounds=empty, font_size=16)
        self.motion = Switch("Enable motion", bounds=empty, checked=True)
        self.create = Button("Launch preview", bounds=empty)
        self.result = Label("Ready for your next idea.", bounds=empty, font_size=14)
        self.surface.add(
            self.heading,
            self.subtitle,
            self.project,
            self.motion,
            self.create,
            self.result,
        )
        self.footer = Label(
            "CANVAS / RETAINED SCENE / GPU",
            bounds=empty,
            font_size=11,
        )
        self.create.on("click", lambda _: self._launch())
        self.add(self.blob, self.status, self.surface, self.footer)
        self.apply_theme()

    def prepare_layout(self, viewport: Rect) -> None:
        self._set_layout_bounds(viewport)
        width, height = viewport.width, viewport.height
        pad = 24.0
        self.status._set_layout_bounds(Rect(viewport.x + pad, viewport.y + 16, 148, 30))
        self.blob._set_layout_bounds(
            Rect(viewport.right - 220, viewport.y + 52, 170, 170)
        )
        surface = Rect(
            viewport.x + pad,
            viewport.y + 54,
            max(0.0, width - 2 * pad),
            max(0.0, height - 90),
        )
        self.surface._set_layout_bounds(surface)
        inner_x = surface.x + 26
        inner_width = max(0.0, surface.width - 52)
        self.heading._set_layout_bounds(Rect(inner_x, surface.y + 22, inner_width, 38))
        self.subtitle._set_layout_bounds(Rect(inner_x, surface.y + 68, inner_width, 24))
        self.project._set_layout_bounds(Rect(inner_x, surface.y + 108, inner_width, 42))
        self.motion._set_layout_bounds(Rect(inner_x, surface.y + 164, inner_width, 36))
        self.create._set_layout_bounds(Rect(inner_x, surface.y + 218, 190, 40))
        self.result._set_layout_bounds(
            Rect(inner_x, surface.y + 270, inner_width, 24)
        )
        self.footer._set_layout_bounds(
            Rect(viewport.x + pad, viewport.bottom - 28, max(0.0, width - 2 * pad), 18)
        )

    def apply_theme(self) -> None:
        base = FUTURE_LIGHT if self.light else NEON_BLUE
        self.theme = replace(
            base,
            surface_style=SurfaceStyle(
                kind=self.material,
                tint_opacity=0.74,
                elevation=14,
                glow_radius=18,
                glow_opacity=0.26,
                depth_layers=self.depth,
                depth_spacing=7,
                tilt_x=8,
                tilt_y=-11,
            ),
        )

    def set_title(self, value: str) -> None:
        text = value.strip()
        self.heading.text = text or "Build beyond ordinary."

    def set_material(self, value: str) -> None:
        normalized = value.strip().lower()
        if normalized not in {"solid", "glass", "acrylic"}:
            raise ValueError("material must be solid, glass or acrylic")
        self.material = cast(MaterialKind, normalized)
        self.apply_theme()

    def set_depth(self, value: int) -> None:
        self.depth = max(0, min(8, int(value)))
        self.apply_theme()

    def set_light(self, value: bool) -> None:
        self.light = bool(value)
        self.apply_theme()

    def reset(self) -> None:
        with state_transaction():
            self.material = "glass"
            self.depth = 3
            self.light = False
            self.heading.text = "Build beyond ordinary."
            self.project.value = "Neon workspace"
            self.motion.checked = True
            self.result.text = "Ready for your next idea."
            self.apply_theme()

    def _launch(self) -> None:
        name = self.project.value.strip()
        self.result.text = (
            f"{name} is ready to render." if name else "Name the project before launch."
        )


class Studio(Panel):
    """One integrated IDE-style showcase built from production SwirUI widgets."""

    def __init__(self) -> None:
        super().__init__(bounds=Rect(0, 0, 1440, 900), theme=NEON_BLUE)
        empty = Rect(0, 0, 0, 0)
        self.light = False
        self.brand = Label("SWIR / STUDIO", bounds=empty, font_size=22)
        self.tagline = Label(
            "Design. Code. Inspect. Ship.",
            bounds=empty,
            font_size=13,
        )
        self.active = Badge("PREVIEW", bounds=empty)
        self.preview_button = Button("Preview", bounds=empty)
        self.code_button = Button(
            "Code",
            bounds=empty,
            variant=ButtonVariant.SECONDARY,
        )
        self.assets_button = Button(
            "Assets",
            bounds=empty,
            variant=ButtonVariant.SECONDARY,
        )
        self.theme_button = Button(
            "Light theme",
            bounds=empty,
            variant=ButtonVariant.SECONDARY,
        )
        self.command_button = Button(
            "Commands · Ctrl+K",
            bounds=empty,
            variant=ButtonVariant.SECONDARY,
        )

        self.preview = StudioPreview()
        self.editor = CodeEditor(
            "from swirui import App, Button, Panel, Window\n"
            "from swirui.rendering import Rect\n\n"
            "def build() -> Panel:\n"
            "    root = Panel(bounds=Rect(0, 0, 960, 640))\n"
            "    root.add(Button(\"Create\", bounds=Rect(32, 32, 180, 44)))\n"
            "    return root\n",
            bounds=empty,
            language="python",
            font_size=16,
            padding=14,
        )
        self.assets = DataGrid(
            [
                DataGridColumn("name", "ASSET", width=300),
                DataGridColumn("kind", "TYPE", width=160),
                DataGridColumn("state", "STATE", width=150),
                DataGridColumn("updated", "UPDATED", width=150),
            ],
            [
                {
                    "id": index,
                    "name": f"{name} / {index + 1:02}",
                    "kind": ("Theme", "Component", "Image", "Motion")[index % 4],
                    "state": ("Ready", "Draft", "Review")[index % 3],
                    "updated": "Today" if index < 8 else "Yesterday",
                }
                for index, name in enumerate(
                    (
                        "Aurora",
                        "Glass shell",
                        "Command deck",
                        "Neon icon",
                        "Dashboard",
                        "Inspector",
                        "Orbit motion",
                        "Ocean theme",
                        "Terminal",
                        "Data table",
                        "Media card",
                        "Settings",
                    )
                )
            ],
            bounds=empty,
            row_key="id",
            selection_mode="multiple",
            row_height=42,
            header_height=42,
        )
        self.assets.select_row(0)

        self.hierarchy = TreeView(
            [
                TreeNode(
                    "app",
                    "Studio application",
                    (
                        TreeNode(
                            "window",
                            "Main window",
                            (
                                TreeNode(
                                    "root",
                                    "Neon workspace",
                                    (
                                        TreeNode("preview", "Preview canvas"),
                                        TreeNode("code", "Code editor"),
                                        TreeNode("assets", "Asset library"),
                                        TreeNode("inspector", "Inspector"),
                                        TreeNode("console", "Console"),
                                    ),
                                ),
                            ),
                        ),
                    ),
                )
            ],
            bounds=empty,
            expanded_keys=["app", "window", "root"],
            item_height=40,
        )

        self.inspector = Inspector(
            [
                PropertyItem("title", "Headline", "Build beyond ordinary.", category="Content"),
                PropertyItem("material", "Material", "glass", category="Appearance"),
                PropertyItem("depth", "Depth layers", 3, category="Appearance"),
                PropertyItem("light", "Light theme", False, category="Appearance"),
                PropertyItem(
                    "renderer",
                    "Renderer",
                    "Rust / wgpu",
                    category="Runtime",
                    read_only=True,
                ),
            ],
            bounds=empty,
            label_fraction=0.5,
        )
        self.terminal = Terminal(
            bounds=empty,
            prompt="studio > ",
            font_size=14,
            padding=12,
        )
        self.terminal.writeln("\x1b[32mIntegrated studio ready.\x1b[0m")
        self.terminal.writeln("Try preview, code, assets, theme, reset or clear.")

        self.workspace = DockWorkspace(
            [
                DockPane("hierarchy", "Hierarchy", self.hierarchy, dock="left", extent=250),
                DockPane("inspector", "Inspector", self.inspector, dock="right", extent=330),
                DockPane("console", "Console", self.terminal, dock="bottom", extent=190),
                DockPane("preview", "Preview canvas", self.preview),
                DockPane("code", "Code", self.editor),
                DockPane("assets", "Assets", self.assets),
            ],
            bounds=empty,
            active_key="preview",
            header_height=34,
            min_center_extent=260,
            accessible_name="SwirUI Studio workspace",
        )

        self.palette = CommandPalette(
            [
                CommandItem("preview", "Show preview canvas"),
                CommandItem("code", "Open code editor"),
                CommandItem("assets", "Open asset library"),
                CommandItem("theme", "Switch light / dark appearance"),
                CommandItem("reset", "Reset preview design"),
                CommandItem("clear", "Clear console"),
            ],
            bounds=Rect(0, 0, 620, 368),
            max_visible_rows=8,
        )
        self.command_dialog = Modal(
            bounds=self.bounds,
            dialog_bounds=Rect(410, 190, 620, 368),
            content=self.palette,
            open=False,
            accessible_name="Studio commands",
        )
        self.palette.on("command_invoked", self._command_invoked)
        self.palette.on("dismissed", self._palette_dismissed)
        self.command_dialog.on("dismissed", self._commands_dismissed)
        self.inspector.on("property_changed", self._property_changed)
        self.terminal.on("submitted", self._terminal_submitted)
        self.preview_button.on("click", lambda _: self.activate("preview"))
        self.code_button.on("click", lambda _: self.activate("code"))
        self.assets_button.on("click", lambda _: self.activate("assets"))
        self.theme_button.on("click", lambda _: self.toggle_theme())
        self.command_button.on("click", lambda _: self.open_commands())

        self.add(
            self.brand,
            self.tagline,
            self.active,
            self.preview_button,
            self.code_button,
            self.assets_button,
            self.theme_button,
            self.command_button,
            self.workspace,
            self.command_dialog,
        )
        self.resize_to(1440, 900)
        self._sync_navigation()

    def resize_to(self, width: float, height: float) -> None:
        self._set_layout_bounds(Rect(0, 0, width, height))
        self.prepare_layout(self.bounds)

    def prepare_layout(self, viewport: Rect) -> None:
        self._set_layout_bounds(viewport)
        width, height = viewport.width, viewport.height
        self.brand._set_layout_bounds(Rect(24, 18, 220, 34))
        self.tagline._set_layout_bounds(Rect(24, 54, 260, 24))
        self.active._set_layout_bounds(Rect(280, 28, 100, 30))
        self.preview_button._set_layout_bounds(Rect(392, 22, 96, 40))
        self.code_button._set_layout_bounds(Rect(498, 22, 86, 40))
        self.assets_button._set_layout_bounds(Rect(594, 22, 92, 40))
        self.theme_button._set_layout_bounds(Rect(width - 330, 22, 124, 40))
        self.command_button._set_layout_bounds(Rect(width - 196, 22, 172, 40))
        self.workspace._set_layout_bounds(
            Rect(18, 86, max(0.0, width - 36), max(0.0, height - 106))
        )
        dialog_width = min(620.0, max(0.0, width - 48))
        dialog_height = min(368.0, max(0.0, height - 96))
        self.command_dialog._set_layout_bounds(viewport)
        self.command_dialog.dialog_bounds = Rect(
            viewport.x + max(0.0, (width - dialog_width) * 0.5),
            viewport.y + max(0.0, (height - dialog_height) * 0.5),
            dialog_width,
            dialog_height,
        )

    def on_mount(self, window: Window) -> None:
        window.on("key_down", self._shortcut)

    def on_unmount(self, window: Window) -> None:
        window.off("key_down", self._shortcut)

    def activate(self, key: str) -> None:
        if key not in {"preview", "code", "assets"}:
            raise ValueError(f"Unknown center pane: {key}")
        self.workspace.activate_pane(key)
        self._sync_navigation()
        self.terminal.writeln(f"\x1b[36mActive pane:\x1b[0m {key}")

    def toggle_theme(self) -> None:
        with state_transaction():
            self.light = not self.light
            self.theme = FUTURE_LIGHT if self.light else NEON_BLUE
            self.preview.set_light(self.light)
            self.inspector.set_value("light", self.light)
            self.theme_button.text = "Dark theme" if self.light else "Light theme"
            self.terminal.writeln(
                f"Appearance: {'light' if self.light else 'neon blue'}"
            )

    def open_commands(self) -> None:
        self.palette.clear_query()
        self.palette.visible = True
        self.command_dialog.show()
        if self.mounted_window:
            self.mounted_window.focus_component(self.palette)

    def execute_command(self, key: str) -> None:
        if key in {"preview", "code", "assets"}:
            self.activate(key)
        elif key == "theme":
            self.toggle_theme()
        elif key == "reset":
            self.preview.reset()
            self._sync_inspector()
            self.terminal.writeln("Preview reset.")
        elif key == "clear":
            self.terminal.clear_buffer()
        else:
            self.terminal.writeln(
                "\x1b[33mTry preview, code, assets, theme, reset or clear.\x1b[0m"
            )

    def _sync_navigation(self) -> None:
        key = str(self.workspace.active_center_key)
        self.active.text = key.upper()
        for pane, button in (
            ("preview", self.preview_button),
            ("code", self.code_button),
            ("assets", self.assets_button),
        ):
            button.variant = (
                ButtonVariant.PRIMARY if pane == key else ButtonVariant.SECONDARY
            )

    def _sync_inspector(self) -> None:
        self.inspector.set_value("title", self.preview.heading.text)
        self.inspector.set_value("material", self.preview.material)
        self.inspector.set_value("depth", self.preview.depth)
        self.inspector.set_value("light", self.preview.light)

    def _property_changed(self, event: Event) -> None:
        key = str(event.data["key"])
        value = event.data["value"]
        if key == "title":
            self.preview.set_title(str(value))
        elif key == "material":
            try:
                self.preview.set_material(str(value))
            except ValueError:
                self.terminal.writeln(
                    "\x1b[31mMaterial must be solid, glass or acrylic.\x1b[0m"
                )
                self.inspector.set_value("material", self.preview.material)
                return
        elif key == "depth":
            depth = max(0, min(8, int(value)))
            self.preview.set_depth(depth)
            if depth != value:
                self.inspector.set_value("depth", depth)
                return
        elif key == "light":
            light = bool(value)
            if light != self.light:
                self.toggle_theme()
                return
        self.terminal.writeln(f"Property changed: {key} = {value}")

    def _terminal_submitted(self, event: Event) -> None:
        self.execute_command(str(event.data["command"]).strip().lower())

    def _command_invoked(self, event: Event) -> None:
        self.execute_command(str(event.data["key"]))
        self.command_dialog.dismiss()

    def _palette_dismissed(self, _event: Event) -> None:
        self.command_dialog.dismiss()

    def _commands_dismissed(self, event: Event) -> None:
        if event.source is self.command_dialog and self.mounted_window:
            self.mounted_window.focus_component(self.command_button)

    def _shortcut(self, event: Event) -> None:
        routed = event.data.get("routed_event")
        if event.default_prevented or isinstance(routed, Event) and routed.default_prevented:
            return
        native = event.data.get("event")
        if not isinstance(native, PlatformEvent) or native.kind is not PlatformEventKind.KEY_DOWN:
            return
        if native.key_code is None:
            return
        if native.ctrl and not native.alt and not native.meta:
            if native.key_code == 0x4B:
                if self.command_dialog.is_open:
                    self.command_dialog.dismiss()
                else:
                    self.open_commands()
                event.prevent_default()
                return
            pane = {0x31: "preview", 0x32: "code", 0x33: "assets"}.get(native.key_code)
            if pane is not None:
                self.activate(pane)
                event.prevent_default()


def run(*, smoke_test: bool = False) -> int:
    renderer = WgpuRenderer()
    app = App("SwirUI Studio", renderer=renderer)
    window = Window(
        title="SwirUI Studio",
        width=1440,
        height=900,
        min_width=1024,
        min_height=720,
    )
    root = Studio()
    window.on("resized", lambda _: root.resize_to(window.width, window.height))
    mount(window, root)
    app.add_window(window)
    try:
        if not smoke_test:
            return app.run()
        app.start()
        app.process_events()
        if renderer.frames_rendered < 1 or not renderer.adapter_name:
            raise RuntimeError("No native Studio frame was rendered")
        print(
            json.dumps(
                {
                    "rendered": True,
                    "frames": renderer.frames_rendered,
                    "adapter": renderer.adapter_name,
                    "backend": renderer.graphics_backend,
                    "active_pane": root.workspace.active_center_key,
                }
            )
        )
        return 0
    finally:
        app.stop()
