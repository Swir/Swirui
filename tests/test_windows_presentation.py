import importlib
import sys

import pytest

from swirui.platforms import NativeWindowSpec
from swirui.platforms.windows import Win32PlatformBackend


@pytest.mark.skipif(sys.platform != "win32", reason="Native presentation smoke requires Windows")
def test_native_wgpu_presentation_policy_can_be_selected_and_reconfigured() -> None:
    native = importlib.import_module("_swirui_native")
    backend = Win32PlatformBackend()
    backend.initialize()
    handle = backend.create_window(NativeWindowSpec("SwirUI Presentation Smoke", 480, 320))
    backend.show_window(handle)
    backend.poll_events()

    try:
        renderer = native.Win32GpuRenderer(
            handle.value,
            480,
            320,
            "auto_no_vsync",
            2,
        )
        assert renderer.presentation_mode == "auto_no_vsync"
        assert renderer.maximum_frame_latency == 2
        renderer.clear()

        renderer.configure_presentation("auto_vsync", 1)
        assert renderer.presentation_mode == "auto_vsync"
        assert renderer.maximum_frame_latency == 1
        renderer.clear()

        with pytest.raises(ValueError, match="presentation_mode"):
            renderer.configure_presentation("immediate", 1)
        with pytest.raises(ValueError, match="maximum_frame_latency"):
            renderer.configure_presentation("auto_vsync", 0)
    finally:
        backend.destroy_window(handle)
        backend.shutdown()
