"""Core building blocks exposed by SwirUI."""

from .accessibility import AccessibilityNode, AccessibilityRole, build_accessibility_tree
from .binding import Binding, ReactiveProperty, bind, bind_bidirectional
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
from .state import ComputedState, State, computed, state_transaction

__all__ = [
    "AccessibilityNode",
    "AccessibilityRole",
    "AdaptiveQualityController",
    "AdaptiveQualityDecision",
    "AdaptiveQualityPolicy",
    "AdaptiveQualityStats",
    "AppConfig",
    "Binding",
    "Component",
    "ComputedState",
    "Event",
    "EventEmitter",
    "EventPhase",
    "PresentationMode",
    "ReactiveProperty",
    "State",
    "VisualQuality",
    "bind",
    "bind_bidirectional",
    "build_accessibility_tree",
    "computed",
    "configure_logging",
    "get_logger",
    "state_transaction",
]
