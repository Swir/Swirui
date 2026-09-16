"""Core building blocks exposed by SwirUI."""

from .component import Component
from .config import AppConfig, PresentationMode, VisualQuality
from .events import Event, EventEmitter, EventPhase
from .logging import configure_logging, get_logger
from .state import State

__all__ = [
    "AppConfig",
    "Component",
    "Event",
    "EventEmitter",
    "EventPhase",
    "PresentationMode",
    "State",
    "VisualQuality",
    "configure_logging",
    "get_logger",
]
