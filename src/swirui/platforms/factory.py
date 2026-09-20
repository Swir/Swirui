"""Platform backend selection for SwirUI."""

from __future__ import annotations

import os
import sys

from .base import NullPlatformBackend, PlatformBackend


def create_platform_backend() -> PlatformBackend:
    """Create the best native backend currently available for this platform.

    Linux selects the direct X11 backend only when an X display is advertised.
    Headless Linux environments, including ordinary CI jobs and servers, retain
    the deterministic null backend instead of failing during application start.
    Windows and macOS select their direct native backends unconditionally.
    """

    if sys.platform == "win32":
        from .windows_scroll import Win32PlatformBackend

        return Win32PlatformBackend()
    if sys.platform == "darwin":
        from .macos_scroll import MacOSCocoaPlatformBackend

        return MacOSCocoaPlatformBackend()
    if sys.platform.startswith("linux") and os.environ.get("DISPLAY"):
        from .linux_scroll import LinuxX11PlatformBackend

        return LinuxX11PlatformBackend()
    return NullPlatformBackend()
