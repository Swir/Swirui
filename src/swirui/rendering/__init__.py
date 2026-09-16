"""Rendering contracts and backend-neutral primitives."""

from .base import NullRenderer, Renderer
from .geometry import Color, CornerRadius, Point, Rect, Size
from .scene import Scene, SceneNode, SceneNodeKind
from .scheduler import FrameScheduler, FrameStats
from .surface import RenderSurface
from .tree import RenderNode, RenderTree
from .windows_gdi import Win32PreviewRenderer

__all__ = [
    "Color",
    "CornerRadius",
    "FrameScheduler",
    "FrameStats",
    "NullRenderer",
    "Point",
    "Rect",
    "RenderNode",
    "Renderer",
    "RenderSurface",
    "RenderTree",
    "Scene",
    "SceneNode",
    "SceneNodeKind",
    "Size",
    "Win32PreviewRenderer",
]
