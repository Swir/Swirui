# Theme packages

`ThemePackage` shares complete appearance variants as a small UTF-8 JSON file.
It includes every semantic palette role, body and monospace fonts, corner radius,
motion duration and reduced-motion preference. Loading does not change a window;
assign a variant to a component to apply the existing runtime inheritance rules.

```python
from dataclasses import replace
from swirui import FUTURE_DARK, FUTURE_LIGHT, ThemePackage

night = replace(FUTURE_DARK, control_radius=8)
package = ThemePackage(
    name="My workspace",
    themes={"night": night, "day": FUTURE_LIGHT},
    default_theme="night",
    version="1.0.0",
    description="Two appearances for the same application.",
)
package.save("workspace.swirui-theme.json")

loaded = ThemePackage.load("workspace.swirui-theme.json")
# root is an existing Panel or other Component:
root.theme = loaded.default
root.theme = loaded.themes["day"]
```

The package copies its variant mapping and exposes it read-only. `Theme` and
`Palette` remain immutable. Explicit widget overrides and local component scopes
continue to take precedence. Text, selection and focus remain in the same controls.

`dumps()` / `loads(text)` provide the same contract without file I/O. `save(path)`
writes a temporary sibling then atomically replaces the destination; a failed
write or replacement leaves an existing file intact. The parent directory must
exist. Filesystem errors propagate as `OSError`; malformed or unsupported packages
raise `ValueError`. Validate first, then apply; failed loading never changes an
active theme.

## File format version 1

Basic themes still use version 1. Themes carrying a `SurfaceStyle` use
[version 2](custom-material-themes.md), adding validated material/depth tokens.
Both formats are supported; older readers reject version 2 explicitly.

The top-level object has exactly these fields:

| Field | Meaning |
| --- | --- |
| `format` | Exactly `swirui.theme-package` |
| `format_version` | Integer `1`; independent of the package's own version |
| `name` | Nonempty display name, at most 120 characters |
| `version` | Nonempty package version label, at most 64 characters |
| `author` | Attribution string, at most 120 characters; use `""` if absent |
| `description` | Description string, at most 2048 characters; use `""` if absent |
| `default_theme` | A key present in `themes` |
| `themes` | Between 1 and 32 complete variant objects |

Variant keys start with a lowercase ASCII letter and contain only lowercase
letters, digits, `_` and `-`, with a maximum of 48 characters. Every variant has
`palette`, `font_family`, `monospace_family`, `control_radius`, `motion_duration`
and `reduced_motion`. Font family strings are nonempty and at most 256 characters.
Both numeric tokens are finite and non-negative; booleans are not numbers.
`reduced_motion` is a JSON boolean.

Every palette includes `canvas`, `surface`, `raised`, `hover`, `pressed`, `border`,
`focus`, `accent`, `accent_hover`, `accent_pressed`, `on_accent`, `text`, `muted`,
`disabled`, `disabled_text`, `selection`, `success`, `warning` and `error`.
Colors use encoded sRGB `#RRGGBB` or `#RRGGBBAA`. Alpha is retained; native shapes
receive linear RGB and native text receives encoded sRGB through the existing
theme APIs.

Files are limited to 256 KiB. Missing fields, unknown fields, duplicate JSON keys,
unsupported format versions, invalid Unicode and non-finite numbers are rejected.
Complete snapshots make appearance independent of future default-token changes.
See [Aurora](../examples/themes/aurora.swirui-theme.json) for an editable package.

## Try a package

With the native Windows build installed, from the repository root:

```console
python examples/workbench_gallery.py --theme-package examples/themes/aurora.swirui-theme.json
```

Use **Next appearance** to cycle the file's variants, starting with its default.
Without a package, Workbench uses Future Dark and Future Light. A malformed file
is reported before a native window opens.

Packages contain data only: no Python execution, remote resources, includes,
embedded font binaries, automatic downloads or global installation. Font family
names use the renderer's installed-font fallback. This feature does not introduce
file watching or a theme store. Version 2 can carry an explicit SurfaceStyle.
To map a
package's light/dark pair to Windows preferences, use the separate
[ThemeController](system-appearance.md), optionally connected to the
[animation driver](theme-presets.md). Native qualification currently covers Windows/wgpu.
