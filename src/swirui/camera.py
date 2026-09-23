"""Python-first camera capture primitives backed by SwirUI's native Rust core."""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Any, Protocol

from .media import ImageFrame


@dataclass(frozen=True, slots=True)
class CameraDevice:
    """One camera exposed by the verified native backend."""

    index: int
    name: str
    description: str = ""


class CameraSource(Protocol):
    """Minimal live-frame contract consumed by CameraView."""

    def read_frame(self) -> ImageFrame: ...

    def close(self) -> None: ...


class NativeCameraCapture:
    """Windows Media Foundation capture session owned by the native Rust core."""

    def __init__(self, index: int = 0) -> None:
        if index < 0:
            raise ValueError("Camera index cannot be negative.")
        native = _native_module()
        if not bool(native.native_camera_capture_supported()):
            raise RuntimeError("Native camera capture is not verified on this platform.")
        self._capture = native.CameraCapture(int(index))
        self._closed = False

    @property
    def closed(self) -> bool:
        return self._closed

    def read_frame(self) -> ImageFrame:
        if self._closed:
            raise RuntimeError("Camera capture is closed.")
        width, height, rgba = self._capture.read_frame()
        frame = ImageFrame(int(width), int(height), bytes(rgba))
        validate_camera_frame(frame)
        return frame

    def close(self) -> None:
        if self._closed:
            return
        self._capture.close()
        self._closed = True

    def __enter__(self) -> NativeCameraCapture:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()


def camera_devices() -> tuple[CameraDevice, ...]:
    """Return cameras discovered by the currently verified native backend."""

    native = _native_module()
    devices = native.list_camera_devices()
    return tuple(
        CameraDevice(int(index), str(name), str(description))
        for index, name, description in devices
    )


def native_camera_capture_supported() -> bool:
    """Whether this build exposes a verified native camera capture backend."""

    return bool(_native_module().native_camera_capture_supported())


def validate_camera_frame(frame: ImageFrame) -> None:
    """Apply native size and RGBA safety limits before a live frame reaches wgpu."""

    _native_module().validate_camera_rgba_frame(
        int(frame.width),
        int(frame.height),
        frame.rgba,
    )


def _native_module() -> Any:
    try:
        return importlib.import_module("_swirui_native")
    except ImportError as exc:
        raise RuntimeError(
            "SwirUI native camera core is not installed. Build/install native/ with Maturin."
        ) from exc


__all__ = [
    "CameraDevice",
    "CameraSource",
    "NativeCameraCapture",
    "camera_devices",
    "native_camera_capture_supported",
    "validate_camera_frame",
]
