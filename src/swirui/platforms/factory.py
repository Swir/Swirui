"""Platform backend selection for SwirUI."""

from __future__ import annotations

import sys

from .base import NullPlatformBackend, PlatformBackend


def create_platform_backend() -> PlatformBackend:
    """Create the best native backend currently available for this platform."""

    if sys.platform == "win32":
        from .windows import Win32PlatformBackend

        return Win32PlatformBackend()
    return NullPlatformBackend()
