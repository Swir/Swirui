import pytest

from swirui import FUTURE_LIGHT, CommandItem, CommandPalette, ContextMenu, Modal, Window, mount
from swirui.platforms import NativeWindowHandle, PlatformEvent, PlatformEventKind, PointerButton
from swirui.rendering import Rect


def send(window, kind, **kwargs):
    window._apply_platform_event(PlatformEvent(kind, NativeWindowHandle(1), **kwargs))


@pytest.mark.parametrize("kind", [ContextMenu, CommandPalette])
def test_wheel_scroll_reveals_later_commands_without_changing_selection(kind):
    control = kind(
        [CommandItem(i, f"Action {i}") for i in range(1000)],
        bounds=Rect(20, 20, 400, 240),
        dismiss_on_invoke=False,
    )
    window = Window(width=500, height=300)
    runtime = mount(window, control)
    try:
        send(window, PlatformEventKind.POINTER_SCROLL, x=80, y=140, delta_y=400.5)
        scene = control.build_scene_node()
        assert any(n.text == "Action 10" for n in scene.walk())
        assert control.scroll_offset == 400.5 and control.active_item.key == 0
        control.theme = FUTURE_LIGHT
        assert control.scroll_offset == 400.5
        assert len(list(control.build_scene_node().walk())) < 80
        window.focus_component(control)
        send(window, PlatformEventKind.KEY_DOWN, key_code=0x24)
        assert control.scroll_offset == 0 and control.active_item.key == 0
    finally:
        runtime.unmount()


@pytest.mark.parametrize("kind", [ContextMenu, CommandPalette])
def test_modal_scrollbar_drag_pages_and_clicks_exact_result(kind):
    control = kind(
        [CommandItem(i, f"Action {i}") for i in range(1000)],
        bounds=Rect(0, 0, 400, 240),
        dismiss_on_invoke=False,
    )
    modal = Modal(
        bounds=Rect(0, 0, 800, 600), dialog_bounds=Rect(180, 100, 400, 240), content=control
    )
    window = Window(width=800, height=600)
    runtime = mount(window, modal)
    invoked = []
    control.on("command_invoked", lambda e: invoked.append(e.data["key"]))
    try:
        thumb = next(n.bounds for n in window.scene.walk() if n.key.endswith(":scrollbar:thumb"))
        send(
            window,
            PlatformEventKind.POINTER_DOWN,
            x=thumb.x + 2,
            y=thumb.y + 4,
            button=PointerButton.LEFT,
        )
        assert window.pointer_capture_component is control and not invoked
        send(window, PlatformEventKind.POINTER_MOVE, x=thumb.x + 2, y=500)
        send(window, PlatformEventKind.POINTER_UP, x=thumb.x + 2, y=500, button=PointerButton.LEFT)
        assert window.pointer_capture_component is None
        row = control.row_bounds(999)
        send(
            window,
            PlatformEventKind.POINTER_DOWN,
            x=200,
            y=100 + row.y + 12,
            button=PointerButton.LEFT,
        )
        assert invoked == [999] and control.active_item.key == 999 and modal.is_open
        assert len(list(control.build_scene_node().walk())) < 80
    finally:
        runtime.unmount()


def test_fractional_scroll_clips_rows_below_query_and_preserves_offset_on_resize():
    palette = CommandPalette(
        [CommandItem(i, f"Action {i}") for i in range(100)],
        bounds=Rect(10, 20, 400, 300),
        max_visible_rows=3,
    )
    palette.scroll_by(21.25)
    scene = palette.build_scene_node()
    rows = next(n for n in scene.children if n.key.endswith(":rows"))
    assert rows.clip_to_bounds and rows.bounds.y == 68 and rows.bounds.height == 120
    assert len(rows.children) == 4  # two partial rows plus two full rows
    assert rows.children[0].bounds.y < rows.bounds.y
    palette.bounds = Rect(10, 20, 440, 240)
    assert palette.scroll_offset == 21.25
    palette.set_query("Action 99")
    assert palette.scroll_offset == 0
    assert not any(":scrollbar:" in n.key for n in palette.build_scene_node().walk())


@pytest.mark.parametrize("kind", [ContextMenu, CommandPalette])
def test_scroll_boundary_bubbles_only_unconsumed_motion(kind):
    control = kind([CommandItem(i, f"Action {i}") for i in range(20)], bounds=Rect(0, 0, 400, 240))
    modal = Modal(
        bounds=Rect(0, 0, 800, 600), dialog_bounds=Rect(180, 100, 400, 240), content=control
    )
    remaining = []
    modal.on(
        "pointer_scroll",
        lambda e: remaining.append(
            (e.data["remaining_scroll_delta_y"], e.data["event"].x, e.data["event"].y)
        ),
    )
    window = Window(width=800, height=600)
    runtime = mount(window, modal)
    try:
        control.scroll_by(1_000_000)
        maximum = control.scroll_offset
        control.scroll_by(-10)
        send(window, PlatformEventKind.POINTER_SCROLL, x=200, y=250, delta_y=35)
        assert control.scroll_offset == maximum and remaining == [(25, 200, 250)]
    finally:
        runtime.unmount()


@pytest.mark.parametrize("kind", [ContextMenu, CommandPalette])
def test_keyboard_selection_is_kept_visible_after_viewport_shrinks(kind):
    control = kind(
        [CommandItem(i, f"Action {i}") for i in range(20)],
        bounds=Rect(0, 0, 400, 280),
        dismiss_on_invoke=False,
    )
    control.activate_key(19)
    control.bounds = Rect(0, 0, 400, 200)
    row = control.row_bounds(19)
    assert row.bottom <= 200 and row.y >= (48 if kind is CommandPalette else 0)
