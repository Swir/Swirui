"""Retained grouped bar chart implementation."""

from __future__ import annotations

from swirui.rendering import Point, Rect, SceneNode

from .cartesian_chart import EPSILON, rectangle_node, text_node
from .large_dataset_chart import LargeDatasetCartesianChart


class BarChart(LargeDatasetCartesianChart):
    """Grouped multi-series bar chart rendered with retained rectangles."""

    include_zero = True
    chart_kind = "bar"

    def add_data_nodes(self, root: SceneNode, plot: Rect, low: float, high: float) -> None:
        slot = self._category_slot_width(plot)
        group_width = slot * 0.72
        bar_step = group_width / len(self.series)
        bar_width = max(1.0, bar_step * 0.82)
        baseline = self.value_y(0.0, plot, low, high)
        for series_index, series in enumerate(self.series):
            color = self.series_color(series_index)
            for point_index in self.render_indices(series_index):
                point = series.points[point_index]
                center = self._category_center(point_index, plot)
                center += (series_index + 0.5) * bar_step - group_width / 2.0
                value_y = self.value_y(point.value, plot, low, high)
                height = abs(value_y - baseline)
                if height <= EPSILON:
                    continue
                root.add(
                    rectangle_node(
                        f"{self.key}:series:{series_index}:bar:{point_index}",
                        Rect(center - bar_width / 2.0, min(value_y, baseline), bar_width, height),
                        color,
                        radius=min(3.0, bar_width / 4.0),
                    )
                )

    def add_category_labels(self, root: SceneNode, plot: Rect) -> None:
        reference = self.series[0].points
        slot = self._category_slot_width(plot)
        for index in self.visible_label_indices(0):
            point = reference[index]
            center = self._category_center(index, plot)
            root.add(
                text_node(
                    f"{self.key}:x:{index}",
                    Rect(center - slot * 0.45, plot.bottom + 7.0, slot * 0.9, 15.0),
                    point.label,
                    10.0,
                )
            )

    def point_position(
        self,
        series_index: int,
        point_index: int,
        plot: Rect,
        low: float,
        high: float,
    ) -> Point:
        series = self.series[series_index]
        slot = self._category_slot_width(plot)
        group_width = slot * 0.72
        bar_step = group_width / len(self.series)
        center = self._category_center(point_index, plot)
        center += (series_index + 0.5) * bar_step - group_width / 2.0
        return Point(center, self.value_y(series.points[point_index].value, plot, low, high))

    def _category_slot_width(self, plot: Rect) -> float:
        viewport = self.viewport
        visible_categories = max(1.0, viewport.x_max - viewport.x_min + 1.0)
        return plot.width / visible_categories

    def _category_center(self, index: int, plot: Rect) -> float:
        viewport = self.viewport
        slot = self._category_slot_width(plot)
        return plot.x + (index - viewport.x_min + 0.5) * slot
