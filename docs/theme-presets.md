# Appearance presets and transitions

SwirUI ships nine immutable appearance presets in `THEME_PRESETS`:

| Key | Character |
| --- | --- |
| `future_dark` | Original dark SwirUI appearance |
| `future_light` | Original light SwirUI appearance |
| `neon_blue` | Navy surfaces, cyan accent, rounded controls |
| `neon_green` | Charcoal-green surfaces, mint accent |
| `matrix` | Near-black green, monospace typography, tight corners |
| `cyberpunk` | Purple surfaces, magenta accent, angular controls |
| `oled` | True black canvas and surface, restrained monochrome accent |
| `minimal` | Neutral light surfaces and charcoal accent |
| `professional` | Light blue-grey surfaces, blue accent |

The corresponding constants are exported at package level, including
`NEON_BLUE`, `MATRIX`, `OLED` and `PROFESSIONAL`. Use
`dataclasses.replace` to customize a copy; the registry cannot be mutated.
All variants round-trip through `ThemePackage`.

Run `python examples/theme_gallery.py` with a native installation to explore
the presets, edit a persistent draft and toggle reduced motion.

## Opt-in animated appearance

```python
from swirui import AnimationController, ThemeController, NEON_BLUE, PROFESSIONAL

# app owns window; mount a root before attaching the controller.
animations = AnimationController(app, window)
appearance = ThemeController(
    window, light=PROFESSIONAL, dark=NEON_BLUE, animations=animations,
)
window.on("closed", lambda _: animations.dispose())
appearance.mode = "light"
```

Without `animations`, changes remain immediate. A visible, native-bound window
animates its root using the target theme's `motion_duration`; initial attachment,
hidden/unbound windows and disposed drivers snap to the chosen appearance.
Either endpoint with `reduced_motion=True` also makes the change immediate.
Reduced motion is an explicit application setting, not detected from the OS.

The animation uses the window's existing rendered-frame clock. There is no
thread or idle polling. Rapid selections cancel only the previous appearance
animation and start from the currently displayed sample. Hiding the window
finishes the transition. Closing the controller cancels it and retains its
current sample. Child theme scopes and explicit widget overrides remain intact.

`effective_theme` and `changed` describe the selected **target**. During a
transition, `window.root.theme` contains the current sample and
`appearance.transitioning` is true. Sample updates use ordinary theme-change
notifications; the policy's `changed` event is not emitted for every frame.

## Interpolation and legibility

`ThemeTransition(source, target, seconds, update)` is also usable directly
with `AnimationController.play` and the existing animation groups. Palette RGB
uses premultiplied linear-light interpolation, then converts back to sRGB HEX.
Radius is interpolated. Fonts switch at completion to avoid changing text
geometry every frame. Exact authored endpoint objects are retained.

By default, opaque text roles with intermediate contrast below 4.5 use the
best contrast among the blended color, endpoint colors, black and white.
This can cause a deliberate foreground polarity change during a dark-to-light
transition. Alpha backgrounds skip this guard. Set
`protect_text_contrast=False` for unmodified palette interpolation.

Preset tests check at least 4.5 contrast for authored text against the main
surfaces and selection, muted text against main surfaces, and on-accent text
against accent states. This is a scoped palette check, not a full accessibility
certification. Arbitrary custom palettes and intermediate surfaces cannot
guarantee every foreground/background combination meets a universal ratio.

These are palette, typography, radius and motion presets. They do not claim
glass materials, backdrop blur, HDR glow, adaptive wallpaper extraction or
system high-contrast integration.
