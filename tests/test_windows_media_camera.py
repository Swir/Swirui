from __future__ import annotations

import sys

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows native camera gate")


def test_windows_native_camera_backend_is_compiled() -> None:
    import _swirui_native as native

    assert native.native_camera_capture_supported() is True
    assert hasattr(native, "CameraCapture")
    assert callable(native.list_camera_devices)
    assert callable(native.validate_camera_rgba_frame)
