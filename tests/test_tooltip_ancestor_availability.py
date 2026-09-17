from swirui import Button, Component, Tooltip
from swirui.rendering import Rect


def test_tooltip_respects_hidden_and_disabled_target_ancestors() -> None:
    parent = Component("parent")
    button = Button("Inspect", bounds=Rect(0.0, 0.0, 120.0, 40.0))
    parent.add(button)
    tooltip = Tooltip(
        "Inspect retained node",
        target=button,
        bounds=Rect(0.0, 48.0, 180.0, 34.0),
    )

    parent.enabled = False
    button.emit("pointer_enter")
    assert tooltip.is_open is False

    parent.enabled = True
    button.emit("pointer_enter")
    assert tooltip.is_open is True
    parent.visible = False
    assert tooltip.is_open is False

    parent.visible = True
    button.emit("focus_gained")
    assert tooltip.is_open is True
    parent.enabled = False
    assert tooltip.is_open is False
