"""Public package API for SwirUI."""

from .app import App
from .core import (
    AccessibilityNode,
    AccessibilityRole,
    AdaptiveQualityController,
    AdaptiveQualityDecision,
    AdaptiveQualityPolicy,
    AdaptiveQualityStats,
    AppConfig,
    Component,
    PresentationMode,
    State,
    VisualQuality,
    build_accessibility_tree,
)
from .widgets import Button, IconButton, Label, Text, Widget, WidgetRuntime, mount
from .window import Window

__all__ = [
    "AccessibilityNode",
    "AccessibilityRole",
    "AdaptiveQualityController",
    "AdaptiveQualityDecision",
    "AdaptiveQualityPolicy",
    "AdaptiveQualityStats",
    "App",
    "AppConfig",
    "Button",
    "Component",
    "IconButton",
    "Label",
    "PresentationMode",
    "State",
    "Text",
    "VisualQuality",
    "Widget",
    "WidgetRuntime",
    "Window",
    "build_accessibility_tree",
    "mount",
]
__version__ = "0.1.0a1"
