"""Core building blocks exposed by SwirUI."""

from .accessibility import AccessibilityNode, AccessibilityRole, build_accessibility_tree
from .async_state import AsyncSnapshot, AsyncState, AsyncStatus
from .binding import Binding, ReactiveProperty, bind, bind_bidirectional
from .collections import ObservableDict, ObservableList
from .component import Component
from .config import AppConfig, PresentationMode, VisualQuality
from .events import Event, EventEmitter, EventPhase
from .logging import configure_logging, get_logger
from .persistent_state import PersistentState
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
    "AsyncSnapshot",
    "AsyncState",
    "AsyncStatus",
    "Binding",
    "Component",
    "ComputedState",
    "Event",
    "EventEmitter",
    "EventPhase",
    "ObservableDict",
    "ObservableList",
    "PersistentState",
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
