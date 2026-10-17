import json
from dataclasses import asdict, replace

import pytest

from swirui import (
    FUTURE_DARK,
    FUTURE_LIGHT,
    Input,
    Panel,
    SurfaceStyle,
    ThemePackage,
    ThemeSurface,
    ThemeTransition,
    Window,
    mount,
)
from swirui.rendering import Rect, SceneNodeKind


@pytest.mark.parametrize("kind", ["solid", "glass", "acrylic"])
def test_style_builds_bounded_noninteractive_layers(kind):
    style = SurfaceStyle(kind=kind, depth_layers=3, elevation=12, glow_radius=16)
    root = style.to_scene_node("sample", Rect(0, 0, 400, 260), FUTURE_DARK)
    nodes = list(root.walk())
    assert len([node for node in nodes if node.kind is SceneNodeKind.PATH]) == 3
    assert all(not node.hit_testable for node in nodes)
    assert len(nodes) < 100
    assert any(":material" in node.key for node in nodes) == (kind != "solid")
    assert len(list(style.to_scene_node("empty", Rect(0, 0, 0, 0), FUTURE_DARK).walk())) == 1
    # Tiny positive layout allocations should not fail material inset validation.
    style.to_scene_node("tiny", Rect(0, 0, .1, .1), FUTURE_DARK)


@pytest.mark.parametrize("name,value", [
    ("kind", "unknown"), ("blur_radius", float("inf")), ("glow_radius", -1),
    ("elevation", float("nan")), ("tint_opacity", 2), ("depth_layers", 9),
    ("depth_layers", True), ("grain_samples", 1.5), ("tilt_x", 36),
    ("border_width", "1"), ("depth_spacing", 10 ** 400),
])
def test_style_rejects_invalid_or_unbounded_tokens(name, value):
    with pytest.raises(ValueError):
        SurfaceStyle(**{name: value})


def test_style_package_v2_round_trip_preserves_v1_and_rejects_unknown_fields(tmp_path):
    styled = replace(FUTURE_DARK, surface_style=SurfaceStyle(kind="acrylic", depth_layers=3))
    package = ThemePackage("Custom dimensional theme", {"night": styled, "day": FUTURE_LIGHT},
                           "night")
    document = json.loads(package.dumps())
    assert document["format_version"] == 2
    assert document["themes"]["night"]["surface_style"] == asdict(styled.surface_style)
    path = tmp_path / "custom.json"
    package.save(path)
    assert ThemePackage.load(path) == package
    assert json.loads(ThemePackage("Basic", {"main": FUTURE_DARK}, "main").dumps())[
        "format_version"] == 1
    document["themes"]["night"]["surface_style"]["shader_path"] = "unsupported.wgsl"
    with pytest.raises(ValueError, match="exactly"):
        ThemePackage.loads(json.dumps(document))


@pytest.mark.parametrize("missing", [True, False])
def test_style_package_missing_or_bad_value_rejected(missing):
    themed = replace(FUTURE_DARK, surface_style=SurfaceStyle())
    document = json.loads(ThemePackage("Custom", {"main": themed}, "main").dumps())
    style = document["themes"]["main"]["surface_style"]
    if missing:
        del style["tilt_y"]
    else:
        style["grain_samples"] = True
    with pytest.raises(ValueError):
        ThemePackage.loads(json.dumps(document))


def test_inherited_style_live_override_reset_and_input_state():
    glass = replace(FUTURE_DARK, surface_style=SurfaceStyle(kind="glass", depth_layers=2))
    acrylic = replace(FUTURE_LIGHT, surface_style=SurfaceStyle(kind="acrylic"))
    root = Panel(bounds=Rect(0, 0, 500, 350), theme=glass)
    surface = ThemeSurface(bounds=Rect(30, 30, 420, 260))
    field = Input("Custom design", bounds=Rect(50, 70, 300, 44))
    surface.add(field)
    root.add(surface)
    window = Window()
    mount(window, root)
    window.focus_component(field)
    field.select(0, 6)
    assert surface.effective_style is glass.surface_style
    override = SurfaceStyle(kind="solid", elevation=0)
    surface.style = override
    root.theme = acrylic
    assert surface.effective_style is override
    surface.style = None
    assert surface.effective_style is acrylic.surface_style
    assert field.value == "Custom design" and field.selected_text == "Custom"
    assert window.focused_component is field
    with pytest.raises(TypeError):
        surface.style = "glass"
    assert surface.style is None


def test_material_policy_switches_at_transition_endpoint():
    source = replace(FUTURE_DARK, surface_style=SurfaceStyle(kind="glass"))
    target = replace(FUTURE_LIGHT, surface_style=SurfaceStyle(kind="acrylic"))
    samples = []
    animation = ThemeTransition(source, target, 1, samples.append).start()
    animation.advance(.5)
    assert samples[-1].surface_style is source.surface_style
    animation.advance(.5)
    assert samples[-1] is target
