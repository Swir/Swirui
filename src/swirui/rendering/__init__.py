"""Rendering contracts and backend-neutral primitives."""

from .base import NullRenderer, Renderer
from .factory import create_renderer
from .geometry import Color, CornerRadius, Point, Rect, Size
from .scene import ImageResource, Scene, SceneNode, SceneNodeKind
from .scheduler import FrameScheduler, FrameStats
from .surface import RenderSurface
from .tree import RenderNode, RenderTree
from .wgpu_renderer import WgpuRenderer
from .windows_gdi import Win32PreviewRenderer

__all__ = [
    "Color",
    "CornerRadius",
    "FrameScheduler",
    "FrameStats",
    "ImageResource",
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
    "WgpuRenderer",
    "Win32PreviewRenderer",
    "create_renderer",
]
