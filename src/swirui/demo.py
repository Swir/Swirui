"""A self-contained, installed-package showcase for the Windows desktop beta."""

from __future__ import annotations

import json
from dataclasses import replace
from functools import partial
from typing import Literal, cast

from . import (
    FUTURE_LIGHT,
    NEON_BLUE,
    App,
    Button,
    ButtonVariant,
    Input,
    Label,
    Panel,
    Slider,
    SurfaceStyle,
    Switch,
    ThemeSurface,
    Window,
    mount,
)
from .core import Event
from .rendering import Color, Rect, WgpuRenderer


class Demo(Panel):
    """Resize and change appearance without replacing editable controls."""

    def __init__(self) -> None:
        super().__init__(bounds=Rect(0, 0, 920, 680), theme=NEON_BLUE)
        self.material: Literal["solid", "glass", "acrylic"] = "glass"
        self.light = False
        empty = Rect(0, 0, 0, 0)
        self.blob = Panel(bounds=empty, background=Color(.015, .23, .4), corner_radius=140)
        self.title = Label("Make it yours.", bounds=empty, font_size=38)
        self.subtitle = Label("Your palette. Your materials. Your Python.",
                              bounds=empty, font_size=16)
        self.heading = Label("A little depth. A lot of you.", bounds=empty, font_size=23)
        self.field = Input("My next great app", bounds=empty, font_size=18)
        self.keep_ideas = Switch("Keep my ideas flowing", bounds=empty, checked=True)
        self.create = Button("Create something great", bounds=empty)
        self.result = Label("Change the style. Your work stays here.", bounds=empty, font_size=14)
        self.surface = ThemeSurface(bounds=empty)
        self.surface.add(self.heading, self.field, self.keep_ideas, self.create, self.result)
        self.mode = Button("Light theme", bounds=empty, variant=ButtonVariant.SECONDARY)
        self.mode.on("click", lambda _: self.toggle_mode())
        self.depth = Slider(bounds=empty, value=3, minimum=0, maximum=6, step=1)
        self.depth.on("changed", lambda _: self.apply_theme())
        self.depth_label = Label("Perspective layers", bounds=empty, font_size=15)
        self.hint = Label("Live controls.\nEditable themes.\nNative rendering.",
                          bounds=empty, font_size=17)
        self.footer = Label("SwirUI desktop beta / made with Python + Rust + wgpu",
                            bounds=empty, font_size=13)
        self.buttons: dict[str, Button] = {}
        for kind in ("glass", "acrylic", "solid"):
            button = Button(kind.title(), bounds=empty, variant=ButtonVariant.SECONDARY)
            button.on("click", partial(self.choose_material, kind))
            self.buttons[kind] = button
        self.create.on("click", lambda _: self.create_message())
        self.add(self.blob, self.title, self.subtitle, self.mode, *self.buttons.values(),
                 self.depth_label, self.depth, self.hint, self.surface, self.footer)
        self.resize_to(920, 680)
        self.apply_theme()

    def resize_to(self, width: float, height: float) -> None:
        self.bounds = Rect(0, 0, width, height)
        self.title.bounds = Rect(32, 32, width - 230, 58)
        self.subtitle.bounds = Rect(34, 100, width - 68, 30)
        self.mode.bounds = Rect(width - 184, 38, 152, 42)
        for index, button in enumerate(self.buttons.values()):
            button.bounds = Rect(32, 174 + index * 58, 180, 44)
        self.depth_label.bounds = Rect(32, 374, 188, 28)
        self.depth.bounds = Rect(32, 414, 180, 32)
        self.hint.bounds = Rect(32, 474, 200, 90)
        card_width = width - 292
        self.blob.bounds = Rect(width - 360, 200, 290, 290)
        self.surface.bounds = Rect(252, 178, card_width, height - 250)
        self.heading.bounds = Rect(280, 212, card_width - 56, 48)
        self.field.bounds = Rect(280, 286, card_width - 56, 48)
        self.keep_ideas.bounds = Rect(280, 358, card_width - 56, 40)
        self.create.bounds = Rect(280, 426, card_width - 56, 46)
        self.result.bounds = Rect(280, 488, card_width - 56, 28)
        self.footer.bounds = Rect(32, height - 42, width - 64, 26)

    def choose_material(self, kind: str, _event: Event | None = None) -> None:
        if kind not in self.buttons:
            raise ValueError("Unknown demo material")
        self.material = cast(Literal["solid", "glass", "acrylic"], kind)
        self.apply_theme()

    def toggle_mode(self) -> None:
        self.light = not self.light
        self.mode.text = "Dark theme" if self.light else "Light theme"
        self.apply_theme()

    def apply_theme(self) -> None:
        self.theme = replace(FUTURE_LIGHT if self.light else NEON_BLUE, surface_style=SurfaceStyle(
            kind=self.material, tint_opacity=.72, elevation=12, glow_radius=16,
            depth_layers=int(self.depth.value), depth_spacing=7,
        ))
        for kind, button in self.buttons.items():
            button.variant = (ButtonVariant.PRIMARY if kind == self.material
                              else ButtonVariant.SECONDARY)

    def create_message(self) -> None:
        self.result.text = (
            "Ready to build!" if self.field.value.strip() else "Give your idea a name."
        )


def run(*, smoke_test: bool = False) -> int:
    renderer = WgpuRenderer()
    app = App("SwirUI desktop beta", renderer=renderer)
    window = Window(title="SwirUI / Make it yours", width=920, height=680,
                    min_width=800, min_height=600)
    root = Demo()
    window.on("resized", lambda _: root.resize_to(window.width, window.height))
    mount(window, root)
    app.add_window(window)
    try:
        if not smoke_test:
            return app.run()
        app.start()
        app.process_events()
        if renderer.frames_rendered < 1 or not renderer.adapter_name:
            raise RuntimeError("No native frame was rendered")
        print(json.dumps({"rendered": True, "frames": renderer.frames_rendered,
                          "adapter": renderer.adapter_name, "backend": renderer.graphics_backend}))
        return 0
    finally:
        app.stop()
