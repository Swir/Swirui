"""Public package API for SwirUI."""

from .app import App
from .core import AppConfig, Component, PresentationMode, State, VisualQuality
from .window import Window

__all__ = [
    "App",
    "AppConfig",
    "Component",
    "PresentationMode",
    "State",
    "VisualQuality",
    "Window",
]
__version__ = "0.1.0a1"
