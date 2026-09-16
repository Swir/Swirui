import sys

import pytest

from swirui.platforms import NativeWindowSpec
from swirui.platforms.windows import Win32PlatformBackend


@pytest.mark.skipif(sys.platform != "win32", reason="Win32 smoke test requires Windows")
def test_win32_backend_creates_real_native_window() -> None:
    backend = Win32PlatformBackend()
    backend.initialize()

    displays = backend.displays()
    assert displays
    assert displays[0].width > 0
    assert displays[0].height > 0

    handle = backend.create_window(NativeWindowSpec("SwirUI CI Native Smoke", 640, 420))
    assert handle.value > 0

    backend.set_window_title(handle, "SwirUI CI Native Smoke Updated")
    backend.resize_window(handle, 700, 460)
    backend.poll_events()
    backend.destroy_window(handle)
    backend.shutdown()
