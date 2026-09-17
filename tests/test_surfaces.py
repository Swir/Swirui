import pytest

from swirui import Card, Component, Frame, GlassCard, Label, Panel
from swirui.core import AccessibilityRole, Event
from swirui.rendering import Color, FrostedGlass, Point, Rect, SceneNodeKind
from swirui.widgets import compile_component_scene


def _node(scene: object, key: str) -> object:
    return next(node for node in scene.walk() if node.key == key)  # type: ignore[attr-defined]


def test_panel_compiles_surface_border_and_widget_children() -> None:
    root = Component("root")
    panel = Panel(
        key="panel",
        bounds=Rect(20.0, 20.0, 280.0, 150.0),
        border_width=2.0,
        corner_radius=14.0,
        clip_to_bounds=True,
        accessible_name="Settings panel",
    )
    label = Label("Retained child", key="panel-label", bounds=Rect(42.0, 46.0, 180.0, 28.0))
    panel.add(label)
    root.add(panel)

    scene = compile_component_scene(root, width=360.0, height=220.0)

    assert scene is not None
    panel_node = next(node for node in scene.walk() if node.key == "panel")
    border = next(node for node in scene.walk() if node.key == "panel:border")
    surface = next(node for node in scene.walk() if node.key == "panel:surface")
    content = next(node for node in scene.walk() if node.key == "panel-label")
    assert panel_node.kind is SceneNodeKind.GROUP
    assert panel_node.clip_to_bounds is True
    assert panel_node.hit_testable is False
    assert border.kind is SceneNodeKind.RECTANGLE
    assert surface.kind is SceneNodeKind.RECTANGLE
    assert content.kind is SceneNodeKind.TEXT
    assert panel.accessibility_role is AccessibilityRole.GROUP
    assert scene.hit_test(Point(52.0, 54.0)) is None


def test_frame_is_border_only_and_preserves_child_content() -> None:
    root = Component("root")
    frame = Frame(key="frame", bounds=Rect(12.0, 14.0, 240.0, 120.0))
    child = Label("Inside", key="inside", bounds=Rect(28.0, 32.0, 100.0, 24.0))
    frame.add(child)
    root.add(frame)

    scene = compile_component_scene(root, width=300.0, height=180.0)

    assert scene is not None
    keys = {node.key for node in scene.walk()}
    assert "frame:border" in keys
    assert "frame:surface" not in keys
    assert "inside" in keys


def test_card_adds_noninteractive_retained_shadow_below_surface() -> None:
    root = Component("root")
    card = Card(
        key="card",
        bounds=Rect(30.0, 30.0, 260.0, 150.0),
        accessible_name="Summary card",
    )
    card.add(Label("Summary", key="card-title", bounds=Rect(54.0, 54.0, 160.0, 28.0)))
    root.add(card)

    scene = compile_component_scene(root, width=360.0, height=240.0)

    assert scene is not None
    card_node = next(node for node in scene.walk() if node.key == "card")
    shadow = next(node for node in scene.walk() if node.key == "card:shadow")
    shadow_layers = [node for node in scene.walk() if node.key.startswith("card:shadow:layer:")]
    surface = next(node for node in scene.walk() if node.key == "card:surface")
    assert card_node.kind is SceneNodeKind.GROUP
    assert shadow.kind is SceneNodeKind.GROUP
    assert shadow.hit_testable is False
    assert len(shadow_layers) == 8
    assert all(node.hit_testable is False for node in shadow_layers)
    assert shadow.z_index < surface.z_index


def test_glass_card_reuses_backdrop_material_and_keeps_child_sharp() -> None:
    root = Component("root")
    material = FrostedGlass(blur_radius=18.0)
    glass = GlassCard(
        key="glass",
        bounds=Rect(24.0, 24.0, 300.0, 170.0),
        material=material,
        accessible_name="Glass status card",
    )
    label = Label("Foreground", key="glass-label", bounds=Rect(48.0, 54.0, 180.0, 30.0))
    glass.add(label)
    root.add(glass)
    invalidations: list[Event] = []
    root.on("invalidated", invalidations.append)

    scene = compile_component_scene(root, width=380.0, height=240.0)

    assert scene is not None
    glass_node = next(node for node in scene.walk() if node.key == "glass")
    tint = next(node for node in scene.walk() if node.key == "glass:tint")
    content = next(node for node in scene.walk() if node.key == "glass-label")
    assert glass_node.kind is SceneNodeKind.BACKDROP_BLUR
    assert glass_node.blur_radius == 18.0
    assert glass_node.hit_testable is False
    assert tint.z_index < content.z_index
    assert glass.accessibility_role is AccessibilityRole.GROUP

    glass.material = FrostedGlass(blur_radius=26.0, tint=Color.from_hex("#0A2444AA"))

    assert invalidations[-1].data["component"] is glass
    assert invalidations[-1].data["reason"] == "material"
    updated = compile_component_scene(root, width=380.0, height=240.0)
    assert updated is not None
    assert next(node for node in updated.walk() if node.key == "glass").blur_radius == 26.0


def test_panel_rejects_border_that_cannot_fit_bounds() -> None:
    panel = Panel(
        bounds=Rect(0.0, 0.0, 20.0, 20.0),
        border_width=11.0,
    )
    with pytest.raises(ValueError, match="border_width"):
        panel.build_scene_node()
