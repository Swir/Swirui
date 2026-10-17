"""Complete integrated SwirUI Studio shell."""

from __future__ import annotations

import json
from dataclasses import replace

from . import (
    App,
    Button,
    ButtonVariant,
    CommandItem,
    CommandPalette,
    DockPane,
    DockWorkspace,
    Modal,
    Toast,
    TreeNode,
    TreeView,
    Window,
    mount,
)
from .core import Event
from .platforms import PlatformEvent, PlatformEventKind
from .rendering import Rect, WgpuRenderer
from .studio import Studio
from .studio_operations import StudioDashboard, StudioSettings


class StudioSuite(Studio):
    """The complete Studio shell with dashboard, settings and notifications."""

    def __init__(self) -> None:
        super().__init__()
        empty = Rect(0, 0, 0, 0)
        self.dashboard = StudioDashboard()
        self.settings = StudioSettings()
        self.dashboard_button = Button("Dashboard", bounds=empty)
        self.settings_button = Button(
            "Settings",
            bounds=empty,
            variant=ButtonVariant.SECONDARY,
        )
        self.dashboard_button.on("click", lambda _: self.activate("dashboard"))
        self.settings_button.on("click", lambda _: self.activate("settings"))
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
                                        TreeNode("dashboard", "Operations dashboard"),
                                        TreeNode("preview", "Preview canvas"),
                                        TreeNode("code", "Code editor"),
                                        TreeNode("assets", "Asset library"),
                                        TreeNode("settings", "Settings"),
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
        self.workspace = DockWorkspace(
            [
                DockPane("hierarchy", "Hierarchy", self.hierarchy, dock="left", extent=250),
                DockPane("inspector", "Inspector", self.inspector, dock="right", extent=330),
                DockPane("console", "Console", self.terminal, dock="bottom", extent=190),
                DockPane("dashboard", "Dashboard", self.dashboard),
                DockPane("preview", "Preview canvas", self.preview),
                DockPane("code", "Code", self.editor),
                DockPane("assets", "Assets", self.assets),
                DockPane("settings", "Settings", self.settings),
            ],
            bounds=empty,
            active_key="dashboard",
            header_height=34,
            min_center_extent=260,
            accessible_name="SwirUI Studio workspace",
        )
        self.palette = CommandPalette(
            [
                CommandItem("dashboard", "Open operations dashboard"),
                CommandItem("preview", "Show preview canvas"),
                CommandItem("code", "Open code editor"),
                CommandItem("assets", "Open asset library"),
                CommandItem("settings", "Open Studio settings"),
                CommandItem("pulse", "Record a performance sample"),
                CommandItem("notify", "Show a Studio notification"),
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
        self.toast = Toast(
            "Studio is ready.",
            title="SwirUI Studio",
            bounds=empty,
            kind="success",
            duration_seconds=4,
        )
        self.toast.visible = False
        self.palette.on("command_invoked", self._command_invoked)
        self.palette.on("dismissed", self._palette_dismissed)
        self.command_dialog.on("dismissed", self._commands_dismissed)
        self.settings.on("settings_changed", self._settings_changed)
        self.dashboard.on("sampled", self._sampled)
        self.clear()
        self.add(
            self.brand,
            self.tagline,
            self.active,
            self.dashboard_button,
            self.preview_button,
            self.code_button,
            self.assets_button,
            self.settings_button,
            self.theme_button,
            self.command_button,
            self.workspace,
            self.toast,
            self.command_dialog,
        )
        self.resize_to(1440, 900)
        self._sync_navigation()

    def prepare_layout(self, viewport: Rect) -> None:
        if not hasattr(self, "dashboard_button"):
            super().prepare_layout(viewport)
            return
        super().prepare_layout(viewport)
        width = viewport.width
        button_width = 74.0 if width < 1200 else 86.0
        gap = 6.0
        start = 306.0
        buttons = (
            self.dashboard_button,
            self.preview_button,
            self.code_button,
            self.assets_button,
            self.settings_button,
        )
        for index, button in enumerate(buttons):
            button._set_layout_bounds(
                Rect(start + index * (button_width + gap), 22, button_width, 40)
            )
        self.theme_button._set_layout_bounds(Rect(width - 314, 22, 118, 40))
        self.command_button._set_layout_bounds(Rect(width - 186, 22, 162, 40))
        self.toast._set_layout_bounds(Rect(max(18.0, width - 390), 92, 360, 94))

    def activate(self, key: str) -> None:
        if not hasattr(self, "dashboard_button"):
            super().activate(key)
            return
        if key not in {"dashboard", "preview", "code", "assets", "settings"}:
            raise ValueError(f"Unknown center pane: {key}")
        self.workspace.activate_pane(key)
        self._sync_navigation()
        self.terminal.writeln(f"\x1b[36mActive pane:\x1b[0m {key}")

    def toggle_theme(self) -> None:
        super().toggle_theme()
        if hasattr(self, "settings"):
            reduced = self.settings.reduced_motion.checked
            assert self.theme is not None and self.preview.theme is not None
            self.theme = replace(self.theme, reduced_motion=reduced)
            self.preview.theme = replace(self.preview.theme, reduced_motion=reduced)

    def execute_command(self, key: str) -> None:
        if key in {"dashboard", "settings"}:
            self.activate(key)
        elif key == "pulse":
            if self.settings.live_metrics.checked:
                self.dashboard.pulse()
            else:
                self.terminal.writeln("\x1b[33mLive metrics are paused in Settings.\x1b[0m")
        elif key == "notify":
            self.show_notification(
                "The integrated workspace is ready for the next build.",
                kind="success",
            )
        else:
            super().execute_command(key)

    def show_notification(
        self,
        message: str,
        *,
        title: str = "SwirUI Studio",
        kind: str = "info",
    ) -> bool:
        if not self.settings.notifications.checked:
            self.terminal.writeln("Notification suppressed by Studio settings.")
            return False
        self.toast.title = title
        self.toast.message = message
        self.toast.kind = kind
        self.toast.show(reason="studio")
        return True

    def _sync_navigation(self) -> None:
        if not hasattr(self, "dashboard_button"):
            super()._sync_navigation()
            return
        key = str(self.workspace.active_center_key)
        self.active.text = key.upper()
        for pane, button in (
            ("dashboard", self.dashboard_button),
            ("preview", self.preview_button),
            ("code", self.code_button),
            ("assets", self.assets_button),
            ("settings", self.settings_button),
        ):
            button.variant = (
                ButtonVariant.PRIMARY if pane == key else ButtonVariant.SECONDARY
            )

    def _settings_changed(self, event: Event) -> None:
        key = str(event.data["key"])
        value = event.data["value"]
        if key == "reduced_motion":
            assert self.theme is not None and self.preview.theme is not None
            self.theme = replace(self.theme, reduced_motion=bool(value))
            self.preview.theme = replace(self.preview.theme, reduced_motion=bool(value))
        elif key == "density":
            self._apply_density(float(value))
        self.terminal.writeln(f"Setting changed: {key} = {value}")

    def _apply_density(self, value: float) -> None:
        scale = max(0.75, min(1.5, value / 100.0))
        extents = {
            "hierarchy": 250.0 * scale,
            "inspector": 330.0 * scale,
            "console": 190.0 * scale,
        }
        panes = tuple(
            replace(pane, extent=extents.get(str(pane.key), pane.extent))
            for pane in self.workspace.panes
        )
        self.workspace.set_panes(panes)
        self.workspace.prepare_layout(self.workspace.bounds)

    def _sampled(self, event: Event) -> None:
        cpu = float(event.data["cpu"])
        gpu = float(event.data["gpu"])
        if max(cpu, gpu) >= 85:
            self.show_notification(
                f"High load detected · CPU {cpu:.0f}% / GPU {gpu:.0f}%",
                title="Performance monitor",
                kind="warning",
            )

    def _shortcut(self, event: Event) -> None:
        routed = event.data.get("routed_event")
        if event.default_prevented or isinstance(routed, Event) and routed.default_prevented:
            return
        native = event.data.get("event")
        if not isinstance(native, PlatformEvent) or native.kind is not PlatformEventKind.KEY_DOWN:
            return
        if native.key_code is None or not native.ctrl or native.alt or native.meta:
            return
        if native.key_code == 0x4B:
            if self.command_dialog.is_open:
                self.command_dialog.dismiss()
            else:
                self.open_commands()
            event.prevent_default()
            return
        pane = {
            0x31: "dashboard",
            0x32: "preview",
            0x33: "code",
            0x34: "assets",
            0x35: "settings",
        }.get(native.key_code)
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
    root = StudioSuite()
    window.on("resized", lambda _: root.resize_to(window.width, window.height))
    mount(window, root)
    app.add_window(window)
    try:
        if not smoke_test:
            return app.run()
        app.start()
        app.process_events()
        root.dashboard.pulse()
        app.render_pending(app._frame_schedulers[window].stats.last_frame_time + 1)
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
                    "metrics_samples": root.dashboard.sample_index,
                }
            )
        )
        return 0
    finally:
        app.stop()
