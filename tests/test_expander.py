from __future__ import annotations

import pytest

from swirui import Accordion, Button, Expander, Label, Window, build_accessibility_tree, mount
from swirui.core import Event
from swirui.platforms import NativeWindowHandle, PlatformEvent, PlatformEventKind, PointerButton
from swirui.rendering import Rect
from swirui.widgets import compile_component_scene


def _platform_event(kind: PlatformEventKind, **kwargs: object) -> PlatformEvent:
    return PlatformEvent(kind, NativeWindowHandle(1), **kwargs)


def _dispatch(expander: Expander, event_type: str, platform_event: PlatformEvent) -> Event:
    event = Event(event_type, expander, {"event": platform_event})
    return expander.dispatch(event)


def test_expander_collapses_and_restores_owned_content() -> None:
    content = Label("Details", bounds=Rect(20.0, 70.0, 160.0, 24.0), key="details")
    expander = Expander(
        "Advanced",
        bounds=Rect(10.0, 10.0, 220.0, 44.0),
        content=content,
        key="advanced",
    )

    assert expander.expanded is False
    assert content.visible is False
    assert expander.accessible_value_text == "Collapsed"

    expander.expand()
    assert content.visible is True
    assert expander.accessible_value_text == "Expanded"

    expander.collapse()
    assert content.visible is False


def test_expander_compiles_content_only_while_expanded() -> None:
    content = Label("Details", bounds=Rect(20.0, 70.0, 160.0, 24.0), key="details")
    expander = Expander(
        "Advanced",
        bounds=Rect(10.0, 10.0, 220.0, 44.0),
        content=content,
        key="advanced",
    )

    collapsed = compile_component_scene(expander, width=320.0, height=180.0)
    assert collapsed is not None
    assert {node.key for node in collapsed.walk()} == {
        "advanced",
        "advanced:title",
        "advanced:indicator",
    }

    expander.expand()
    expanded = compile_component_scene(expander, width=320.0, height=180.0)
    assert expanded is not None
    keys = {node.key for node in expanded.walk()}
    assert "details" in keys
    assert "advanced" in keys


def test_expander_pointer_and_keyboard_activation_are_preventable() -> None:
    expander = Expander("Advanced", bounds=Rect(10.0, 10.0, 220.0, 44.0))
    changes: list[bool] = []
    expander.on("expanded_changed", lambda event: changes.append(bool(event.data["expanded"])))

    _dispatch(
        expander,
        "pointer_down",
        _platform_event(PlatformEventKind.POINTER_DOWN, button=PointerButton.LEFT),
    )
    _dispatch(
        expander,
        "pointer_up",
        _platform_event(PlatformEventKind.POINTER_UP, button=PointerButton.LEFT),
    )
    assert expander.expanded is True

    key_down = _dispatch(
        expander,
        "key_down",
        _platform_event(PlatformEventKind.KEY_DOWN, key_code=0x20),
    )
    key_up = _dispatch(
        expander,
        "key_up",
        _platform_event(PlatformEventKind.KEY_UP, key_code=0x20),
    )
    assert key_down.default_prevented is True
    assert key_up.default_prevented is True
    assert expander.expanded is False
    assert changes == [True, False]


def test_expander_arrow_keys_set_disclosure_state_without_toggling() -> None:
    expander = Expander("Advanced", bounds=Rect(10.0, 10.0, 220.0, 44.0))

    right = _dispatch(
        expander,
        "key_down",
        _platform_event(PlatformEventKind.KEY_DOWN, key_code=0x27),
    )
    assert right.default_prevented is True
    assert expander.expanded is True

    down = _dispatch(
        expander,
        "key_down",
        _platform_event(PlatformEventKind.KEY_DOWN, key_code=0x28),
    )
    assert down.default_prevented is True
    assert expander.expanded is True

    left = _dispatch(
        expander,
        "key_down",
        _platform_event(PlatformEventKind.KEY_DOWN, key_code=0x25),
    )
    assert left.default_prevented is True
    assert expander.expanded is False


def test_nested_header_and_button_handle_their_own_input() -> None:
    button = Button("Apply", bounds=Rect(16, 106, 140, 32))
    inner = Expander("Options", bounds=Rect(12, 62, 220, 36), content=button, expanded=True)
    outer = Expander("Workspace", bounds=Rect(8, 12, 240, 40), content=inner, expanded=True)
    window = Window(width=300, height=190)
    mount(window, outer)
    clicked = []
    button.on("click", clicked.append)
    window.focus_component(button)
    for kind in (PlatformEventKind.KEY_DOWN, PlatformEventKind.KEY_UP):
        window._apply_platform_event(_platform_event(kind, key_code=0x20))
    assert len(clicked) == 1 and inner.expanded and outer.expanded
    window._apply_platform_event(_platform_event(PlatformEventKind.KEY_DOWN, key_code=0x25))
    assert inner.expanded and outer.expanded
    window.focus_component(inner)
    window._apply_platform_event(_platform_event(PlatformEventKind.KEY_DOWN, key_code=0x25))
    assert outer.expanded and not inner.expanded
    for kind in (PlatformEventKind.POINTER_DOWN, PlatformEventKind.POINTER_UP):
        window._apply_platform_event(_platform_event(kind, x=30, y=75, button=PointerButton.LEFT))
    assert outer.expanded and inner.expanded and window.focused_component is inner
    window._apply_platform_event(_platform_event(PlatformEventKind.POINTER_DOWN, x=30, y=24,
                                                 button=PointerButton.LEFT))
    assert outer.pressed
    window._apply_platform_event(_platform_event(PlatformEventKind.POINTER_UP, x=30, y=75,
                                                 button=PointerButton.LEFT))
    assert not outer.pressed and outer.expanded and inner.expanded


def test_expander_rejects_multiple_managed_children() -> None:
    expander = Expander("Advanced", bounds=Rect(10.0, 10.0, 220.0, 44.0))
    first = Label("First", bounds=Rect(0.0, 60.0, 100.0, 20.0))
    second = Label("Second", bounds=Rect(0.0, 90.0, 100.0, 20.0))

    with pytest.raises(ValueError, match="exactly one"):
        expander.add(first, second)

    expander.add(first)
    assert expander.content is first
    expander.add(second)
    assert expander.content is second
    assert first.parent is None


def test_exclusive_accordion_collapses_previous_item() -> None:
    first = Expander("One", bounds=Rect(0.0, 0.0, 180.0, 40.0), expanded=True)
    second = Expander("Two", bounds=Rect(0.0, 50.0, 180.0, 40.0))
    accordion = Accordion(first, second)

    assert accordion.expanded_item is first
    second.expand()
    assert first.expanded is False
    assert second.expanded is True
    assert accordion.expanded_items == (second,)


def test_required_accordion_keeps_one_item_open() -> None:
    first = Expander("One", bounds=Rect(0.0, 0.0, 180.0, 40.0))
    second = Expander("Two", bounds=Rect(0.0, 50.0, 180.0, 40.0))
    accordion = Accordion(first, second, require_one=True)

    assert accordion.expanded_item is first
    assert first.expanded is True
    first.collapse()
    assert first.expanded is True

    second.expand()
    assert second.expanded is True
    assert first.expanded is False
    second.collapse()
    assert second.expanded is True
    assert accordion.expanded_item is second


def test_multi_expand_accordion_allows_independent_items() -> None:
    first = Expander("One", bounds=Rect(0.0, 0.0, 180.0, 40.0))
    second = Expander("Two", bounds=Rect(0.0, 50.0, 180.0, 40.0))
    accordion = Accordion(first, second, allow_multiple=True)

    first.expand()
    second.expand()
    assert accordion.expanded_items == (first, second)


def test_collapsed_content_is_absent_from_accessibility_tree() -> None:
    content = Label("Secret details", bounds=Rect(0.0, 50.0, 180.0, 24.0), key="details")
    expander = Expander(
        "Advanced",
        bounds=Rect(0.0, 0.0, 180.0, 40.0),
        content=content,
        key="advanced",
    )

    collapsed = build_accessibility_tree(expander)
    assert collapsed is not None
    assert collapsed.find("details") is None
    assert collapsed.value_text == "Collapsed"

    expander.expand()
    expanded = build_accessibility_tree(expander)
    assert expanded is not None
    assert expanded.find("details") is not None
    assert expanded.value_text == "Expanded"


def test_disabled_expander_does_not_activate() -> None:
    expander = Expander("Advanced", bounds=Rect(10.0, 10.0, 220.0, 44.0))
    expander.enabled = False

    _dispatch(
        expander,
        "pointer_down",
        _platform_event(PlatformEventKind.POINTER_DOWN, button=PointerButton.LEFT),
    )
    _dispatch(
        expander,
        "pointer_up",
        _platform_event(PlatformEventKind.POINTER_UP, button=PointerButton.LEFT),
    )
    assert expander.expanded is False
