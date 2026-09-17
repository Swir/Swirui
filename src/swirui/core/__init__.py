"""Core building blocks exposed by SwirUI."""

from .accessibility import AccessibilityNode, AccessibilityRole, build_accessibility_tree
from .component import Component
from .config import AppConfig, PresentationMode, VisualQuality
from .events import Event, EventEmitter, EventPhase
from .logging import configure_logging, get_logger
from .quality import (
    AdaptiveQualityController,
    AdaptiveQualityDecision,
    AdaptiveQualityPolicy,
    AdaptiveQualityStats,
)
from .state import State

__all__ = [
    "AccessibilityNode",
    "AccessibilityRole",
    "AdaptiveQualityController",
    "AdaptiveQualityDecision",
    "AdaptiveQualityPolicy",
    "AdaptiveQualityStats",
    "AppConfig",
    "Component",
    "Event",
    "EventEmitter",
    "EventPhase",
    "PresentationMode",
    "State",
    "VisualQuality",
    "build_accessibility_tree",
    "configure_logging",
    "get_logger",
]
