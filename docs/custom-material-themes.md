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

## Animated material feedback

Since 0.1.0b2, `SurfaceInteraction` adds a shadow lift, accent glow, border emphasis
and soft diagonal sheen to an ordinary `ThemeSurface`. It follows hover, primary
button press and keyboard focus within the surface. Child geometry, edited values
and explicit `SurfaceStyle` objects remain unchanged. It does not animate the
layout or turn the child controls into projected 3D objects.

```python
from swirui import (
    AnimationController, App, Button, NEON_BLUE, SurfaceInteraction,
    SurfaceStyle, ThemeSurface, Window, mount,
)
from swirui.rendering import Rect, WgpuRenderer

app = App(renderer=WgpuRenderer())
window = app.add_window(Window(title="My material UI", width=560, height=360))
surface = ThemeSurface(
    bounds=Rect(60, 50, 440, 240), theme=NEON_BLUE,
    style=SurfaceStyle(kind="glass", depth_layers=2, elevation=10),
)
surface.add(Button("Create something", bounds=Rect(100, 140, 260, 48)))
mount(window, surface)
clock = AnimationController(app, window)
feedback = SurfaceInteraction(clock, surface)  # Bind after mounting.
try:
    app.run()
finally:
    feedback.dispose()
    clock.dispose()
    app.stop()
```

The binding uses the window's existing animation clock and hit-test paths, so
decorations never intercept a child's click. It enables hit testing only on the
container's own bounds. There is at most one active tween per binding, including
rapid direction changes. `Theme.motion_duration` controls timing; setting inherited
`reduced_motion=True` immediately completes the feedback without a moving transition.
Palette and material changes still follow the live theme. Effects stop when idle.

Bind only once per surface and to the window where it is mounted. `dispose()` is
idempotent and restores its ordinary appearance/input policy. Unmounting the
surface or closing the window disposes it automatically; bind again after remounting.
The binding is runtime state and is not serialized into a theme package.

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
