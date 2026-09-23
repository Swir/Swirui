from __future__ import annotations

import sys

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows native microphone gate")


def test_windows_native_microphone_backend_is_compiled() -> None:
    import _swirui_native as native

    assert native.native_microphone_input_supported() is True
    assert hasattr(native, "MicrophoneCapture")
    assert callable(native.list_microphone_devices)
    assert callable(native.validate_microphone_pcm16)
