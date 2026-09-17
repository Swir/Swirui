"""Public wgpu renderer with bounded custom-shader post-processing."""

from __future__ import annotations

from typing import Any

from swirui.core import Component, PresentationMode
from swirui.window import Window

from .backdrop_wgpu_renderer import WgpuRenderer as _BackdropWgpuRenderer
from .custom_shaders import CustomShaderEffect
from .geometry import Color
from .surface import RenderSurface


class WgpuRenderer(_BackdropWgpuRenderer):
    """Persistent SwirUI GPU renderer with optional validated custom WGSL effects.

    Custom shaders run as the final retained GPU post-process after scene blur and
    the optional affine color filter. The Rust core keeps the full-size output
    target, bind group, parameter buffer and compiled render pipeline alive for
    the window. Updating only the four effect parameters therefore writes one
    small uniform buffer instead of recompiling the shader pipeline.
    """

    def __init__(
        self,
        *,
        background: Color | None = None,
        native_module: Any | None = None,
        presentation_mode: PresentationMode = PresentationMode.AUTO_VSYNC,
        maximum_frame_latency: int = 1,
        scene_blur_radius: float = 0.0,
        color_filter: Any | None = None,
        custom_shader: CustomShaderEffect | None = None,
    ) -> None:
        super().__init__(
            background=background,
            native_module=native_module,
            presentation_mode=presentation_mode,
            maximum_frame_latency=maximum_frame_latency,
            scene_blur_radius=scene_blur_radius,
            color_filter=color_filter,
        )
        self.custom_shader = custom_shader

    def set_custom_shader(self, custom_shader: CustomShaderEffect | None) -> None:
        """Atomically update the custom post-process on all live GPU contexts."""

        if custom_shader is not None and self._native is not None:
            custom_shader.validate_native(self._native)

        previous = self.custom_shader
        configured: list[Any] = []
        try:
            for context in self._contexts.values():
                self._configure_custom_shader(context, custom_shader)
                configured.append(context)
        except Exception:
            for context in configured:
                try:
                    self._configure_custom_shader(context, previous)
                except Exception:
                    pass
            raise
        self.custom_shader = custom_shader

    def create_surface(self, window: Window) -> RenderSurface:
        surface = super().create_surface(window)
        if window.native_handle is None:
            return surface
        context = self._contexts.get(window.native_handle.value)
        if context is None or self.custom_shader is None:
            return surface
        try:
            self._configure_custom_shader(context, self.custom_shader)
        except Exception:
            super().destroy_surface(window)
            raise
        return surface

    def render(self, window: Window, root: Component | None) -> None:
        if self.custom_shader is not None and window.native_handle is not None:
            if window.native_handle.value not in self._contexts:
                raise RuntimeError(
                    "Custom shader effects require the persistent SwirUI native GPU context."
                )
        super().render(window, root)

    @staticmethod
    def _configure_custom_shader(
        context: Any,
        custom_shader: CustomShaderEffect | None,
    ) -> None:
        if custom_shader is None:
            clear = getattr(context, "clear_custom_shader", None)
            if clear is not None:
                clear()
            return

        configure = getattr(context, "set_custom_shader", None)
        if configure is None:
            raise RuntimeError(
                "Installed SwirUI native GPU core does not support custom shader effects."
            )
        configure(
            custom_shader.native_wgsl(),
            list(custom_shader.native_parameters()),
        )
