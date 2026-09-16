"""Framework configuration primitives."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class VisualQuality(StrEnum):
    AUTO = "auto"
    PERFORMANCE = "performance"
    BALANCED = "balanced"
    QUALITY = "quality"
    ULTRA = "ultra"
    CINEMATIC = "cinematic"


class PresentationMode(StrEnum):
    """Portable presentation policies supported by the native GPU renderer."""

    AUTO_VSYNC = "auto_vsync"
    AUTO_NO_VSYNC = "auto_no_vsync"


@dataclass(slots=True)
class AppConfig:
    """Runtime configuration shared by SwirUI subsystems."""

    visual_quality: VisualQuality = VisualQuality.AUTO
    debug: bool = False
    target_fps: int = 60
    presentation_mode: PresentationMode = PresentationMode.AUTO_VSYNC
    maximum_frame_latency: int = 1

    def __post_init__(self) -> None:
        if self.target_fps <= 0:
            raise ValueError("target_fps must be positive.")
        if self.maximum_frame_latency <= 0:
            raise ValueError("maximum_frame_latency must be positive.")
