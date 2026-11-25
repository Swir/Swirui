# Build your own signature appearance

`Theme.with_accent()` creates an immutable branded copy of any existing theme.
It changes only `accent`, `accent_hover`, `accent_pressed`, `on_accent`, `focus`
and `selection`. Your typography, spacing radius, semantic success/error colors,
motion policy and `SurfaceStyle` remain intact. Existing widget color overrides
still take precedence over inherited theme tokens.

```python
from dataclasses import replace
from swirui import NEON_BLUE, FUTURE_LIGHT, SurfaceStyle, ThemePackage

night = replace(
    NEON_BLUE.with_accent("#7FE0BF"),
    control_radius=18,
    surface_style=SurfaceStyle(kind="glass", depth_layers=3, elevation=12),
)
day = FUTURE_LIGHT.with_accent("#146F52")
package = ThemePackage("My signature", {"night": night, "day": day}, "night")
package.save("signature.swirui-theme.json")
# Apply to your existing component tree:
# root.theme = package.default
```

Use an opaque six-digit sRGB hex color, optionally prefixed by `#`. Eight-digit
colors are accepted only with `FF` alpha. The theme's canvas must also be opaque;
otherwise `ValueError` is raised before any new theme is applied. For translucent
canvases, author the full `Palette` against the actual composited backdrop.

The helper preserves the exact requested accent and chooses a black or white
`on_accent`. Hover/pressed states retain at least 4.5:1 contrast with that label,
including black, white and boundary grays; their foreground never flips on press.
Focus is derived to contrast at least 3:1 with the canvas. Checks use the final
quantized sRGB tokens and relative luminance, consistent with the
[W3C contrast definition](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html).
These are token-pair guarantees, not a claim of application-wide WCAG compliance:
transparency, custom overrides, other backgrounds, text sizes and transitions
still require review. Selection tint has no independent contrast guarantee.

In Studio, open **Settings → Signature color**. Apply a swatch or type a hex
color and press Enter/Apply. Invalid input leaves the current theme intact.
Reset restores each mode's default accent. Your chosen accent survives mode,
material and reduced-motion changes, and does not recreate edited controls.
Studio settings are session-local; `ThemePackage.save()` is the explicit route
for sharing/persisting your own application's theme. No theme code is executed,
and no external assets are downloaded by the authoring helper.
