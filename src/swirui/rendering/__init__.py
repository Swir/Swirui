"""Rendering contracts and backend-neutral primitives."""

from .base import NullRenderer, Renderer
from .geometry import Color, CornerRadius, Point, Rect, Size
from .scene import Scene, SceneNode, SceneNodeKind
from .scheduler import FrameScheduler, FrameStats
from .tree import RenderNode, RenderTree

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
    "RenderTree",
    "Scene",
    "SceneNode",
    "SceneNodeKind",
    "Size",
]
