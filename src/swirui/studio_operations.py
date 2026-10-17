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
    Switch,
)
from .core import Event
from .rendering import Rect


class StudioDashboard(Panel):
    """Live, bounded operational dashboard for one retained Studio session."""

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
            title="Live performance",
            y_min=0,
            y_max=100,
        )
        self.status = Badge("LIVE METRICS", bounds=empty)
        self.heading = Label("Runtime command center", bounds=empty, font_size=28)
        self.subtitle = Label(
            "Bounded retained telemetry samples for the active Studio session.",
            bounds=empty,
            font_size=14,
        )
        self.cpu_label = Label("CPU 49%", bounds=empty, font_size=18)
        self.gpu_label = Label("GPU 46%", bounds=empty, font_size=18)
        self.frame_label = Label("144 FPS · 6.9 ms", bounds=empty, font_size=16)
        self.frame_ring = ProgressRing(
            bounds=empty,
            value=100,
            accessible_name="Frame rate budget",
        )
        self.pulse_button = Button("Record sample", bounds=empty)
        self.pulse_button.on("click", lambda _: self.pulse())
        self._sample_index = len(cpu_points)
        self.add(
            self.status,
            self.heading,
            self.subtitle,
            self.chart,
            self.cpu_label,
            self.gpu_label,
            self.frame_label,
            self.frame_ring,
            self.pulse_button,
        )

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
        x, y = viewport.x, viewport.y
        width, height = viewport.width, viewport.height
        pad = 24.0
        self.status._set_layout_bounds(Rect(x + pad, y + 18, 142, 30))
        self.heading._set_layout_bounds(Rect(x + pad, y + 58, max(0.0, width - 48), 38))
        self.subtitle._set_layout_bounds(Rect(x + pad, y + 100, max(0.0, width - 48), 24))
        if width >= 720:
            metrics_width = 210.0
            chart_width = max(0.0, width - metrics_width - 3 * pad)
            self.chart._set_layout_bounds(
                Rect(x + pad, y + 142, chart_width, max(0.0, height - 174))
            )
            metric_x = x + 2 * pad + chart_width
            self.frame_ring._set_layout_bounds(Rect(metric_x + 45, y + 150, 116, 116))
            self.frame_label._set_layout_bounds(Rect(metric_x, y + 278, metrics_width, 28))
            self.cpu_label._set_layout_bounds(Rect(metric_x, y + 326, metrics_width, 28))
            self.gpu_label._set_layout_bounds(Rect(metric_x, y + 364, metrics_width, 28))
            self.pulse_button._set_layout_bounds(Rect(metric_x, y + 416, metrics_width, 40))
        else:
            available = max(0.0, height - 278.0)
            chart_height = min(max(140.0, height * 0.48), available)
            self.chart._set_layout_bounds(
                Rect(x + pad, y + 136, max(0.0, width - 2 * pad), chart_height)
            )
            metric_y = min(viewport.bottom - 100.0, y + 150 + chart_height)
            self.frame_ring._set_layout_bounds(Rect(x + pad, metric_y, 88, 88))
            self.frame_label._set_layout_bounds(
                Rect(x + 126, metric_y + 4, max(0.0, width - 150), 24)
            )
            self.cpu_label._set_layout_bounds(Rect(x + 126, metric_y + 34, 130, 24))
            self.gpu_label._set_layout_bounds(Rect(x + 260, metric_y + 34, 130, 24))
            self.pulse_button._set_layout_bounds(Rect(x + 126, metric_y + 62, 190, 36))

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
        self.live_metrics = Switch("Enable live performance samples", bounds=empty, checked=True)
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
