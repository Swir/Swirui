"""Read-only Windows application appearance preference; no registry writes."""

from __future__ import annotations

from typing import Any

from .events import ColorScheme

_PERSONALIZE = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"


def _registry_scheme(registry: Any) -> ColorScheme | None:
    try:
        with registry.OpenKey(registry.HKEY_CURRENT_USER, _PERSONALIZE,
                              0, registry.KEY_READ) as key:
            value, kind = registry.QueryValueEx(key, "AppsUseLightTheme")
    except OSError:
        return None
    if kind != registry.REG_DWORD or type(value) is not int or value not in (0, 1):
        return None
    return ColorScheme.LIGHT if value else ColorScheme.DARK


def read_app_color_scheme() -> ColorScheme | None:
    """Return the current user's app preference, or None when unavailable.

    The registry contract is documented under Personalization - colors:
    https://learn.microsoft.com/windows/apps/develop/settings/settings-common
    """
    try:
        import winreg
    except ImportError:
        return None
    return _registry_scheme(winreg)
