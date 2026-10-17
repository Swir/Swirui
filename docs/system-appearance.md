# System appearance

`ThemeController` selects a window's root theme from a light/dark pair. Its default
mode follows the native application appearance preference. Applications can offer
an explicit light or dark choice without changing operating-system settings.

```python
from swirui import ThemeController, ThemeMode

# window is an existing Window; attach before or after mount()/App.start().
appearance = ThemeController(window)
appearance.mode = ThemeMode.LIGHT
appearance.mode = ThemeMode.DARK
appearance.mode = ThemeMode.SYSTEM
```

The controller applies Future Light and Future Dark by default. To use package
variants, choose their meaning explicitly; variant names are not inferred:

```python
from swirui import ColorScheme, ThemeController, ThemePackage

package = ThemePackage.load("workspace.swirui-theme.json")
appearance = ThemeController(
    window,
    light=package.themes["day"],
    dark=package.themes["night"],
    fallback=ColorScheme.DARK,
)
```

Only one controller may own a window at a time. Replace its pair with
`appearance.set_themes(light=..., dark=...)`, or call `appearance.close()` before
attaching another controller. While attached, the controller owns `window.root.theme`;
use its mode/pair API instead of assigning that root theme directly. Local child
themes and explicit widget overrides keep their existing precedence.

## Availability and lifecycle

`system_scheme` is the last detected `ColorScheme.LIGHT` / `ColorScheme.DARK`, or
`None` when no preference is available. `effective_scheme` and `effective_theme`
report the applied choice. In system mode, an unavailable preference uses the
configured `fallback` (dark by default). Manual mode always wins. The fallback
can also be changed at runtime.

The controller responds to initial native binding, appearance notifications and
root replacement. Root theme updates and dependent `changed` observers run in one
state transaction. Duplicate notifications do not rebuild an unchanged scene.
`refresh()` explicitly rereads the preference; there is no timer, polling thread
or background automation. Use controller methods on the UI thread.

`appearance.on("changed", handler)` reports `mode`, `system_scheme`,
`effective_scheme`, `theme`, and `previous` (the previous tuple of those first four
values, or `None`). A window closing automatically closes its controller.
`close()` is idempotent, removes its window listeners and retains the current
appearance. A closed controller rejects subsequent updates.

## Windows implementation

The Win32 backend reads the current user's `AppsUseLightTheme` DWORD under
`Software\Microsoft\Windows\CurrentVersion\Themes\Personalize`. Value 0 selects
dark and 1 selects light; missing, inaccessible or malformed values are unknown.
It does not use `SystemUsesLightTheme`, which describes Windows surfaces rather
than the application preference. These values are documented in Microsoft's
[Personalization colors reference](https://learn.microsoft.com/windows/apps/develop/settings/settings-common#personalization---colors).

The backend normalizes [WM_SETTINGCHANGE](https://learn.microsoft.com/windows/win32/winmsg/wm-settingchange)
and [WM_THEMECHANGED](https://learn.microsoft.com/windows/win32/winmsg/wm-themechanged)
as `PlatformEventKind.SYSTEM_APPEARANCE_CHANGED` for its own windows. The framework
then emits `system_appearance_changed`. Preference reading and theme changes occur
in the application event loop, outside the native callback. No notification pointer
is dereferenced and no system preference is written.

`Window.get_system_color_scheme()` exposes the optional backend capability without
requiring a controller. Existing third-party backends remain compatible. A backend
can implement `get_system_color_scheme()` and emit the normalized event to support
the same policy. Headless, Linux and macOS backends currently report unknown;
native synchronization on those systems is not implemented by this change.

## Preview and qualification

```console
python examples/appearance_gallery.py
```

The native Windows example provides system/light/dark choices, an editable draft,
and a child panel that keeps its own dark theme. Its status distinguishes detected
system preference from fallback.

Tests cover initial binding, manual override, fallback, independent windows,
replacement roots, local scopes, cleanup, reentrant observers and deduplication.
The Windows/wgpu test first reads the real current preference, then uses controlled
reader results with real messages sent to its own HWND to verify light/dark pixels,
focus, selection and context retention. It does not modify Windows settings or
claim a user-performed operating-system appearance toggle.

This supports application color preference only. High contrast, system accent
colors, native title-bar styling, automatic reduced-motion detection, Linux/macOS
appearance adapters remain separate work. Optional animated transitions and
built-in variants are described in [Appearance presets](theme-presets.md).
