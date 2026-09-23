from __future__ import annotations

import sys
import types

import pytest

from swirui.camera import CameraDevice, NativeCameraCapture, camera_devices
from swirui.media import ImageFrame
from swirui.rendering import Rect
from swirui.widgets.camera_view import CameraView


class Renderer:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int, int, bytes]] = []

    def register_image_rgba(
        self,
        resource_id: str,
        width: int,
        height: int,
        rgba: bytes | bytearray | memoryview,
    ) -> None:
        self.calls.append((resource_id, width, height, bytes(rgba)))


class Source:
    def __init__(self) -> None:
        self.frame_number = 0
        self.closed = False

    def read_frame(self) -> ImageFrame:
        self.frame_number += 1
        red = min(self.frame_number * 20, 255)
        return ImageFrame(2, 1, bytes((red, 0, 0, 255)) * 2)

    def close(self) -> None:
        self.closed = True


class FakeCapture:
    def __init__(self, index: int) -> None:
        self.index = index
        self.closed = False

    def read_frame(self) -> tuple[int, int, bytes]:
        return 2, 1, bytes((20, 30, 40, 255)) * 2

    def close(self) -> None:
        self.closed = True


def fake_native() -> types.SimpleNamespace:
    def validate(width: int, height: int, rgba: bytes) -> tuple[int, int, int]:
        expected = width * height * 4
        if width <= 0 or height <= 0 or len(rgba) != expected:
            raise ValueError("invalid camera frame")
        return width, height, expected

    return types.SimpleNamespace(
        CameraCapture=FakeCapture,
        list_camera_devices=lambda: [(0, "Front Camera", "Media Foundation")],
        native_camera_capture_supported=lambda: True,
        validate_camera_rgba_frame=validate,
    )


def test_camera_view_is_exported_from_public_api() -> None:
    from swirui import CameraView as PublicCameraView

    assert PublicCameraView is CameraView


def test_camera_device_discovery_uses_native_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "_swirui_native", fake_native())

    assert camera_devices() == (CameraDevice(0, "Front Camera", "Media Foundation"),)


def test_native_capture_wraps_rgba_frames(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "_swirui_native", fake_native())
    capture = NativeCameraCapture(0)

    frame = capture.read_frame()
    assert frame.width == 2
    assert frame.height == 1
    assert frame.rgba == bytes((20, 30, 40, 255)) * 2

    capture.close()
    assert capture.closed is True
    with pytest.raises(RuntimeError, match="closed"):
        capture.read_frame()


def test_camera_view_refreshes_one_persistent_resource(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "_swirui_native", fake_native())
    source = Source()
    renderer = Renderer()
    view = CameraView(
        source,
        renderer,
        "demo:camera",
        bounds=Rect(0.0, 0.0, 320.0, 180.0),
        accessible_name="Camera preview",
    )

    assert renderer.calls[-1][3] == bytes((20, 0, 0, 255)) * 2
    view.refresh()
    assert renderer.calls[-1][3] == bytes((40, 0, 0, 255)) * 2

    view.pause().refresh()
    assert len(renderer.calls) == 2
    view.resume().refresh()
    assert len(renderer.calls) == 3

    view.close()
    assert source.closed is True
    assert view.closed is True
    with pytest.raises(RuntimeError, match="closed"):
        view.resume()


def test_camera_view_rejects_native_frame_safety_violation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    native = fake_native()
    native.validate_camera_rgba_frame = lambda width, height, rgba: (_ for _ in ()).throw(
        ValueError("camera frame exceeds safety limit")
    )
    monkeypatch.setitem(sys.modules, "_swirui_native", native)

    with pytest.raises(ValueError, match="safety limit"):
        CameraView(
            Source(),
            Renderer(),
            "demo:camera",
            bounds=Rect(0.0, 0.0, 100.0, 100.0),
        )
