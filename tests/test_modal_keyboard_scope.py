from swirui import Button, Component, Dialog, Window, mount
from swirui.platforms import NativeWindowHandle, PlatformEvent, PlatformEventKind
from swirui.rendering import Rect


def tab(window, *, reverse=False):
    window._apply_platform_event(
        PlatformEvent(PlatformEventKind.KEY_DOWN, NativeWindowHandle(1), key_code=9, shift=reverse)
    )


def test_modal_tab_wraps_skips_unavailable_descendants_and_respects_prevention():
    bounds = Rect(0, 0, 120, 40)
    outside = Button("Outside", bounds=bounds)
    first, last = Button("First", bounds=bounds), Button("Last", bounds=bounds)
    hidden = Component().add(Button("Hidden", bounds=bounds))
    hidden.visible = False
    disabled = Button("Disabled", bounds=bounds)
    disabled.enabled = False
    content = Component().add(first, hidden, disabled, last)
    dialog = Dialog(
        bounds=Rect(0, 0, 500, 400),
        dialog_bounds=Rect(50, 50, 400, 300),
        content=content,
        dismiss_on_escape=False,
    )
    window = Window(width=500, height=400)
    runtime = mount(window, Component().add(outside, dialog))
    try:
        window.focus_component(first)
        tab(window, reverse=True)
        assert window.focused_component is last
        tab(window)
        assert window.focused_component is first
        tab(window)
        assert window.focused_component is last
        last.on("key_down", lambda event: event.prevent_default())
        tab(window)
        assert window.focused_component is last
        first.enabled = last.enabled = False
        window.focus_component(dialog)
        tab(window)
        assert window.focused_component is dialog
    finally:
        runtime.unmount()


def test_nested_dialog_owns_tab_without_outer_dialog_moving_focus_again():
    bounds = Rect(0, 0, 120, 40)
    outer_button = Button("Outer", bounds=bounds)
    inner_button = Button("Inner", bounds=bounds)
    inner = Dialog(
        bounds=Rect(0, 0, 400, 300), dialog_bounds=Rect(20, 20, 360, 260), content=inner_button
    )
    outer = Dialog(
        bounds=Rect(0, 0, 500, 400),
        dialog_bounds=Rect(20, 20, 460, 360),
        content=Component().add(outer_button, inner),
    )
    window = Window(width=500, height=400)
    runtime = mount(window, outer)
    try:
        window.focus_component(inner_button)
        for reverse in (False, True):
            tab(window, reverse=reverse)
            assert window.focused_component is inner_button
    finally:
        runtime.unmount()
