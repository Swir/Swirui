"""Rendering contracts and backend-neutral primitives."""

from .backdrop import BackdropBlur
from .backdrop_wgpu_renderer import WgpuRenderer
from .base import NullRenderer, Renderer
from .bloom import Bloom
from .depth import Parallax, PerspectivePlane
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
from .lighting import AdaptiveLighting
from .materials import Acrylic, FrostedGlass
from .noise import Noise
from .reflections import Reflection
from .scene import Scene, SceneNode, SceneNodeKind
from .scheduler import FrameScheduler, FrameStats
from .surface import RenderSurface
from .tree import RenderNode, RenderTree
from .windows_gdi import Win32PreviewRenderer

__all__ = [
    "Acrylic",
    "AdaptiveLighting",
    "BackdropBlur",
    "Bloom",
    "Color",
    "CornerRadius",
    "DropShadow",
    "DynamicShadow",
    "EffectQualityProfile",
    "FrameScheduler",
    "FrameStats",
    "FrostedGlass",
    "Glow",
    "GradientStop",
    "LinearGradient",
    "MeshGradient",
    "Noise",
    "NullRenderer",
    "Parallax",
    "Path2D",
    "PerspectivePlane",
    "Point",
    "RadialGradient",
    "Rect",
    "Reflection",
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
