"""Rendering contracts and backend-neutral primitives."""

from .backdrop import BackdropBlur
from .base import NullRenderer, Renderer
from .bloom import Bloom
from .effects import (
    DropShadow,
    DynamicShadow,
    EffectQualityProfile,
    Glow,
    effect_quality_profile,
)
from .factory import create_renderer
from .geometry import Color, CornerRadius, Path2D, Point, Rect, Size
from .gradients import GradientStop, LinearGradient, MeshGradient, RadialGradient
from .scene import Scene, SceneNode, SceneNodeKind
from .scheduler import FrameScheduler, FrameStats
from .surface import RenderSurface
from .tree import RenderNode, RenderTree
from .wgpu_renderer import WgpuRenderer
from .windows_gdi import Win32PreviewRenderer

__all__ = [
    "BackdropBlur",
    "Bloom",
    "Color",
    "CornerRadius",
    "DropShadow",
    "DynamicShadow",
    "EffectQualityProfile",
    "FrameScheduler",
    "FrameStats",
    "Glow",
    "GradientStop",
    "LinearGradient",
    "MeshGradient",
    "NullRenderer",
    "Path2D",
    "Point",
    "RadialGradient",
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
    "effect_quality_profile",
]
