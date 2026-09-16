"""Temporary Win32 GDI bring-up renderer for validating visible scene submission.

This backend is intentionally a development bridge, not the long-term SwirUI renderer.
The final renderer is GPU-first. Keeping this renderer behind the common Renderer contract lets
us validate scene construction, invalidation and native-window presentation before the wgpu core
is fully connected.
"""

from __future__ import annotations

import ctypes
import sys
from typing import Any

from swirui.core import Component
from swirui.window import Window

from .geometry import Color, CornerRadius, Rect
from .scene import SceneNode, SceneNodeKind
from .surface import RenderSurface

_TRANSPARENT = 1
_DEFAULT_CHARSET = 1
_OUT_DEFAULT_PRECIS = 0
_CLIP_DEFAULT_PRECIS = 0
_CLEARTYPE_QUALITY = 5
_DEFAULT_PITCH = 0


class _WinRect(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


class Win32PreviewRenderer:
    """Visible scene renderer used only while the GPU backend is being brought online."""

    name = "win32-gdi-preview"

    def __init__(self, *, clear_color: Color | None = None) -> None:
        self.clear_color = clear_color or Color.from_hex("#070B14")
        self.initialized = False
        self.frames_rendered = 0
        self.surfaces: dict[int, RenderSurface] = {}
        self._user32: Any = None
        self._gdi32: Any = None

    def initialize(self) -> None:
        if self.initialized:
            return
        if sys.platform != "win32":
            raise RuntimeError("Win32PreviewRenderer can only run on Windows.")

        win_dll: Any = ctypes.__dict__["WinDLL"]
        self._user32 = win_dll("user32", use_last_error=True)
        self._gdi32 = win_dll("gdi32", use_last_error=True)
        self._configure_signatures()
        self.initialized = True

    def create_surface(self, window: Window) -> RenderSurface:
        self._require_initialized()
        if window.native_handle is None:
            raise RuntimeError("A native window handle is required before creating a surface.")
        surface = RenderSurface(window.native_handle, window.width, window.height)
        self.surfaces[window.native_handle.value] = surface
        return surface

    def resize_surface(self, window: Window, width: int, height: int) -> None:
        self._surface_for(window).resize(width, height)

    def destroy_surface(self, window: Window) -> None:
        if window.native_handle is None:
            return
        surface = self.surfaces.pop(window.native_handle.value, None)
        if surface is not None:
            surface.destroy()

    def render(self, window: Window, root: Component | None) -> None:
        """Paint the attached scene into the HWND using the temporary GDI bridge."""

        del root
        self._require_initialized()
        if window.native_handle is None:
            raise RuntimeError("Window is not bound to a native handle.")
        self._surface_for(window)

        hwnd = ctypes.c_void_p(window.native_handle.value)
        hdc = self._user32.GetDC(hwnd)
        if not hdc:
            raise OSError(ctypes.get_last_error(), "GetDC failed for SwirUI preview renderer.")

        try:
            client = _WinRect()
            if not self._user32.GetClientRect(hwnd, ctypes.byref(client)):
                raise OSError(
                    ctypes.get_last_error(),
                    "GetClientRect failed for SwirUI preview renderer.",
                )
            self._fill_native_rect(hdc, client, self.clear_color)

            scene = window.scene
            if scene is not None:
                for node in scene.walk():
                    self._paint_node(hdc, node)
            self.frames_rendered += 1
        finally:
            self._user32.ReleaseDC(hwnd, hdc)

    def shutdown(self) -> None:
        for surface in self.surfaces.values():
            surface.destroy()
        self.surfaces.clear()
        self.initialized = False
        self._user32 = None
        self._gdi32 = None

    def _paint_node(self, hdc: Any, node: SceneNode) -> None:
        if node.opacity <= 0.0:
            return
        if node.kind in (SceneNodeKind.GROUP, SceneNodeKind.RECTANGLE):
            if node.fill is not None:
                self._fill_rect(hdc, node.bounds, node.fill, node.corner_radius)
            return
        if node.kind is SceneNodeKind.TEXT and node.text is not None:
            self._draw_text(hdc, node)

    def _fill_rect(
        self,
        hdc: Any,
        rect: Rect,
        color: Color,
        radius: CornerRadius,
    ) -> None:
        native = self._to_native_rect(rect)
        maximum_radius = max(
            radius.top_left,
            radius.top_right,
            radius.bottom_right,
            radius.bottom_left,
        )
        brush = self._gdi32.CreateSolidBrush(self._colorref(color))
        if not brush:
            raise OSError(ctypes.get_last_error(), "CreateSolidBrush failed.")
        try:
            if maximum_radius <= 0.0:
                self._user32.FillRect(hdc, ctypes.byref(native), brush)
                return
            diameter = max(1, int(round(maximum_radius * 2.0)))
            region = self._gdi32.CreateRoundRectRgn(
                native.left,
                native.top,
                native.right + 1,
                native.bottom + 1,
                diameter,
                diameter,
            )
            if not region:
                raise OSError(ctypes.get_last_error(), "CreateRoundRectRgn failed.")
            try:
                self._gdi32.FillRgn(hdc, region, brush)
            finally:
                self._gdi32.DeleteObject(region)
        finally:
            self._gdi32.DeleteObject(brush)

    def _fill_native_rect(self, hdc: Any, rect: _WinRect, color: Color) -> None:
        brush = self._gdi32.CreateSolidBrush(self._colorref(color))
        if not brush:
            raise OSError(ctypes.get_last_error(), "CreateSolidBrush failed.")
        try:
            self._user32.FillRect(hdc, ctypes.byref(rect), brush)
        finally:
            self._gdi32.DeleteObject(brush)

    def _draw_text(self, hdc: Any, node: SceneNode) -> None:
        color = node.fill or Color(1.0, 1.0, 1.0, 1.0)
        height = -max(1, int(round(node.font_size)))
        font = self._gdi32.CreateFontW(
            height,
            0,
            0,
            0,
            500,
            False,
            False,
            False,
            _DEFAULT_CHARSET,
            _OUT_DEFAULT_PRECIS,
            _CLIP_DEFAULT_PRECIS,
            _CLEARTYPE_QUALITY,
            _DEFAULT_PITCH,
            node.font_family,
        )
        if not font:
            raise OSError(ctypes.get_last_error(), "CreateFontW failed.")

        previous_font = self._gdi32.SelectObject(hdc, font)
        try:
            self._gdi32.SetBkMode(hdc, _TRANSPARENT)
            self._gdi32.SetTextColor(hdc, self._colorref(color))
            x = int(round(node.bounds.x))
            y = int(round(node.bounds.y))
            self._gdi32.TextOutW(hdc, x, y, node.text, len(node.text))
        finally:
            if previous_font:
                self._gdi32.SelectObject(hdc, previous_font)
            self._gdi32.DeleteObject(font)

    def _surface_for(self, window: Window) -> RenderSurface:
        self._require_initialized()
        if window.native_handle is None:
            raise RuntimeError("Window is not bound to a native handle.")
        try:
            return self.surfaces[window.native_handle.value]
        except KeyError as exc:
            raise RuntimeError("Window does not have an attached render surface.") from exc

    def _configure_signatures(self) -> None:
        self._user32.GetDC.argtypes = [ctypes.c_void_p]
        self._user32.GetDC.restype = ctypes.c_void_p
        self._user32.ReleaseDC.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        self._user32.ReleaseDC.restype = ctypes.c_int
        self._user32.GetClientRect.argtypes = [ctypes.c_void_p, ctypes.POINTER(_WinRect)]
        self._user32.GetClientRect.restype = ctypes.c_bool
        self._user32.FillRect.argtypes = [ctypes.c_void_p, ctypes.POINTER(_WinRect), ctypes.c_void_p]
        self._user32.FillRect.restype = ctypes.c_int

        self._gdi32.CreateSolidBrush.argtypes = [ctypes.c_uint32]
        self._gdi32.CreateSolidBrush.restype = ctypes.c_void_p
        self._gdi32.DeleteObject.argtypes = [ctypes.c_void_p]
        self._gdi32.DeleteObject.restype = ctypes.c_bool
        self._gdi32.CreateRoundRectRgn.argtypes = [
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
        ]
        self._gdi32.CreateRoundRectRgn.restype = ctypes.c_void_p
        self._gdi32.FillRgn.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
        self._gdi32.FillRgn.restype = ctypes.c_bool
        self._gdi32.SetBkMode.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self._gdi32.SetBkMode.restype = ctypes.c_int
        self._gdi32.SetTextColor.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        self._gdi32.SetTextColor.restype = ctypes.c_uint32
        self._gdi32.SelectObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        self._gdi32.SelectObject.restype = ctypes.c_void_p
        self._gdi32.TextOutW.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_wchar_p,
            ctypes.c_int,
        ]
        self._gdi32.TextOutW.restype = ctypes.c_bool
        self._gdi32.CreateFontW.argtypes = [
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.c_wchar_p,
        ]
        self._gdi32.CreateFontW.restype = ctypes.c_void_p

    @staticmethod
    def _to_native_rect(rect: Rect) -> _WinRect:
        return _WinRect(
            int(round(rect.x)),
            int(round(rect.y)),
            int(round(rect.right)),
            int(round(rect.bottom)),
        )

    @staticmethod
    def _colorref(color: Color) -> int:
        red = int(round(color.r * 255.0))
        green = int(round(color.g * 255.0))
        blue = int(round(color.b * 255.0))
        return red | (green << 8) | (blue << 16)

    def _require_initialized(self) -> None:
        if not self.initialized:
            raise RuntimeError("Renderer must be initialized before use.")
