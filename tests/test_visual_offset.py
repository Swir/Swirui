import math

import pytest

from swirui import Button
from swirui.rendering import Point, Rect
from swirui.widgets.runtime import compile_component_scene


def test_visual_offset_translates_scene_and_hit_testing_without_changing_layout_geometry() -> None:
    button = Button(
        "Offset",
        key="offset-button",
        bounds=Rect(40.0, 30.0, 120.0, 44.0),
    )
    authored_bounds = button.bounds
    preferred_size = button.preferred_size
    layout_revision = button._layout_revision

    button.visual_offset = Point(80.0, 24.0)
    scene = compile_component_scene(button, width=360.0, height=220.0)

    assert scene is not None
    assert button.bounds == authored_bounds
    assert button.preferred_size == preferred_size
    assert button._layout_revision == layout_revision
    assert scene.root.bounds == Rect(120.0, 54.0, 120.0, 44.0)
    assert scene.hit_test_xy(150.0, 70.0) is scene.root
    assert scene.hit_test_xy(60.0, 50.0) is None


def test_visual_offset_moves_the_complete_compiled_widget_subtree() -> None:
    button = Button(
        "Children move too",
        key="translated-button",
        bounds=Rect(20.0, 20.0, 180.0, 48.0),
    )
    button.visual_offset = Point(15.0, -5.0)

    scene = compile_component_scene(button, width=320.0, height=180.0)

    assert scene is not None
    assert scene.root.bounds == Rect(35.0, 15.0, 180.0, 48.0)
    for child in scene.root.children:
        assert child.bounds.x >= scene.root.bounds.x
        assert child.bounds.y >= scene.root.bounds.y


def test_set_visual_offset_is_chainable_and_rejects_non_finite_coordinates() -> None:
    button = Button("Offset", bounds=Rect(0.0, 0.0, 120.0, 40.0))

    assert button.set_visual_offset(4.0, -3.0) is button
    assert button.visual_offset == Point(4.0, -3.0)

    with pytest.raises(ValueError, match="visual_offset"):
        button.visual_offset = Point(math.inf, 0.0)
    with pytest.raises(ValueError, match="visual_offset"):
        button.set_visual_offset(0.0, math.nan)
