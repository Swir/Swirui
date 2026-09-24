"""Retained audio spectrum visualization backed by native Rust analysis."""

from __future__ import annotations

import importlib
import math
from typing import Any

from swirui.audio import AudioClip
from swirui.core import AccessibilityRole
from swirui.microphone import MicrophoneChunk
from swirui.rendering.geometry import Color, Rect
from swirui.rendering.scene import SceneNode, SceneNodeKind

from .base import Widget

_BACKGROUND = Color.from_hex("#101920")
_SPECTRUM = Color.from_hex("#0A98F0")
_MAX_BINS = 512


def spectrum_magnitudes_pcm16(
    pcm16: bytes,
    *,
    channels: int,
    bins: int = 64,
) -> tuple[float, ...]:
    """Return bounded linear-frequency magnitudes for interleaved PCM16 audio."""

    channel_count = int(channels)
    bin_count = int(bins)
    if not 1 <= channel_count <= 8:
        raise ValueError("channels must be in the range [1, 8].")
    if not 1 <= bin_count <= _MAX_BINS:
        raise ValueError(f"bins must be in the range [1, {_MAX_BINS}].")
    raw = _native_module().spectrum_magnitudes_pcm16(
        channel_count,
        bytes(pcm16),
        bin_count,
    )
    magnitudes = tuple(float(value) for value in raw)
    if any(not math.isfinite(value) or value < 0.0 or value > 1.0 for value in magnitudes):
        raise RuntimeError("Native spectrum core returned an invalid magnitude.")
    return magnitudes


class SpectrumVisualizer(Widget):
    """GPU-retained spectrum bars driven by native bounded PCM16 analysis.

    Python owns source updates, smoothing, accessibility and retained scene
    construction. Rust performs the bounded analysis kernel, while bar geometry is
    submitted through SwirUI's existing HiDPI-aware persistent wgpu renderer.
    """

    def __init__(
        self,
        *,
        bounds: Rect,
        bins: int = 64,
        smoothing: float = 0.35,
        color: Color = _SPECTRUM,
        background: Color = _BACKGROUND,
        key: str | None = None,
        opacity: float = 1.0,
        z_index: int = 0,
        accessible_name: str | None = None,
        accessible_description: str | None = None,
    ) -> None:
        bin_count = int(bins)
        smoothing_value = float(smoothing)
        if not 1 <= bin_count <= _MAX_BINS:
            raise ValueError(f"bins must be in the range [1, {_MAX_BINS}].")
        if not math.isfinite(smoothing_value) or not 0.0 <= smoothing_value < 1.0:
            raise ValueError("smoothing must be finite and in the range [0, 1).")
        self._bin_count = bin_count
        self._smoothing = smoothing_value
        self._color = color
        self._background = background
        self._magnitudes: tuple[float, ...] = ()
        self._sample_rate = 0
        self._channels = 0
        super().__init__(
            bounds=bounds,
            key=key,
            opacity=opacity,
            z_index=z_index,
            clip_to_bounds=True,
            focusable=False,
            accessibility_role=AccessibilityRole.IMAGE,
            accessible_name=accessible_name or "Audio spectrum",
            accessible_description=accessible_description,
        )
        self._sync_accessibility()

    @property
    def bin_count(self) -> int:
        return self._bin_count

    @property
    def smoothing(self) -> float:
        return self._smoothing

    @property
    def magnitudes(self) -> tuple[float, ...]:
        return self._magnitudes

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    @property
    def channels(self) -> int:
        return self._channels

    def set_audio_clip(self, clip: AudioClip) -> SpectrumVisualizer:
        """Replace the spectrum using a validated :class:`AudioClip`."""

        return self._set_pcm_source(
            clip.pcm16,
            sample_rate=clip.sample_rate,
            channels=clip.channels,
        )

    def set_microphone_chunk(self, chunk: MicrophoneChunk) -> SpectrumVisualizer:
        """Replace the spectrum using one validated microphone chunk."""

        return self._set_pcm_source(
            chunk.pcm16,
            sample_rate=chunk.sample_rate,
            channels=chunk.channels,
        )

    def set_magnitudes(
        self,
        magnitudes: tuple[float, ...] | list[float],
        *,
        sample_rate: int = 0,
        channels: int = 0,
        smooth: bool = False,
    ) -> SpectrumVisualizer:
        """Set precomputed magnitudes, optionally applying temporal smoothing."""

        normalized = tuple(float(value) for value in magnitudes)
        if len(normalized) > _MAX_BINS:
            raise ValueError(f"Spectrum magnitudes cannot exceed {_MAX_BINS} bins.")
        if any(not math.isfinite(value) or value < 0.0 or value > 1.0 for value in normalized):
            raise ValueError("Spectrum magnitudes must be finite values in the range [0, 1].")
        if sample_rate < 0:
            raise ValueError("sample_rate cannot be negative.")
        if channels < 0 or channels > 8:
            raise ValueError("channels must be in the range [0, 8].")

        if smooth and self._magnitudes and len(self._magnitudes) == len(normalized):
            persistence = self._smoothing
            normalized = tuple(
                min(1.0, max(0.0, previous * persistence + current * (1.0 - persistence)))
                for previous, current in zip(self._magnitudes, normalized, strict=True)
            )

        if (
            normalized == self._magnitudes
            and int(sample_rate) == self._sample_rate
            and int(channels) == self._channels
        ):
            return self

        self._magnitudes = normalized
        self._sample_rate = int(sample_rate)
        self._channels = int(channels)
        self._sync_accessibility()
        self.invalidate(reason="spectrum_data")
        return self

    def reset(self) -> SpectrumVisualizer:
        """Clear retained spectrum data without changing widget configuration."""

        return self.set_magnitudes((), sample_rate=0, channels=0)

    def build_scene_node(self) -> SceneNode:
        root = SceneNode(
            key=self.key,
            kind=SceneNodeKind.RECTANGLE,
            bounds=self.bounds,
            opacity=self.opacity,
            z_index=self.z_index,
            fill=self._background,
            clip_to_bounds=True,
            hit_testable=False,
        )
        if self.bounds.width <= 0.0 or self.bounds.height <= 0.0 or not self._magnitudes:
            return root

        slot_width = self.bounds.width / len(self._magnitudes)
        bar_width = max(0.25, slot_width * 0.72)
        minimum_bar_height = min(0.5, self.bounds.height)
        for index, magnitude in enumerate(self._magnitudes):
            height = max(minimum_bar_height, magnitude * self.bounds.height)
            height = min(height, self.bounds.height)
            x = self.bounds.x + index * slot_width + (slot_width - bar_width) / 2.0
            y = self.bounds.bottom - height
            root.add(
                SceneNode(
                    key=f"{self.key}:bin:{index}",
                    kind=SceneNodeKind.RECTANGLE,
                    bounds=Rect(x, y, bar_width, height),
                    z_index=1,
                    fill=self._color,
                    hit_testable=False,
                )
            )
        return root

    def _set_pcm_source(
        self,
        pcm16: bytes,
        *,
        sample_rate: int,
        channels: int,
    ) -> SpectrumVisualizer:
        magnitudes = spectrum_magnitudes_pcm16(
            pcm16,
            channels=int(channels),
            bins=self._bin_count,
        )
        return self.set_magnitudes(
            magnitudes,
            sample_rate=int(sample_rate),
            channels=int(channels),
            smooth=True,
        )

    def _sync_accessibility(self) -> None:
        if not self._magnitudes:
            self.accessible_value_text = "No spectrum data"
            return
        peak_index = max(range(len(self._magnitudes)), key=self._magnitudes.__getitem__)
        peak = self._magnitudes[peak_index]
        if self._sample_rate > 0 and len(self._magnitudes) > 1:
            peak_hz = peak_index * (self._sample_rate / 2.0) / (len(self._magnitudes) - 1)
            peak_label = f", peak {peak_hz:.0f} Hz at {peak:.2f}"
        else:
            peak_label = f", peak {peak:.2f}"
        channel_label = "channel" if self._channels == 1 else "channels"
        self.accessible_value_text = (
            f"{len(self._magnitudes)} spectrum bins{peak_label}, "
            f"{self._channels} {channel_label}"
        )


def _native_module() -> Any:
    try:
        return importlib.import_module("_swirui_native")
    except ImportError as exc:
        raise RuntimeError(
            "SwirUI native spectrum core is not installed. Build/install native/ with Maturin."
        ) from exc


__all__ = ["SpectrumVisualizer", "spectrum_magnitudes_pcm16"]
