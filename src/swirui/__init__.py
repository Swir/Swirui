"""Public package API for SwirUI."""

from .app import App
from .core import (
    AccessibilityNode,
    AccessibilityRole,
    AppConfig,
    Component,
    PresentationMode,
    State,
    VisualQuality,
    build_accessibility_tree,
)
from .window import Window

__all__ = [
    "AccessibilityNode",
    "AccessibilityRole",
    "App",
    "AppConfig",
    "Component",
    "PresentationMode",
    "State",
    "VisualQuality",
    "Window",
    "build_accessibility_tree",
]
__version__ = "0.1.0a1"
