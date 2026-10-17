"""An interactive native design playground for SwirUI's shared visual system.

Run with the checkout and native module installed: python examples/swirui_studio.py
This is a showcase, not the roadmap's future visual application editor.
"""

from __future__ import annotations

import math
from dataclasses import replace

from swirui import (
    FUTURE_LIGHT,
    AnimationController,
    App,
    AppConfig,
    Button,
    ButtonVariant,
    Checkbox,
    Input,
    Palette,
    Slider,
    Switch,
    Theme,
    Tween,
    Window,
    ease_out_cubic,
    state_transaction,
)
from swirui.core import Event
from swirui.rendering import (
    Color,
    CornerRadius,
    FrostedGlass,
    Point,
    RadialGradient,
    Rect,
    SceneNode,
    SceneNodeKind,
    WgpuRenderer,
)
from swirui.widgets import Widget, mount

PALETTES = {
    "Violet": Palette(),
    "Ocean": replace(
        Palette(),
        accent="#82DEED",
        accent_hover="#B0EDF5",
        accent_pressed="#53B8CC",
        focus="#B0EDF5",
        on_accent="#092B34",
    ),
    "Rose": replace(
        Palette(),
        accent="#F0A8C5",
        accent_hover="#F6C5D9",
        accent_pressed="#D98AAE",
        focus="#F6C5D9",
        on_accent="#351323",
    ),
}

LIGHT_PALETTES = {
    "Violet": FUTURE_LIGHT.palette,
    "Ocean": replace(
        FUTURE_LIGHT.palette,
        accent="#087A8C",
        accent_hover="#096B7B",
        accent_pressed="#075563",
        focus="#087A8C",
    ),
    "Rose": replace(
        FUTURE_LIGHT.palette,
        accent="#B33570",
        accent_hover="#A02C61",
        accent_pressed="#862250",
        focus="#B33570",
    ),
}


def rectangle(key: str, bounds: Rect, color: Color, radius: float = 0) -> SceneNode:
    return SceneNode(
        key,
        SceneNodeKind.RECTANGLE,
        bounds,
        fill=color,
        corner_radius=CornerRadius.uniform(radius),
        hit_testable=False,
    )


class Studio(Widget):
    def __init__(self) -> None:
        super().__init__(bounds=Rect(0, 0, 1440, 900), key="studio")
        self.theme = Theme()
        self.palette_name = "Violet"
        self.light_mode = False
        self.title = "Make space for possibility."
        self.radius = 24.0
        self.depth = 24.0
        self.motion = True
        self.glass = True
        self.phase = 0.0
        self.preview_count = 0
        self.controller: AnimationController | None = None
        self.controls: dict[str, Widget] = {}
        self._gradient_key: tuple[Rect, Palette] | None = None
        self._gradient: SceneNode | None = None
        self._make_controls()

    def _make_controls(self) -> None:
        """Create controls once; their styles inherit from this root at runtime."""
        with state_transaction():
            self.clear()
            self.controls = {}
            title = Input(
                self.title,
                bounds=Rect(0, 0, 240, 44),
                font_size=14,
                accessible_name="Preview title",
                max_length=32,
            )
            title.on("changed", self._title_changed)
            self.controls["title"] = title
            for name, value, maximum in (("radius", self.radius, 48), ("depth", self.depth, 48)):
                slider = Slider(
                    bounds=Rect(0, 0, 240, 36),
                    value=value,
                    maximum=maximum,
                    accessible_name=name,
                )
                slider.on(
                    "changed", lambda event, setting=name: self._number_changed(setting, event)
                )
                self.controls[name] = slider
            motion = Switch("Motion", bounds=Rect(0, 0, 240, 40), checked=self.motion, font_size=14)
            motion.on("changed", self._motion_changed)
            self.controls["motion"] = motion
            glass = Checkbox(
                "Frosted glass",
                bounds=Rect(0, 0, 240, 40),
                checked=self.glass,
                font_size=14,
            )
            glass.on("changed", self._glass_changed)
            self.controls["glass"] = glass
            for name in PALETTES:
                button = Button(
                    name,
                    bounds=Rect(0, 0, 76, 36),
                    variant=(
                        ButtonVariant.PRIMARY
                        if name == self.palette_name
                        else ButtonVariant.SECONDARY
                    ),
                    font_size=12,
                    padding=10,
                )
                button.on("click", lambda _, selected=name: self.change_palette(selected))
                self.controls[name] = button
            for key, title_text, action, variant in (
                ("replay", "Replay motion", self.replay, ButtonVariant.PRIMARY),
                ("reset", "Reset style", self.reset, ButtonVariant.SECONDARY),
                ("mode", "Light theme", self.toggle_mode, ButtonVariant.SECONDARY),
                ("primary", "Try me", self.press_preview, ButtonVariant.PRIMARY),
                ("secondary", "Secondary", self.press_preview, ButtonVariant.SECONDARY),
                ("ghost", "Quiet action", self.press_preview, ButtonVariant.GHOST),
            ):
                button = Button(
                    title_text,
                    bounds=Rect(0, 0, 136, 40),
                    variant=variant,
                    font_size=14,
                )
                button.on("click", lambda _, callback=action: callback())
                self.controls[key] = button
            self.add(*self.controls.values())

    def _title_changed(self, event: Event) -> None:
        self.title = str(event.data["value"])
        self.invalidate(reason="preview")

    def _number_changed(self, name: str, event: Event) -> None:
        setattr(self, name, float(event.data["value"]))
        self.invalidate(reason="preview")

    def _motion_changed(self, _event: Event) -> None:
        control = self.controls["motion"]
        assert isinstance(control, Switch)
        self.motion = control.checked
        if not self.motion and self.controller:
            self.controller.cancel_all()
        self.invalidate(reason="preview")

    def _glass_changed(self, _event: Event) -> None:
        control = self.controls["glass"]
        assert isinstance(control, Checkbox)
        self.glass = control.checked
        self.invalidate(reason="preview")

    def change_palette(self, name: str) -> None:
        with state_transaction():
            self.palette_name = name
            assert self.theme is not None
            palettes = LIGHT_PALETTES if self.light_mode else PALETTES
            self.theme = replace(self.theme, palette=palettes[name])
            for option in PALETTES:
                button = self.controls[option]
                assert isinstance(button, Button)
                button.variant = (
                    ButtonVariant.PRIMARY if option == name else ButtonVariant.SECONDARY
                )
            self.invalidate(reason="palette")

    def toggle_mode(self) -> None:
        with state_transaction():
            self.light_mode = not self.light_mode
            button = self.controls["mode"]
            assert isinstance(button, Button)
            button.text = "Dark theme" if self.light_mode else "Light theme"
            self.change_palette(self.palette_name)

    def reset(self) -> None:
        with state_transaction():
            self.title, self.radius, self.depth = "Make space for possibility.", 24.0, 24.0
            self.motion, self.glass = True, True
            title, radius, depth = (
                self.controls["title"],
                self.controls["radius"],
                self.controls["depth"],
            )
            motion, glass = self.controls["motion"], self.controls["glass"]
            assert (
                isinstance(title, Input)
                and isinstance(radius, Slider)
                and isinstance(depth, Slider)
            )
            assert isinstance(motion, Switch) and isinstance(glass, Checkbox)
            title.value, radius.value, depth.value = self.title, self.radius, self.depth
            motion.checked, glass.checked = self.motion, self.glass
            if self.light_mode:
                self.toggle_mode()
            self.change_palette("Violet")

    def press_preview(self) -> None:
        self.preview_count += 1
        self.replay()
        self.invalidate(reason="preview")

    def replay(self) -> None:
        if self.controller is None or not self.motion or self.theme.reduced_motion:
            return
        self.controller.cancel_all()
        start = self.phase
        self.controller.play(
            Tween(start, start + math.tau, 1.2, self._set_phase, easing=ease_out_cubic)
        )

    def _set_phase(self, phase: float) -> None:
        self.phase = phase
        self.invalidate(reason="preview")

    def prepare_layout(self, viewport: Rect) -> None:
        self._set_layout_bounds(viewport)
        x = viewport.width - 280
        positions = {
            "title": Rect(x, 274, 240, 44),
            "radius": Rect(x, 426, 240, 36),
            "depth": Rect(x, 510, 240, 36),
            "motion": Rect(x, 568, 240, 40),
            "glass": Rect(x, 614, 240, 40),
            "replay": Rect(x, 680, 240, 44),
            "reset": Rect(viewport.width - 152, 24, 124, 38),
            "mode": Rect(viewport.width - 292, 24, 128, 38),
            "Violet": Rect(x, 358, 76, 36),
            "Ocean": Rect(x + 82, 358, 76, 36),
            "Rose": Rect(x + 164, 358, 76, 36),
            "primary": Rect(240, 682, 122, 42),
            "secondary": Rect(376, 682, 126, 42),
            "ghost": Rect(516, 682, 132, 42),
        }
        for name, bounds in positions.items():
            self.controls[name]._set_layout_bounds(bounds)

    def _text(
        self,
        key: str,
        text: str,
        x: float,
        y: float,
        width: float,
        size: float = 14,
        role: str = "text",
    ) -> SceneNode:
        color = self.theme.text_color(
            "muted" if role == "muted" else "accent" if role == "accent" else "text"
        )
        return SceneNode(
            key,
            SceneNodeKind.TEXT,
            Rect(x, y, width, size * 1.5),
            text=text,
            fill=color,
            font_size=size,
            font_family=self.theme.font_family,
            hit_testable=False,
            z_index=5,
        )

    def build_scene_node(self) -> SceneNode:
        width, height = self.bounds.width, self.bounds.height
        theme, text = self.theme, self._text
        assert theme is not None
        paint = theme.surface_color
        root = rectangle(self.key, self.bounds, paint("canvas"))
        root.add(
            rectangle("rail", Rect(0, 0, 184, height), paint("surface")),
            rectangle("rail-line", Rect(183, 0, 1, height), paint("border")),
            rectangle("logo", Rect(24, 27, 32, 32), paint("accent"), 10),
            text("logo-word", "swir", 70, 22, 110, 29),
            text("rail-subtitle", "DESIGN PLAYGROUND", 24, 100, 152, 10, "muted"),
            rectangle("nav-active", Rect(16, 137, 152, 44), paint("raised"), 12),
            text("nav-label", "Visual language", 30, 148, 130, 13, "accent"),
            text("rail-caption", "One system.", 24, 227, 146, 19),
            text("rail-caption-2", "Every detail.", 24, 257, 146, 19),
            text("rail-detail", "Color · Type · Motion", 24, 308, 150, 12, "muted"),
            text("rail-footer", "BUILT WITH PYTHON", 24, height - 77, 150, 10, "muted"),
            text("rail-footer-2", "SwirUI / Preview", 24, height - 50, 150, 13),
            text("breadcrumb", "Workspace  /  Visual system", 216, 33, 450, 14, "muted"),
            rectangle("header-line", Rect(208, 79, width - 232, 1), paint("border")),
            text("eyebrow", "CREATE SOMETHING EXTRAORDINARY", 216, 109, 620, 11, "accent"),
            text("heading", "Your ideas. Without limits.", 212, 139, width - 552, 35),
            text(
                "subheading",
                "A native canvas for thoughtful, expressive interfaces.",
                216,
                194,
                width - 552,
                14,
                "muted",
            ),
        )
        hero = Rect(216, 244, width - 552, 338)
        key = (hero, theme.palette)
        if self._gradient_key != key:
            self._gradient = RadialGradient.two_color(
                paint("accent").with_alpha(0.75),
                paint("surface"),
                center=Point(0.78, 0.35),
                radius=0.8,
            ).to_scene_node("hero-gradient", hero, steps=96, segments=48, z_index=-1)
            for node in self._gradient.walk():
                node.hit_testable = False
            self._gradient_key = key
        if self._gradient:
            root.add(self._gradient)
        cx, cy = hero.right - 145, hero.y + 146
        # Retained geometry gives the abstract mark actual depth and motion.
        for ring in range(3):
            radius = 64 + ring * 22
            for step in range(32):
                angle = step * math.tau / 32 + self.phase * (1 if ring % 2 else -1)
                x = cx + math.cos(angle) * radius
                y = cy + math.sin(angle) * radius * 0.61
                size = 3 + ring * 0.7
                root.add(
                    rectangle(
                        f"orb:{ring}:{step}",
                        Rect(x, y, size, size),
                        paint("text").with_alpha(0.28 + ring * 0.18),
                        size / 2,
                    )
                )
        root.add(rectangle("orb-core", Rect(cx - 26, cy - 26, 52, 52), paint("accent"), 26))
        for node in root.children:
            if node.key.startswith("orb"):
                node.z_index = 2
        card = Rect(hero.x + 24, hero.y + 28, max(270, hero.width * 0.57), 282)
        if self.glass and self.depth > 0:
            material = FrostedGlass(
                blur_radius=self.depth,
                tint=paint("canvas").with_alpha(0.72),
                border_color=paint("text").with_alpha(0.14),
                corner_radius=CornerRadius.uniform(self.radius),
            )
            root.add(material.to_scene_node("preview-glass", card, z_index=1))
        else:
            root.add(rectangle("preview-solid", card, paint("surface"), self.radius))
        root.add(
            text(
                "preview-kicker",
                "SWIR / FUTURE LIGHT" if self.light_mode else "SWIR / FUTURE DARK",
                card.x + 24,
                card.y + 28,
                card.width - 48,
                11,
                "accent",
            ),
            text("preview-title", self.title, card.x + 24, card.y + 72, card.width - 48, 26),
            text(
                "preview-copy",
                "Beautiful by intention.",
                card.x + 24,
                card.y + 133,
                card.width - 48,
                15,
            ),
            text(
                "preview-copy-2",
                "Responsive by nature.",
                card.x + 24,
                card.y + 158,
                card.width - 48,
                15,
                "muted",
            ),
            text(
                "preview-tag",
                "LIVE PREVIEW",
                card.x + 24,
                card.bottom - 51,
                card.width - 48,
                10,
                "accent",
            ),
            rectangle("component-card", Rect(216, 606, width - 552, 166), paint("surface"), 18),
            text("component-title", "Small details. Big difference.", 240, 625, 520, 20),
            text(
                "component-copy",
                "Try the controls. Tab through them. Make it yours.",
                240,
                656,
                width - 600,
                12,
                "muted",
            ),
            text(
                "feedback",
                f"{self.preview_count} interactions · Changes are live",
                240,
                741,
                width - 600,
                11,
                "muted",
            ),
        )
        x = width - 304
        root.add(
            rectangle("inspector", Rect(x, 244, 280, 528), paint("surface"), 18),
            text("inspector-title", "Make it yours", x + 24, 195, 240, 20),
            text("title-label", "CARD TITLE", x + 24, 253, 240, 10, "muted"),
            text("palette-label", "ACCENT COLOR", x + 24, 334, 240, 10, "muted"),
            text(
                "radius-label",
                f"Corner radius                         {self.radius:.0f}",
                x + 24,
                409,
                240,
                12,
                "muted",
            ),
            text(
                "depth-label",
                f"Glass depth                           {self.depth:.0f}",
                x + 24,
                493,
                240,
                12,
                "muted",
            ),
            text(
                "motion-hint", "Motion plays on demand, then rests.", x + 24, 741, 240, 10, "muted"
            ),
            text(
                "footer",
                "Native controls. Real interaction. Your visual language.",
                216,
                height - 49,
                width - 248,
                12,
                "muted",
            ),
        )
        return root


def main() -> int:
    renderer = WgpuRenderer()
    app = App("SwirUI design playground", config=AppConfig(target_fps=120), renderer=renderer)
    window = Window(
        title="SwirUI — Visual playground", width=1440, height=860, min_width=1240, min_height=820
    )
    studio = Studio()
    mount(window, studio)
    studio.controller = AnimationController(app, window)
    app.add_window(window)
    try:
        return app.run()
    finally:
        studio.controller.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
