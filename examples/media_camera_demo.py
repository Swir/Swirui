"""Minimal CameraView example using the verified native camera source."""

from __future__ import annotations

from swirui import CameraView
from swirui.camera import NativeCameraCapture, camera_devices
from swirui.rendering import Rect


class DemoRenderer:
    def register_image_rgba(
        self,
        resource_id: str,
        width: int,
        height: int,
        rgba: bytes | bytearray | memoryview,
    ) -> None:
        print(f"registered {resource_id}: {width}x{height}, {len(rgba)} RGBA bytes")


def main() -> None:
    devices = camera_devices()
    if not devices:
        print("No Windows Media Foundation camera is available.")
        return

    capture = NativeCameraCapture(devices[0].index)
    view = CameraView(
        capture,
        DemoRenderer(),
        "demo:camera",
        bounds=Rect(0.0, 0.0, 640.0, 360.0),
        accessible_name="Camera preview",
    )
    try:
        view.refresh()
        print(f"captured from {devices[0].name}: {view.pixel_size[0]}x{view.pixel_size[1]}")
    finally:
        view.close()


if __name__ == "__main__":
    main()
