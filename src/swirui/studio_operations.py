"""Operational dashboard and settings surfaces for SwirUI Studio."""

from __future__ import annotations

import math
from collections.abc import Callable

from . import (
    AnimationController,
    Badge,
    Button,
    ButtonVariant,
    ChartPoint,
    Input,
    Label,
    Panel,
    ProgressRing,
    ScrollView,
    SilkRibbon,
    Slider,
    StreamingAreaChart,
    StreamingChartSeries,
    SurfaceStyle,
    Switch,
    ThemeSurface,
)
from .core import Event
from .rendering import CornerRadius, Rect, SceneNode, SceneNodeKind
from .theme import FUTURE_DARK, ColorRole


class StudioHero(Panel):
    """Backdrop for the material library and its controls."""

    def build_scene_node(self) -> SceneNode:
        theme = self.effective_theme or FUTURE_DARK
        return SceneNode(self.key, SceneNodeKind.RECTANGLE, self.bounds,
                         fill=theme.surface_color("surface"),
                         corner_radius=CornerRadius.uniform(18), clip_to_bounds=True,
                         hit_testable=False, opacity=self.opacity, z_index=self.z_index)


class StudioSampleBars(Panel):
    """Small decorative history using the same samples as the main chart."""

    def __init__(self, stream: StreamingChartSeries, role: ColorRole) -> None:
        super().__init__(bounds=Rect(0, 0, 0, 0))
        self.stream = stream
        self.role = role

    def build_scene_node(self) -> SceneNode:
        node = SceneNode(self.key, SceneNodeKind.GROUP, self.bounds, hit_testable=False)
        if self.bounds.width <= 0 or self.bounds.height <= 0:
            return node
        theme = self.effective_theme or FUTURE_DARK
        points = self.stream.snapshot().points[-12:]
        step = self.bounds.width / len(points)
        for index, point in enumerate(points):
            height = max(2, self.bounds.height * point.value / 100)
            node.add(SceneNode(
                f"{self.key}:bar:{index}", SceneNodeKind.RECTANGLE,
                Rect(self.bounds.x + index * step, self.bounds.bottom - height,
                     max(1, step - 3), height),
                fill=theme.surface_color(self.role).with_alpha(
                    .25 + .65 * (index + 1) / len(points)),
                corner_radius=CornerRadius.uniform(2), hit_testable=False,
            ))
        return node


class StudioDashboard(Panel):
    """Responsive visual workspace with explicitly labelled demonstration data."""

    def __init__(self) -> None:
        super().__init__(bounds=Rect(0, 0, 760, 540))
        empty = Rect(0, 0, 0, 0)
        cpu_points = tuple(
            ChartPoint(index, f"T{index + 1}", value)
            for index, value in enumerate((34, 37, 41, 39, 46, 52, 48, 44, 57, 61, 54, 49))
        )
        gpu_points = tuple(
            ChartPoint(index, f"T{index + 1}", value)
            for index, value in enumerate((28, 31, 35, 42, 38, 45, 51, 47, 55, 58, 52, 46))
        )
        self.cpu_stream = StreamingChartSeries(
            "cpu", "CPU", cpu_points, capacity=60
        )
        self.gpu_stream = StreamingChartSeries(
            "gpu", "GPU", gpu_points, capacity=60
        )
        self.chart = StreamingAreaChart(
            (self.cpu_stream, self.gpu_stream),
            bounds=empty,
            key="studio-live-performance",
            title="Sample activity · CPU / GPU",
            y_min=0,
            y_max=100,
        )
        self.status = Badge("DEMO DATA", bounds=empty)
        self.heading = Label("Material library", bounds=empty, font_size=36)
        self.subtitle = Label("Open a material in the preview canvas.", bounds=empty, font_size=14)
        self.ribbon = SilkRibbon(bounds=empty)
        self.material_buttons = tuple(
            Button(kind.title(), bounds=empty, variant=ButtonVariant.SECONDARY,
                   accessible_name=f"Open {kind} material preview")
            for kind in ("glass", "acrylic", "solid")
        )
        self.cpu_label = Label("CPU 49%", bounds=empty, font_size=18)
        self.gpu_label = Label("GPU 46%", bounds=empty, font_size=18)
        self.cpu_label._theme_styles["_color"] = ("text", "accent", self.cpu_label.color)
        self.gpu_label._theme_styles["_color"] = ("text", "success", self.gpu_label.color)
        self.frame_label = Label("144 FPS · 6.9 ms", bounds=empty, font_size=16)
        self.frame_ring = ProgressRing(
            bounds=empty,
            value=100,
            accessible_name="Demonstration frame budget",
        )
        self.pulse_button = Button("Next sample", bounds=empty)
        self.pulse_button.on("click", lambda _: self.pulse())
        self._sample_index = len(cpu_points)
        self.hero = StudioHero(bounds=empty)
        self.hero.add(self.ribbon, self.heading, self.subtitle, *self.material_buttons)
        self.metric_cards = tuple(ThemeSurface(
            bounds=empty, style=SurfaceStyle(elevation=4, border_opacity=.45,
                                             glow_radius=8, glow_opacity=.015),
        ) for _ in range(3))
        self.metric_captions = tuple(Label(text, bounds=empty, font_size=12, opacity=.78)
                                     for text in ("PROCESSOR", "GRAPHICS", "FRAME BUDGET"))
        for card, caption, value in zip(
            self.metric_cards, self.metric_captions,
            (self.cpu_label, self.gpu_label, self.frame_label), strict=True,
        ):
            card.add(caption, value)
        self.metric_cards[2].add(self.frame_ring)
        self.sample_bars = (StudioSampleBars(self.cpu_stream, "accent"),
                            StudioSampleBars(self.gpu_stream, "success"))
        for card, bars in zip(self.metric_cards[:2], self.sample_bars, strict=True):
            card.add(bars)
        self.chart_surface = ThemeSurface(
            bounds=empty, style=SurfaceStyle(elevation=2, border_opacity=.35),
        )
        self.chart_surface.add(self.chart)
        self.disclaimer = Label("Generated samples · not device telemetry", bounds=empty,
                                font_size=12, opacity=.8)
        self.add(self.hero, self.status, *self.metric_cards, self.chart_surface,
                 self.disclaimer, self.pulse_button)

    @property
    def sample_index(self) -> int:
        return self._sample_index

    def record_sample(self, cpu: float, gpu: float, frame_ms: float) -> None:
        cpu_value = self._percentage(cpu, "cpu")
        gpu_value = self._percentage(gpu, "gpu")
        frame_value = float(frame_ms)
        if not math.isfinite(frame_value) or frame_value <= 0:
            raise ValueError("frame_ms must be finite and greater than zero.")
        index = self._sample_index
        label = f"T{index + 1}"
        self.chart.append(
            "cpu",
            ChartPoint(index, label, cpu_value),
            refresh=False,
        )
        self.chart.append(
            "gpu",
            ChartPoint(index, label, gpu_value),
            refresh=False,
        )
        self.chart.refresh()
        for bars in self.sample_bars:
            bars.invalidate()
        self._sample_index += 1
        fps = min(999.0, 1000.0 / frame_value)
        self.cpu_label.text = f"CPU {cpu_value:.0f}%"
        self.gpu_label.text = f"GPU {gpu_value:.0f}%"
        self.frame_label.text = f"{fps:.0f} FPS · {frame_value:.1f} ms"
        self.frame_ring.value = min(100.0, fps / 1.44)
        self.emit(
            "sampled",
            cpu=cpu_value,
            gpu=gpu_value,
            frame_ms=frame_value,
            fps=fps,
        )

    def pulse(self) -> None:
        index = self._sample_index
        cpu = 38.0 + float((index * 13) % 47)
        gpu = 32.0 + float((index * 17) % 53)
        frame_ms = 6.4 + float(index % 6) * 1.25
        self.record_sample(cpu, gpu, frame_ms)

    def prepare_layout(self, viewport: Rect) -> None:
        self._set_layout_bounds(viewport)
        compact = viewport.height < 440
        pad = min(14.0 if compact else 20.0, viewport.width / 12)
        gap = 8.0 if compact else 12.0
        x, y = viewport.x + pad, viewport.y + pad
        width = max(0.0, viewport.width - 2 * pad)
        hero_height = min(74.0 if compact else 176.0, viewport.height * .25)
        card_height = min(56.0 if compact else 104.0, viewport.height * .19)
        self.hero._set_layout_bounds(Rect(x, y, width, hero_height))
        inset = 12 if compact else 20
        button_width = min(78.0, max(0.0, (width - 2 * inset - 12) / 3))
        controls_width = 3 * button_width + 12
        detail = hero_height >= 120
        self.heading.font_size = 36 if detail else 19
        self.heading._set_layout_bounds(Rect(x + inset, y + (12 if detail else 2),
                                             controls_width + 16, 46 if detail else 26))
        self.subtitle.visible = detail
        self.subtitle._set_layout_bounds(Rect(x + inset, y + 65, controls_width + 20, 22))
        button_height = 34 if detail else 28
        button_y = y + hero_height - button_height - (14 if detail else 5)
        for index, button in enumerate(self.material_buttons):
            button._set_layout_bounds(Rect(x + inset + index * (button_width + 6),
                                           button_y, button_width, button_height))
        art_left = x + inset + controls_width + 22
        self.ribbon._set_layout_bounds(Rect(art_left, y, max(0, x + width - art_left - 8),
                                             hero_height))
        cards_y = y + hero_height + gap
        card_width = max(0, (width - 2 * gap) / 3)
        for index, (card, caption, value) in enumerate(zip(
            self.metric_cards, self.metric_captions,
            (self.cpu_label, self.gpu_label, self.frame_label), strict=True,
        )):
            left = x + index * (card_width + gap)
            card._set_layout_bounds(Rect(left, cards_y, card_width, card_height))
            caption.font_size = 12 if card_width >= 160 else 10
            caption._set_layout_bounds(Rect(left + 12, cards_y + 6, max(0, card_width - 24), 18))
            value.font_size = (28 if index < 2 else 19) if card_width >= 200 else 14
            if compact:
                value.font_size = min(18, value.font_size)
            value._set_layout_bounds(Rect(left + 12, cards_y + (26 if compact else 34),
                                          max(0, card_width - 24),
                                          36 if value.font_size > 20 else 24))
        for card, bars in zip(self.metric_cards[:2], self.sample_bars, strict=True):
            bars.visible = card_height >= 90
            bars._set_layout_bounds(Rect(card.bounds.x + 12, cards_y + card_height - 27,
                                         max(0, card_width - 24), 20))
        self.frame_ring.visible = card_width >= 270
        self.frame_ring._set_layout_bounds(Rect(self.metric_cards[2].bounds.right - 54,
                                               cards_y + 12, 36, 36))
        chart_y = cards_y + card_height + gap
        footer_y = viewport.bottom - pad - 36
        chart_height = max(0, footer_y - chart_y - gap)
        self.chart_surface._set_layout_bounds(Rect(x, chart_y, width, chart_height))
        inset = 6 if compact else 12
        self.chart._set_layout_bounds(Rect(x + inset, chart_y + inset,
                                           max(0, width - 2 * inset),
                                           max(0, chart_height - 2 * inset)))
        self.status._set_layout_bounds(Rect(x, footer_y, 110, 30))
        self.disclaimer.visible = width >= 620
        self.disclaimer._set_layout_bounds(Rect(x + 122, footer_y + 6,
                                                max(0, width - 274), 20))
        self.pulse_button._set_layout_bounds(Rect(x + max(0, width - 132), footer_y, 132, 34))

    @staticmethod
    def _percentage(value: float, name: str) -> float:
        result = float(value)
        if not math.isfinite(result) or not 0.0 <= result <= 100.0:
            raise ValueError(f"{name} must be finite and in [0, 100].")
        return result


class StudioSettingsScroll(ScrollView):
    """Settings viewport with a non-interactive scroll position indicator."""

    def build_scene_node(self) -> SceneNode:
        node = super().build_scene_node()
        if self.max_scroll_y > 0 and self.bounds.height > 0:
            theme = self.effective_theme or FUTURE_DARK
            height = min(self.bounds.height, max(24, self.bounds.height ** 2 / self.content_height))
            top = self.bounds.y + (self.bounds.height - height) * self.scroll_y / self.max_scroll_y
            node.add(SceneNode(
                f"{self.key}:position", SceneNodeKind.RECTANGLE,
                Rect(self.bounds.right - 6, top, 4, height),
                fill=theme.surface_color("muted").with_alpha(.5),
                corner_radius=CornerRadius.uniform(2), z_index=100_000, hit_testable=False,
            ))
        return node


class StudioSettings(Panel):
    """Application-owned settings surface with retained interactive state."""

    def __init__(self, *, animations: AnimationController | None = None) -> None:
        super().__init__(bounds=Rect(0, 0, 760, 540))
        empty = Rect(0, 0, 0, 0)
        self.heading = Label("Make it yours.", bounds=empty, font_size=30)
        self.subtitle = Label(
            "One signature color. A whole new atmosphere.",
            bounds=empty,
            font_size=14,
        )
        self.autosave = Switch("Autosave project state", bounds=empty, checked=True,
                               animations=animations)
        self.notifications = Switch("Show Studio notifications", bounds=empty, checked=True,
                                    animations=animations)
        self.reduced_motion = Switch("Reduce appearance motion", bounds=empty,
                                     animations=animations)
        self.live_metrics = Switch("Enable demo sample actions", bounds=empty, checked=True,
                                   animations=animations)
        self.density = Slider(
            bounds=empty,
            value=100,
            minimum=75,
            maximum=150,
            accessible_name="Workspace density",
        )
        self.density_label = Label("Workspace density · 100%", bounds=empty, font_size=15)
        self.status = Label("Settings are applied to this session.", bounds=empty, font_size=14)
        self.accent: str | None = None
        self.appearance_card = ThemeSurface(
            bounds=empty, style=SurfaceStyle(elevation=3, border_opacity=.4),
        )
        self.accent_caption = Label("SIGNATURE COLOR", bounds=empty, font_size=12, opacity=.8)
        self.accent_input = Input("#62DEFF", bounds=empty, accessible_name="Accent hex color")
        self.apply_accent_button = Button("Apply", bounds=empty)
        self.reset_accent_button = Button("Reset", bounds=empty)
        self.accent_status = Label("Choose a color or enter your own hex.", bounds=empty,
                                   font_size=13)
        self.apply_accent_button.on("click", self._submit_accent)
        self.accent_input.on("submitted", self._submit_accent)
        self.reset_accent_button.on("click", self._reset_accent)
        self.swatches = tuple(
            Button(name, bounds=empty, theme=FUTURE_DARK.with_accent(color), font_size=14,
                   accessible_name=f"Use {name} accent {color}")
            for name, color in (("Ice", "#62DEFF"), ("Mint", "#7FE0BF"),
                                ("Violet", "#B6A0FF"), ("Rose", "#FF7ADE"),
                                ("Amber", "#F3D083"), ("Coral", "#FF9DAF"))
        )
        for button in self.swatches:
            assert button.theme is not None
            color = button.theme.palette.accent
            button.on("click", self._accent_handler(color))
        self.appearance_card.add(self.accent_caption, self.accent_input,
                                 self.apply_accent_button, self.reset_accent_button,
                                 *self.swatches, self.accent_status)
        self.runtime_heading = Label("Workspace preferences", bounds=empty, font_size=21)
        self.scroll = StudioSettingsScroll(
            bounds=empty, accessible_name="Appearance and workspace settings",
        )
        for control in (self.accent_input, self.apply_accent_button, self.reset_accent_button,
                        *self.swatches, self.autosave, self.notifications, self.reduced_motion,
                        self.live_metrics, self.density):
            control.on("focus_gained", self._reveal_control)
        for key, control in (
            ("autosave", self.autosave),
            ("notifications", self.notifications),
            ("reduced_motion", self.reduced_motion),
            ("live_metrics", self.live_metrics),
        ):
            control.on("changed", self._switch_handler(key))
        self.density.on("changed", self._density_changed)
        self.add(self.scroll)
        self.scroll.add(
            self.heading,
            self.subtitle,
            self.appearance_card,
            self.runtime_heading,
            self.autosave,
            self.notifications,
            self.reduced_motion,
            self.live_metrics,
            self.density_label,
            self.density,
            self.status,
        )

    @property
    def snapshot(self) -> dict[str, bool | float]:
        return {
            "autosave": self.autosave.checked,
            "notifications": self.notifications.checked,
            "reduced_motion": self.reduced_motion.checked,
            "live_metrics": self.live_metrics.checked,
            "density": self.density.value,
        }

    def prepare_layout(self, viewport: Rect) -> None:
        self._set_layout_bounds(viewport)
        self.scroll._set_layout_bounds(viewport)
        # ScrollView children use content-local coordinates, independent of the
        # dock pane's position. Every setting stays reachable on compact windows.
        x, width = 24.0, max(0.0, viewport.width - 48)
        self.heading._set_layout_bounds(Rect(x, 24, width, 42))
        self.subtitle.font_size = 13 if width < 500 else 14
        self.subtitle._set_layout_bounds(Rect(x, 72, width, 24))
        narrow = width < 650
        card_height = 258.0 if narrow else 210.0
        self.appearance_card._set_layout_bounds(Rect(x, 112, width, card_height))
        inner_x, inner_width = x + 16, max(0.0, width - 32)
        self.accent_caption._set_layout_bounds(Rect(inner_x, 132, inner_width, 20))
        input_width = max(0, inner_width - 172)
        self.accent_input._set_layout_bounds(Rect(inner_x, 166, input_width, 42))
        self.apply_accent_button._set_layout_bounds(Rect(inner_x + input_width + 8, 166, 74, 42))
        self.reset_accent_button._set_layout_bounds(Rect(inner_x + input_width + 90, 166, 82, 42))
        columns = 3 if narrow else 6
        swatch_width = max(0, (inner_width - (columns - 1) * 8) / columns)
        for index, swatch in enumerate(self.swatches):
            swatch._set_layout_bounds(Rect(inner_x + (index % columns) * (swatch_width + 8),
                                           226 + (index // columns) * 48, swatch_width, 38))
        self.accent_status._set_layout_bounds(Rect(inner_x, 112 + card_height - 38,
                                                   inner_width, 24))
        y = 112 + card_height + 28
        self.runtime_heading._set_layout_bounds(Rect(x, y, width, 32))
        for index, control in enumerate((self.autosave, self.notifications,
                                         self.reduced_motion, self.live_metrics)):
            control._set_layout_bounds(Rect(x, y + 46 + index * 46, width, 40))
        self.density_label._set_layout_bounds(Rect(x, y + 244, width, 24))
        self.density._set_layout_bounds(Rect(x, y + 278, min(420.0, width), 36))
        self.status._set_layout_bounds(Rect(x, y + 332, width, 26))
        self.scroll.set_content_size(width=viewport.width, height=y + 382)

    def set_accent(self, value: str | None) -> bool:
        """Validate before emitting a change; bad input leaves the active theme intact."""
        try:
            theme = self.effective_theme or FUTURE_DARK
            normalized = None if value is None else theme.with_accent(value).palette.accent
        except ValueError:
            self.accent_status.text = "Use an opaque hex color, e.g. #B6A0FF."
            return False
        self.accent = normalized
        if normalized is not None:
            self.accent_input.value = normalized
        self.accent_status.text = ("Default appearance restored." if normalized is None
                                   else f"{normalized} applied throughout Studio.")
        self.emit("accent_changed", value=normalized)
        return True

    def _accent_handler(self, color: str) -> Callable[[Event], None]:
        def choose(_event: Event) -> None:
            self.set_accent(color)
        return choose

    def _submit_accent(self, _event: Event) -> None:
        self.set_accent(self.accent_input.value)

    def _reset_accent(self, _event: Event) -> None:
        self.set_accent(None)

    def _reveal_control(self, event: Event) -> None:
        control = event.source
        if not isinstance(control, (Button, Input, Switch, Slider)):
            return
        top, bottom = self.scroll.scroll_y, self.scroll.scroll_y + self.scroll.bounds.height
        if control.bounds.y < top + 8:
            self.scroll.scroll_to(y=control.bounds.y - 8)
        elif control.bounds.bottom > bottom - 8:
            self.scroll.scroll_to(y=control.bounds.bottom - self.scroll.bounds.height + 8)

    def _switch_handler(self, key: str) -> Callable[[Event], None]:
        def changed(event: Event) -> None:
            self._switch_changed(key, event)

        return changed

    def _switch_changed(self, key: str, _event: Event) -> None:
        value = bool(self.snapshot[key])
        self.status.text = f"{key.replace('_', ' ').title()}: {'on' if value else 'off'}"
        self.emit("settings_changed", key=key, value=value, snapshot=self.snapshot)

    def _density_changed(self, event: Event) -> None:
        value = float(event.data["value"])
        self.density_label.text = f"Workspace density · {value:.0f}%"
        self.status.text = "Workspace density updated for this session."
        self.emit("settings_changed", key="density", value=value, snapshot=self.snapshot)
