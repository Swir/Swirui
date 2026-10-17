"""Read-only installation checks; loading an extension is not a GPU test."""

from __future__ import annotations

import importlib
import platform
import sys

from . import __version__


def installation_report() -> dict[str, str | bool]:
    supported = sys.platform == "win32" and platform.machine().lower() in {"amd64", "x86_64"}
    report: dict[str, str | bool] = {
        "version": __version__, "python": platform.python_version(),
        "platform": sys.platform, "architecture": platform.machine(),
        "supported_beta_platform": supported, "native_available": False,
        "ready": False, "gpu_tested": False,
    }
    if not supported:
        report["message"] = (
            "The desktop beta supports Windows x64; other platforms are experimental."
        )
        return report
    try:
        native = importlib.import_module("swirui._swirui_native")
        core_version = str(native.core_version())
    except (ImportError, OSError, AttributeError) as error:
        report["message"] = (
            "Native core could not load. Use 64-bit Python and install the Windows wheel with "
            f"python -m pip install --only-binary=:all: --force-reinstall swirui=={__version__}. "
            f"Details: {error}"
        )
        return report
    report["native_available"] = True
    report["native_version"] = core_version
    # Cargo uses SemVer prereleases; the public wheel uses PEP 440 spelling.
    normalized = core_version.replace("-alpha.", "a").replace("-beta.", "b").replace("-rc.", "rc")
    if normalized != __version__:
        report["message"] = "Python and native core versions differ. Reinstall the matching wheel."
        return report
    report["ready"] = True
    report["message"] = (
        "Native core loaded. Run python -m swirui demo --smoke-test to test rendering."
    )
    return report
