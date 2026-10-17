import pytest

from swirui import Button, Component, Panel, TabItem, Tabs, Window, mount
from swirui.platforms import NativeWindowHandle, PlatformEvent, PlatformEventKind
from swirui.rendering import Rect

BOUNDS = Rect(0, 0, 400, 300)


def key(window, code):
    window._apply_platform_event(
        PlatformEvent(PlatformEventKind.KEY_DOWN, NativeWindowHandle(1), key_code=code)
    )


@pytest.mark.parametrize("code", [0x23, 0x24, 0x25, 0x27])
def test_unhandled_content_navigation_keys_do_not_activate_parent_tabs(code):
    button = Button("Content action", bounds=Rect(20, 20, 180, 40))
    tabs = Tabs(
        [
            TabItem("first", "First", Panel(bounds=BOUNDS)),
            TabItem("middle", "Middle", button),
            TabItem("last", "Last", Panel(bounds=BOUNDS)),
        ],
        selected_key="middle",
        bounds=BOUNDS,
    )
    window = Window(width=400, height=300)
    runtime = mount(window, tabs)
    try:
        window.focus_component(button)
        key(window, code)
        assert tabs.selected_key == "middle" and window.focused_component is button
        # These same keys still operate the tab header when it actually owns focus.
        window.focus_component(tabs)
        key(window, code)
        assert tabs.selected_key != "middle"
    finally:
        runtime.unmount()


def test_nested_tabs_consume_navigation_once_and_honor_prevented_default():
    inner = Tabs(
        [TabItem("a", "A", Panel(bounds=BOUNDS)), TabItem("b", "B", Panel(bounds=BOUNDS))],
        bounds=BOUNDS,
    )
    outer = Tabs(
        [TabItem("inner", "Inner", inner), TabItem("other", "Other", Panel(bounds=BOUNDS))],
        bounds=BOUNDS,
    )
    root = Component().add(outer)
    window = Window(width=400, height=300)
    runtime = mount(window, root)
    try:
        window.focus_component(inner)
        key(window, 0x27)
        assert inner.selected_key == "b" and outer.selected_key == "inner"
        root.on("key_down", lambda event: event.prevent_default(), capture=True)
        key(window, 0x25)
        assert inner.selected_key == "b" and outer.selected_key == "inner"
    finally:
        runtime.unmount()
