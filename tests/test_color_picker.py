from __future__ import annotations

import pytest

from swirui import ColorPicker
from swirui.core import AccessibilityRole
from swirui.rendering import Color, Rect


def test_color_picker_round_trip_channels_and_hex() -> None:
    picker = ColorPicker(
        bounds=Rect(0.0, 0.0, 420.0, 300.0),
        value=Color.from_hex("#336699CC"),
        key="picker",
    )

    assert picker.hex_value == "#336699CC"
    assert picker.channels == ("hue", "saturation", "value", "alpha")
    assert picker.active_channel == "hue"

    changes: list[str] = []
    picker.on("color_changed", lambda event: changes.append(event.data["hex_value"]))
    picker.activate_channel("saturation").set_channel_value("saturation", 1.0)
    assert picker.channel_value("saturation") == pytest.approx(1.0)
    assert changes[-1] == picker.hex_value

    picker.set_hex("#0088FFFF")
    assert picker.hex_value == "#0088FFFF"
    assert picker.value.a == pytest.approx(1.0)


def test_color_picker_scene_uses_stable_channel_keys() -> None:
    picker = ColorPicker(
        bounds=Rect(12.0, 20.0, 500.0, 300.0),
        value=Color.from_hex("#FF6600AA"),
        key="brand",
    )

    scene = picker.build_scene_node()
    keys = {node.key for node in scene.walk()}
    assert "brand:preview" in keys
    assert "brand:hex" in keys
    assert "brand:thumb:hue" in keys
    assert "brand:thumb:saturation" in keys
    assert "brand:thumb:value" in keys
    assert "brand:thumb:alpha" in keys
    assert "brand:track:hue:0" in keys
    assert "brand:track:hue:15" in keys

    hue_track = picker.track_bounds("hue")
    alpha_track = picker.track_bounds("alpha")
    assert hue_track.width == pytest.approx(472.0)
    assert alpha_track.y > hue_track.y


def test_color_picker_accessibility_exposes_each_channel() -> None:
    picker = ColorPicker(
        bounds=Rect(0.0, 0.0, 460.0, 300.0),
        value=Color.from_hex("#62E5FF80"),
        key="a11y-picker",
    )
    picker.activate_channel("alpha")

    snapshot = picker.accessibility_snapshot(focused=picker)
    assert snapshot.role is AccessibilityRole.GROUP
    assert snapshot.focused is True
    assert snapshot.value_text == picker.hex_value
    assert snapshot.column_count == 4
    assert len(snapshot.children) == 4
    assert all(child.role is AccessibilityRole.SLIDER for child in snapshot.children)
    alpha = snapshot.children[-1]
    assert alpha.name == "Alpha"
    assert alpha.selected is True
    assert alpha.max_value == pytest.approx(100.0)
    assert alpha.value == pytest.approx(50.196078, rel=1e-5)


def test_color_picker_without_alpha_keeps_opaque_contract() -> None:
    picker = ColorPicker(
        bounds=Rect(0.0, 0.0, 420.0, 250.0),
        value=Color.from_hex("#33669940"),
        show_alpha=False,
        key="opaque",
    )

    assert picker.channels == ("hue", "saturation", "value")
    assert picker.hex_value == "#336699"
    assert picker.value.a == pytest.approx(1.0)
    with pytest.raises(ValueError, match="not available"):
        picker.activate_channel("alpha")
    with pytest.raises(ValueError, match="not available"):
        picker.track_bounds("alpha")


def test_color_picker_adjustment_is_bounded() -> None:
    picker = ColorPicker(
        bounds=Rect(0.0, 0.0, 420.0, 300.0),
        value=Color.from_hex("#00FF00FF"),
    )
    picker.activate_channel("value")
    picker.set_channel_value("value", 0.02)
    picker.adjust_active(-10, coarse=True)
    assert picker.channel_value("value") == pytest.approx(0.0)
    picker.adjust_active(20, coarse=True)
    assert picker.channel_value("value") == pytest.approx(1.0)
