"""Bounded live-data primitives for retained SwirUI charts.

The buffer is safe for producer-thread ingestion. Visual refresh remains an explicit
UI/runtime operation so background producers never mutate the retained component tree.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Hashable, Sequence
from threading import RLock

from swirui.rendering import Color, Rect

from .charts import ChartPoint, ChartSeries
from .line_area_chart import LineChart


class StreamingChartSeries:
    """Thread-safe bounded chart series for live and streaming data.

    Producers may append samples from worker threads. Consumers obtain an immutable
    :class:`ChartSeries` snapshot and can refresh a retained chart on the UI/runtime
    thread. Capacity is fixed so long-running streams keep bounded memory use.
    """

    def __init__(
        self,
        key: Hashable,
        name: str,
        points: Sequence[ChartPoint],
        *,
        capacity: int = 256,
        color: Color | None = None,
    ) -> None:
        hash(key)
        normalized_name = str(name).strip()
        if not normalized_name:
            raise ValueError("StreamingChartSeries name must not be empty.")
        if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity < 2:
            raise ValueError("capacity must be an integer greater than or equal to 2.")

        normalized = tuple(points)
        if not normalized:
            raise ValueError("StreamingChartSeries requires at least one initial point.")
        self._validate_unique_keys(normalized)

        retained = normalized[-capacity:]
        self._key = key
        self._name = normalized_name
        self._capacity = capacity
        self._color = color
        self._points: deque[ChartPoint] = deque(retained, maxlen=capacity)
        self._revision = 0
        self._dropped_count = max(0, len(normalized) - capacity)
        self._lock = RLock()

    @property
    def key(self) -> Hashable:
        return self._key

    @property
    def name(self) -> str:
        return self._name

    @property
    def capacity(self) -> int:
        return self._capacity

    @property
    def color(self) -> Color | None:
        return self._color

    @property
    def revision(self) -> int:
        with self._lock:
            return self._revision

    @property
    def dropped_count(self) -> int:
        with self._lock:
            return self._dropped_count

    @property
    def point_count(self) -> int:
        with self._lock:
            return len(self._points)

    @property
    def latest(self) -> ChartPoint:
        with self._lock:
            return self._points[-1]

    def append(self, point: ChartPoint) -> ChartPoint | None:
        """Append one point and return the evicted point when capacity is full."""

        if not isinstance(point, ChartPoint):
            raise TypeError("point must be a ChartPoint.")
        with self._lock:
            return self._append_unlocked(point)

    def extend(self, points: Sequence[ChartPoint]) -> tuple[ChartPoint, ...]:
        """Append a batch atomically and return all points evicted by the batch."""

        normalized = tuple(points)
        if not normalized:
            return ()
        if any(not isinstance(point, ChartPoint) for point in normalized):
            raise TypeError("points must contain only ChartPoint values.")

        with self._lock:
            dropped: list[ChartPoint] = []
            for point in normalized:
                evicted = self._append_unlocked(point)
                if evicted is not None:
                    dropped.append(evicted)
            return tuple(dropped)

    def snapshot(self) -> ChartSeries:
        """Return an immutable snapshot suitable for any retained chart."""

        _, snapshot = self.snapshot_state()
        return snapshot

    def snapshot_state(self) -> tuple[int, ChartSeries]:
        """Atomically return ``(revision, snapshot)`` for minimal refresh scheduling."""

        with self._lock:
            return (
                self._revision,
                ChartSeries(
                    self._key,
                    self._name,
                    tuple(self._points),
                    color=self._color,
                ),
            )

    def _append_unlocked(self, point: ChartPoint) -> ChartPoint | None:
        current = tuple(self._points)
        remaining = current[1:] if len(current) == self._capacity else current
        if any(existing.key == point.key for existing in remaining):
            raise ValueError(f"Duplicate streaming chart point key: {point.key!r}")

        dropped = self._points.popleft() if len(self._points) == self._capacity else None
        self._points.append(point)
        self._revision += 1
        if dropped is not None:
            self._dropped_count += 1
        return dropped

    @staticmethod
    def _validate_unique_keys(points: Sequence[ChartPoint]) -> None:
        keys: set[Hashable] = set()
        for point in points:
            if not isinstance(point, ChartPoint):
                raise TypeError("points must contain only ChartPoint values.")
            if point.key in keys:
                raise ValueError(f"Duplicate streaming chart point key: {point.key!r}")
            keys.add(point.key)


class StreamingLineChart(LineChart):
    """Retained line chart backed by bounded live-data series.

    Stream buffers may ingest data concurrently. ``refresh()`` is intentionally
    explicit and should be called by the UI/runtime loop; it only invalidates the
    retained chart when one of the source revisions changed.
    """

    chart_kind = "streaming line"

    def __init__(
        self,
        streams: Sequence[StreamingChartSeries],
        *,
        bounds: Rect,
        key: str | None = None,
        title: str | None = None,
        y_min: float | None = None,
        y_max: float | None = None,
    ) -> None:
        self._streams = self._validate_streams(streams)
        states = tuple(stream.snapshot_state() for stream in self._streams)
        self._stream_revisions = tuple(revision for revision, _ in states)
        self._paused = False
        super().__init__(
            tuple(snapshot for _, snapshot in states),
            bounds=bounds,
            key=key,
            title=title,
            y_min=y_min,
            y_max=y_max,
        )

    @property
    def streams(self) -> tuple[StreamingChartSeries, ...]:
        return self._streams

    @property
    def paused(self) -> bool:
        return self._paused

    def pause(self) -> None:
        """Freeze visual refresh while stream buffers continue accepting points."""

        self._paused = True

    def resume(self) -> bool:
        """Resume visual refresh and publish the newest buffered snapshot."""

        was_paused = self._paused
        self._paused = False
        return self.refresh(force=was_paused)

    def refresh(self, *, force: bool = False) -> bool:
        """Publish new stream snapshots only when source revisions changed."""

        if self._paused and not force:
            return False

        states = tuple(stream.snapshot_state() for stream in self._streams)
        revisions = tuple(revision for revision, _ in states)
        if not force and revisions == self._stream_revisions:
            return False

        self.set_series(tuple(snapshot for _, snapshot in states))
        self._stream_revisions = revisions
        self.emit("stream_refreshed", revisions=revisions)
        return True

    def append(
        self,
        series_key: Hashable,
        point: ChartPoint,
        *,
        refresh: bool = True,
    ) -> ChartPoint | None:
        """Append to one stream and optionally refresh the retained visual."""

        stream = self._stream_for(series_key)
        dropped = stream.append(point)
        if refresh:
            self.refresh()
        return dropped

    def extend(
        self,
        series_key: Hashable,
        points: Sequence[ChartPoint],
        *,
        refresh: bool = True,
    ) -> tuple[ChartPoint, ...]:
        """Append a batch to one stream and optionally refresh once."""

        stream = self._stream_for(series_key)
        dropped = stream.extend(points)
        if refresh and points:
            self.refresh()
        return dropped

    def _stream_for(self, series_key: Hashable) -> StreamingChartSeries:
        for stream in self._streams:
            if stream.key == series_key:
                return stream
        raise KeyError(f"Unknown streaming chart series key: {series_key!r}")

    @staticmethod
    def _validate_streams(
        streams: Sequence[StreamingChartSeries],
    ) -> tuple[StreamingChartSeries, ...]:
        normalized = tuple(streams)
        if not normalized:
            raise ValueError("StreamingLineChart requires at least one stream.")
        keys: set[Hashable] = set()
        for stream in normalized:
            if not isinstance(stream, StreamingChartSeries):
                raise TypeError("streams must contain only StreamingChartSeries values.")
            if stream.key in keys:
                raise ValueError(f"Duplicate streaming chart series key: {stream.key!r}")
            keys.add(stream.key)
        return normalized


__all__ = ["StreamingChartSeries", "StreamingLineChart"]
