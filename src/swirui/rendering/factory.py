"""Automatic renderer selection for SwirUI applications."""

from __future__ import annotations

import importlib
import sys

from .base import NullRenderer, Renderer
from .wgpu_renderer import WgpuRenderer
from .windows_gdi import Win32PreviewRenderer


def create_renderer() -> Renderer:
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
    return WgpuRenderer(native_module=native)
