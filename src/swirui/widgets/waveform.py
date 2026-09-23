"""Retained PCM waveform visualization backed by native Rust envelope reduction."""

from __future__ import annotations

import importlib
import math
from dataclasses import dataclass
from typing import Any

from swirui.audio import AudioClip
from swirui.core import AccessibilityRole
from swirui.microphone import MicrophoneChunk
from swirui.rendering.geometry import Color, Rect
from swirui.rendering.scene import SceneNode, SceneNodeKind

from .base import Widget

_BACKGROUND = Color.from_hex("#101920")
_CENTER_LINE = Color.from_hex("#35505F")
_WAVEFORM = Color.from_hex("#0A98F0")
_MAX_BUCKETS = 4_096


@dataclass(frozen=True, slots=True)
class WaveformEnvelope:
    """One normalized min/max amplitude bucket in the range [-1, 1]."""

    minimum: float
    maximum: float

    def __post_init__(self) -> None:
        minimum = float(self.minimum)
        maximum = float(self.maximum)
        if not math.isfinite(minimum) or not math.isfinite(maximum):
            raise ValueError("Waveform amplitudes must be finite.")
        if minimum < -1.0 or maximum > 1.0 or minimum > maximum:
            raise ValueError("Waveform amplitudes must satisfy -1 <= minimum <= maximum <= 1.")
        object.__setattr__(self, "minimum", minimum)
        object.__setattr__(self, "maximum", maximum)


def waveform_envelope_pcm16(
    pcm16: bytes,
    *,
    channels: int,
    buckets: int = 256,
) -> tuple[WaveformEnvelope, ...]:
    """Reduce interleaved signed PCM16 into a bounded native min/max envelope."""

    channel_count = int(channels)
    bucket_count = int(buckets)
    if not 1 <= channel_count <= 8:
        raise ValueError("channels must be in the range [1, 8].")
    if not 1 <= bucket_count <= _MAX_BUCKETS:
        raise ValueError(f"buckets must be in the range [1, {_MAX_BUCKETS}].")
    payload = bytes(pcm16)
    raw = _native_module().waveform_envelope_pcm16(channel_count, payload, bucket_count)
    return tuple(
        WaveformEnvelope(float(minimum), float(maximum)) for minimum, maximum in raw
    )


class Waveform(Widget):
    """GPU-retained waveform bars driven by native PCM16 envelope extraction.

    Python owns the public source/update API while Rust reduces potentially large
    PCM buffers into a bounded envelope. The retained rectangle scene is then
    submitted through SwirUI's existing HiDPI-aware wgpu renderer.
    """

    def __init__(
        self,
        *,
        bounds: Rect,
        buckets: int = 256,
        color: Color = _WAVEFORM,
        background: Color = _BACKGROUND,
        key: str | None = None,
        opacity: float = 1.0,
        z_index: int = 0,
        accessible_name: str | None = None,
        accessible_description: str | None = None,
    ) -> None:
        bucket_count = int(buckets)
        if not 1 <= bucket_count <= _MAX_BUCKETS:
            raise ValueError(f"buckets must be in the range [1, {_MAX_BUCKETS}].")
        self._bucket_count = bucket_count
        self._color = color
        self._background = background
        self._envelope: tuple[WaveformEnvelope, ...] = ()
        self._duration_ms = 0.0
        self._channels = 0
        super().__init__(
            bounds=bounds,
            key=key,
            opacity=opacity,
            z_index=z_index,
            clip_to_bounds=True,
            focusable=False,
            accessibility_role=AccessibilityRole.IMAGE,
            accessible_name=accessible_name or "Audio waveform",
            accessible_description=accessible_description,
        )
        self._sync_accessibility()

    @property
    def bucket_count(self) -> int:
        return self._bucket_count

    @property
    def envelope(self) -> tuple[WaveformEnvelope, ...]:
        return self._envelope

    @property
    def duration_ms(self) -> float:
        return self._duration_ms

    @property
    def channels(self) -> int:
        return self._channels

    def set_audio_clip(self, clip: AudioClip) -> Waveform:
        """Replace the displayed envelope from a validated :class:`AudioClip`."""

        return self._set_pcm_source(
            clip.pcm16,
            channels=clip.channels,
            duration_ms=clip.duration_ms,
        )

    def set_microphone_chunk(self, chunk: MicrophoneChunk) -> Waveform:
        """Replace the displayed envelope from one captured microphone chunk."""

        return self._set_pcm_source(
            chunk.pcm16,
            channels=chunk.channels,
            duration_ms=chunk.duration_ms,
        )

    def set_envelope(
        self,
        envelope: tuple[WaveformEnvelope, ...] | list[WaveformEnvelope],
        *,
        duration_ms: float = 0.0,
        channels: int = 0,
    ) -> Waveform:
        """Set precomputed normalized buckets for custom/streaming pipelines."""

        normalized = tuple(envelope)
        if len(normalized) > _MAX_BUCKETS:
            raise ValueError(f"Waveform envelope cannot exceed {_MAX_BUCKETS} buckets.")
        if not math.isfinite(duration_ms) or duration_ms < 0.0:
            raise ValueError("duration_ms must be finite and non-negative.")
        if channels < 0 or channels > 8:
            raise ValueError("channels must be in the range [0, 8].")
        if (
            normalized == self._envelope
            and duration_ms == self._duration_ms
            and channels == self._channels
        ):
            return self
        self._envelope = normalized
        self._duration_ms = float(duration_ms)
        self._channels = int(channels)
        self._sync_accessibility()
        self.invalidate(reason="waveform_data")
        return self

    def clear(self) -> None:
        self.set_envelope((), duration_ms=0.0, channels=0)

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
        if self.bounds.width <= 0.0 or self.bounds.height <= 0.0:
            return root

        center_y = self.bounds.y + self.bounds.height / 2.0
        center_height = min(1.0, self.bounds.height)
        root.add(
            SceneNode(
                key=f"{self.key}:center",
                kind=SceneNodeKind.RECTANGLE,
                bounds=Rect(
                    self.bounds.x,
                    center_y - center_height / 2.0,
                    self.bounds.width,
                    center_height,
                ),
                z_index=0,
                fill=_CENTER_LINE,
                hit_testable=False,
            )
        )
        if not self._envelope:
            return root

        slot_width = self.bounds.width / len(self._envelope)
        bar_width = max(0.25, slot_width * 0.72)
        half_height = self.bounds.height / 2.0
        minimum_bar_height = min(0.5, self.bounds.height)
        for index, bucket in enumerate(self._envelope):
            top = center_y - bucket.maximum * half_height
            bottom = center_y - bucket.minimum * half_height
            height = max(0.0, bottom - top)
            if height < minimum_bar_height:
                midpoint = (top + bottom) / 2.0
                height = minimum_bar_height
                top = midpoint - height / 2.0
            top = max(self.bounds.y, min(top, self.bounds.bottom - height))
            x = self.bounds.x + index * slot_width + (slot_width - bar_width) / 2.0
            root.add(
                SceneNode(
                    key=f"{self.key}:bucket:{index}",
                    kind=SceneNodeKind.RECTANGLE,
                    bounds=Rect(x, top, bar_width, height),
                    z_index=1,
                    fill=self._color,
                    hit_testable=False,
                )
            )
        return root

    def _set_pcm_source(self, pcm16: bytes, *, channels: int, duration_ms: float) -> Waveform:
        envelope = waveform_envelope_pcm16(
            pcm16,
            channels=int(channels),
            buckets=self._bucket_count,
        )
        return self.set_envelope(
            envelope,
            duration_ms=float(duration_ms),
            channels=int(channels),
        )

    def _sync_accessibility(self) -> None:
        if not self._envelope:
            self.accessible_value_text = "No waveform data"
            return
        channel_label = "channel" if self._channels == 1 else "channels"
        self.accessible_value_text = (
            f"{len(self._envelope)} waveform buckets, {self._duration_ms:.1f} ms, "
            f"{self._channels} {channel_label}"
        )


def _native_module() -> Any:
    try:
        return importlib.import_module("_swirui_native")
    except ImportError as exc:
        raise RuntimeError(
            "SwirUI native waveform core is not installed. Build/install native/ with Maturin."
        ) from exc


__all__ = ["Waveform", "WaveformEnvelope", "waveform_envelope_pcm16"]
