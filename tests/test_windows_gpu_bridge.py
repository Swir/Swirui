import importlib
import sys

import pytest

from swirui.platforms import NativeWindowSpec
from swirui.platforms.windows import Win32PlatformBackend


@pytest.mark.skipif(sys.platform != "win32", reason="Native GPU bridge test requires Windows")
def test_wgpu_core_clears_and_draws_real_win32_surface() -> None:
    native = importlib.import_module("_swirui_native")
    backend = Win32PlatformBackend()
    backend.initialize()
    handle = backend.create_window(NativeWindowSpec("SwirUI wgpu CI Smoke", 640, 420))
    backend.show_window(handle)
    backend.poll_events()

    try:
        adapter_name, graphics_backend = native.clear_win32_surface(
            handle.value,
            640,
            420,
            0.027,
            0.043,
            0.078,
            1.0,
        )
        assert adapter_name
        assert graphics_backend

        adapter_name, graphics_backend, rectangle_count = native.draw_rectangles_win32_surface(
            handle.value,
            640,
            420,
            [
                (32.0, 36.0, 260.0, 120.0, 0.0, 0.55, 1.0, 1.0),
                (330.0, 80.0, 180.0, 220.0, 0.10, 0.18, 0.34, 0.92),
                (96.0, 230.0, 380.0, 96.0, 0.42, 0.18, 1.0, 0.82),
            ],
            0.027,
            0.043,
            0.078,
            1.0,
        )
        assert adapter_name
        assert graphics_backend
        assert rectangle_count == 3
    finally:
        backend.destroy_window(handle)
        backend.shutdown()
