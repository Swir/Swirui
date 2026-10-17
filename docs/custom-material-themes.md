# Create your own dimensional appearance

Applications are not restricted to the built-in presets. A `Theme` can carry a
custom palette, fonts, radius, motion and an immutable `SurfaceStyle`.
`ThemeSurface` inherits that style and applies it around ordinary child controls.

```python
from dataclasses import replace
from swirui import NEON_BLUE, SurfaceStyle, ThemePackage, ThemeSurface, Input
from swirui.rendering import Rect

my_theme = replace(
    NEON_BLUE,
    palette=replace(NEON_BLUE.palette, accent="#85F5E3"),
    control_radius=20,
    surface_style=SurfaceStyle(
        kind="glass", blur_radius=28, tint_opacity=0.66,
        elevation=14, glow_radius=20, depth_layers=3, depth_spacing=12,
        tilt_x=10, tilt_y=-12,
    ),
)
panel = ThemeSurface(bounds=Rect(40, 40, 420, 260), theme=my_theme)
panel.add(Input("My application", bounds=Rect(64, 90, 360, 44)))

package = ThemePackage("My appearance", {"main": my_theme}, "main")
package.save("my-appearance.swirui-theme.json")
restored = ThemePackage.load("my-appearance.swirui-theme.json")
panel.theme = restored.default
```

Use `kind="solid"`, `"glass"` or `"acrylic"`. Surface tint and border follow the
theme; glow and perspective planes follow its accent. A local `style=` override
has priority over the inherited theme; assigning `panel.style = None` restores
inheritance. Existing `Card` and `GlassCard` APIs retain their behavior.

Depth is made from projected decorative planes, shadows and glow. Foreground
controls keep normal geometry and hit testing. This is a dimensional UI material,
not a 3D model viewport, a transformed interactive subtree or physically based
rendering. The existing lower-level `PerspectivePlane`, `Parallax`,
`FrostedGlass` and `Acrylic` APIs remain available for custom scene authoring.

Geometry and sampling are bounded: at most eight planes, 96 grain samples,
64-DIP blur/glow and 35-degree backplate tilt. Invalid and non-finite values fail
before rendering. Zero-size surfaces produce an empty group; tiny positive
surfaces clamp border width. Decoration does not capture input.

Theme transitions blend colors/radius as before. Surface policy switches at
completion; blur, grain, depth and material kinds are not interpolated. Custom
glass backgrounds require contrast checks against their actual backdrop.

## Sharing and compatibility

Packages with a material style use JSON `format_version: 2`, which includes
`surface_style` for every variant (an object or null). Packages without a style
still write the unchanged version-1 schema. Both versions load; old readers reject
version 2 explicitly. Unknown/missing style fields and unsupported values are
rejected. The package remains data-only: no code, shader imports or external
assets are executed.

Run `python examples/custom_theme_gallery.py` on Windows with the native package
installed. Its `make_package()` function is an editable starting point, with
glass/acrylic/solid variants. The companion
`examples/themes/ocean-studio.swirui-theme.json` can be loaded directly.
