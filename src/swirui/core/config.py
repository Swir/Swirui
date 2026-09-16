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


@dataclass(slots=True)
class AppConfig:
    """Runtime configuration shared by SwirUI subsystems."""

    visual_quality: VisualQuality = VisualQuality.AUTO
    debug: bool = False
    target_fps: int = 60

    def __post_init__(self) -> None:
        if self.target_fps <= 0:
            raise ValueError("target_fps must be positive.")
