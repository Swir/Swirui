"""Operational dashboard and settings surfaces for SwirUI Studio."""

from __future__ import annotations

import math
from collections.abc import Callable

from . import (
    Badge,
    Button,
    ChartPoint,
    Label,
    Panel,
    ProgressRing,
    Slider,
    StreamingChartSeries,
    StreamingLineChart,
    SurfaceStyle,
    Switch,
    ThemeSurface,
)
from .core import Event
from .rendering import CornerRadius, LinearGradient, Rect, SceneNode, SceneNodeKind
from .theme import FUTURE_DARK


class StudioHero(Panel):
    """A bounded accent wash that inherits the current application palette."""

    def build_scene_node(self) -> SceneNode:
        theme = self.effective_theme or FUTURE_DARK
        node = SceneNode(self.key, SceneNodeKind.RECTANGLE, self.bounds,
                         fill=theme.surface_color("raised"),
                         corner_radius=CornerRadius.uniform(18), clip_to_bounds=True,
                         hit_testable=False, opacity=self.opacity, z_index=self.z_index)
        if self.bounds.width > 0 and self.bounds.height > 0:
            wash = LinearGradient.two_color(
                theme.surface_color("accent").with_alpha(.13),
                theme.surface_color("focus").with_alpha(.03),
            ).to_scene_node(f"{self.key}:wash", self.bounds, steps=24)
            for decoration in wash.walk():
                decoration.hit_testable = False
            node.add(wash)
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
        self.chart = StreamingLineChart(
            (self.cpu_stream, self.gpu_stream),
            bounds=empty,
            key="studio-live-performance",
            title="Sample activity · CPU / GPU",
            y_min=0,
            y_max=100,
        )
        self.status = Badge("DEMO DATA", bounds=empty)
        self.heading = Label("Shape your next idea.", bounds=empty, font_size=32)
        self.subtitle = Label(
            "Explore the visuals. Make them yours.",
            bounds=empty,
            font_size=14,
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
        self.hero.add(self.heading, self.subtitle)
        self.metric_cards = tuple(ThemeSurface(
            bounds=empty, style=SurfaceStyle(elevation=5, border_opacity=.5),
        ) for _ in range(3))
        self.metric_captions = tuple(Label(text, bounds=empty, font_size=12, opacity=.78)
                                     for text in ("PROCESSOR", "GRAPHICS", "FRAME BUDGET"))
        for card, caption, value in zip(
            self.metric_cards, self.metric_captions,
            (self.cpu_label, self.gpu_label, self.frame_label), strict=True,
        ):
            card.add(caption, value)
        self.metric_cards[2].add(self.frame_ring)
        self.disclaimer = Label("Generated samples · not device telemetry", bounds=empty,
                                font_size=12, opacity=.8)
        self.add(self.hero, self.status, *self.metric_cards, self.chart,
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
        hero_height = min(64.0 if compact else 120.0, viewport.height * .24)
        card_height = min(56.0 if compact else 88.0, viewport.height * .19)
        self.hero._set_layout_bounds(Rect(x, y, width, hero_height))
        self.heading.font_size = 32 if width >= 600 else 24
        self.heading._set_layout_bounds(Rect(x + 18, y + 14, max(0, width - 36), 42))
        self.subtitle.visible = hero_height >= 90
        self.subtitle._set_layout_bounds(Rect(x + 20, y + 64, max(0, width - 40), 22))
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
            value.font_size = (24 if index < 2 else 19) if card_width >= 220 else 12
            value._set_layout_bounds(Rect(left + 12, cards_y + (26 if compact else 34),
                                          max(0, card_width - 24), 24))
        self.frame_ring.visible = card_width >= 270
        self.frame_ring._set_layout_bounds(Rect(self.metric_cards[2].bounds.right - 54,
                                               cards_y + 12, 36, 36))
        chart_y = cards_y + card_height + gap
        footer_y = viewport.bottom - pad - 36
        self.chart._set_layout_bounds(Rect(x, chart_y, width, max(0, footer_y - chart_y - gap)))
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


class StudioSettings(Panel):
    """Application-owned settings surface with retained interactive state."""

    def __init__(self) -> None:
        super().__init__(bounds=Rect(0, 0, 760, 540))
        empty = Rect(0, 0, 0, 0)
        self.heading = Label("Studio settings", bounds=empty, font_size=28)
        self.subtitle = Label(
            "Configure the workspace without rebuilding the retained component tree.",
            bounds=empty,
            font_size=14,
        )
        self.autosave = Switch("Autosave project state", bounds=empty, checked=True)
        self.notifications = Switch("Show Studio notifications", bounds=empty, checked=True)
        self.reduced_motion = Switch("Reduce appearance motion", bounds=empty, checked=False)
        self.live_metrics = Switch("Enable demo sample actions", bounds=empty, checked=True)
        self.density = Slider(
            bounds=empty,
            value=100,
            minimum=75,
            maximum=150,
            accessible_name="Workspace density",
        )
        self.density_label = Label("Workspace density · 100%", bounds=empty, font_size=15)
        self.status = Label("Settings are applied to this session.", bounds=empty, font_size=14)
        for key, control in (
            ("autosave", self.autosave),
            ("notifications", self.notifications),
            ("reduced_motion", self.reduced_motion),
            ("live_metrics", self.live_metrics),
        ):
            control.on("changed", self._switch_handler(key))
        self.density.on("changed", self._density_changed)
        self.add(
            self.heading,
            self.subtitle,
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
        x, y = viewport.x + 30, viewport.y + 28
        width = max(0.0, viewport.width - 60)
        self.heading._set_layout_bounds(Rect(x, y, width, 38))
        self.subtitle._set_layout_bounds(Rect(x, y + 46, width, 24))
        self.autosave._set_layout_bounds(Rect(x, y + 100, width, 40))
        self.notifications._set_layout_bounds(Rect(x, y + 150, width, 40))
        self.reduced_motion._set_layout_bounds(Rect(x, y + 200, width, 40))
        self.live_metrics._set_layout_bounds(Rect(x, y + 250, width, 40))
        self.density_label._set_layout_bounds(Rect(x, y + 316, width, 24))
        self.density._set_layout_bounds(Rect(x, y + 348, min(420.0, width), 36))
        self.status._set_layout_bounds(Rect(x, y + 410, width, 26))

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
