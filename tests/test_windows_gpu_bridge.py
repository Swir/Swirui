import importlib
import sys

import pytest

from swirui.platforms import NativeWindowSpec
from swirui.platforms.windows import Win32PlatformBackend


@pytest.mark.skipif(sys.platform != "win32", reason="Native GPU bridge test requires Windows")
def test_wgpu_core_clears_real_win32_surface() -> None:
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
    finally:
        backend.destroy_window(handle)
        backend.shutdown()
