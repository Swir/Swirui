from dataclasses import replace
from itertools import product

import pytest

from swirui import FUTURE_DARK, FUTURE_LIGHT, SurfaceStyle, ThemePackage


def luminance(swatch: str) -> float:
    channels = [int(swatch[index:index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4 for c in channels]
    return sum(a * b for a, b in zip(linear, (.2126, .7152, .0722), strict=True))


def contrast(first: str, second: str) -> float:
    a, b = sorted((luminance(first), luminance(second)))
    return (b + .05) / (a + .05)


@pytest.mark.parametrize("base", (FUTURE_DARK, FUTURE_LIGHT))
def test_accent_states_keep_label_contrast_across_rgb_cube_and_gray_boundaries(base):
    colors = {f"#{r:02X}{g:02X}{b:02X}" for r, g, b in product(range(0, 256, 51), repeat=3)}
    colors.update(f"#{v:02X}{v:02X}{v:02X}" for v in range(256))
    for color in colors:
        palette = base.with_accent(color).palette
        states = (palette.accent, palette.accent_hover, palette.accent_pressed)
        assert palette.accent == color
        assert len(set(states)) == 3
        assert all(contrast(palette.on_accent, state) >= 4.5 for state in states)
        assert contrast(palette.canvas, palette.focus) >= 3


def test_accent_authoring_preserves_material_and_motion_and_roundtrips_package():
    base = replace(FUTURE_DARK, control_radius=20, reduced_motion=True,
                   surface_style=SurfaceStyle(kind="glass", depth_layers=4))
    branded = base.with_accent("7fe0bfff")
    assert branded.palette.accent == "#7FE0BF"
    assert branded.surface_style is base.surface_style
    assert branded.control_radius == 20 and branded.reduced_motion
    assert branded.font_family == base.font_family
    assert branded.palette.success == base.palette.success
    assert branded.palette.surface == base.palette.surface
    assert base.palette.accent == FUTURE_DARK.palette.accent
    package = ThemePackage("Mint", {"main": branded}, "main")
    assert ThemePackage.loads(package.dumps()).default == branded


@pytest.mark.parametrize("value", ("", "#123", "#XX1122", "#11223380", "#11223300"))
def test_bad_or_translucent_accent_is_rejected_without_mutating_theme(value):
    before = FUTURE_DARK.palette
    with pytest.raises(ValueError):
        FUTURE_DARK.with_accent(value)
    assert FUTURE_DARK.palette is before


def test_translucent_canvas_requires_an_authored_palette_instead():
    base = replace(FUTURE_DARK, palette=replace(FUTURE_DARK.palette, canvas="#00000000"))
    with pytest.raises(ValueError, match="opaque"):
        base.with_accent("#FF0000")
