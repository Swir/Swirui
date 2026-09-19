"""Automatic renderer selection for SwirUI applications."""

from __future__ import annotations

import importlib
import sys

from swirui.core import AppConfig

from .affine_text_wgpu_renderer import WgpuRenderer
from .base import NullRenderer, Renderer
from .windows_gdi import Win32PreviewRenderer


def create_renderer(config: AppConfig | None = None) -> Renderer:
    """Return the best renderer currently available for this platform.

    Windows prefers the Rust/wgpu backend whenever the native extension is
    installed. During bring-up, the temporary GDI renderer remains a visible
    fallback. Unsupported native platforms stay headless until their native
    backends land.
    """

    if sys.platform != "win32":
        return NullRenderer()

    try:
        native = importlib.import_module("_swirui_native")
    except ImportError:
        return Win32PreviewRenderer()

    runtime = config or AppConfig()
    return WgpuRenderer(
        native_module=native,
        presentation_mode=runtime.presentation_mode,
        maximum_frame_latency=runtime.maximum_frame_latency,
    )
