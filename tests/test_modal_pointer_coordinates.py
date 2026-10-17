from swirui import CommandItem, CommandPalette, ContextMenu, Modal, Window, mount
from swirui.platforms import NativeWindowHandle, PlatformEvent, PlatformEventKind, PointerButton
from swirui.rendering import Rect


def pointer(window, kind, x, y):
    window._apply_platform_event(
        PlatformEvent(kind, NativeWindowHandle(1), x=x, y=y, button=PointerButton.LEFT)
    )


def test_modal_palette_header_click_does_not_invoke_a_result():
    palette = CommandPalette(
        [CommandItem(i, f"Action {i}") for i in range(10)],
        bounds=Rect(0, 0, 400, 200),
        dismiss_on_invoke=False,
    )
    modal = Modal(
        bounds=Rect(0, 0, 800, 600), dialog_bounds=Rect(200, 120, 400, 200), content=palette
    )
    window = Window(width=800, height=600)
    runtime = mount(window, modal)
    invoked = []
    palette.on("command_invoked", lambda e: invoked.append(e.data["key"]))
    try:
        pointer(window, PlatformEventKind.POINTER_DOWN, 220, 135)
        assert not invoked and modal.is_open and window.focused_component is palette
        pointer(window, PlatformEventKind.POINTER_DOWN, 220, 180)
        assert invoked == [0]
    finally:
        runtime.unmount()


def test_nested_modal_target_and_ancestor_observers_use_their_own_coordinates():
    menu = ContextMenu(
        [CommandItem(i, f"Action {i}") for i in range(3)],
        bounds=Rect(0, 0, 240, 120),
        dismiss_on_invoke=False,
    )
    inner = Modal(bounds=Rect(0, 0, 400, 200), dialog_bounds=Rect(80, 40, 240, 120), content=menu)
    outer = Modal(
        bounds=Rect(0, 0, 800, 600), dialog_bounds=Rect(200, 120, 400, 200), content=inner
    )
    observed = []
    for control, label in ((outer, "outer"), (inner, "inner"), (menu, "menu")):
        control.on(
            "pointer_down",
            lambda e, label=label: observed.append((label, e.data["event"].x, e.data["event"].y)),
            capture=True,
        )
    menu.on(
        "pointer_enter", lambda e: observed.append(("enter", e.data["event"].x, e.data["event"].y))
    )
    window = Window(width=800, height=600)
    runtime = mount(window, outer)
    try:
        pointer(window, PlatformEventKind.POINTER_MOVE, 300, 206)
        pointer(window, PlatformEventKind.POINTER_DOWN, 300, 206)
        assert menu.active_item.key == 1 and outer.is_open and inner.is_open
        assert ("outer", 300, 206) in observed
        assert ("inner", 100, 86) in observed
        assert ("menu", 20, 46) in observed
        assert ("enter", 20, 46) in observed
    finally:
        runtime.unmount()


def test_modal_pointer_capture_tracks_dialog_move_and_preserves_window_event():
    menu = ContextMenu([CommandItem("a", "Action")], bounds=Rect(0, 0, 240, 120))
    modal = Modal(bounds=Rect(0, 0, 800, 600), dialog_bounds=Rect(200, 120, 240, 120), content=menu)
    window = Window(width=800, height=600)
    runtime = mount(window, modal)
    coordinates = []
    menu.on(
        "pointer_move",
        lambda e: coordinates.append(
            (
                e.data["event"].x,
                e.data["event"].y,
                e.data["window_event"].x,
                e.data["window_event"].y,
            )
        ),
    )
    try:
        window.capture_pointer(menu)
        modal.dialog_bounds = Rect(220, 130, 240, 120)
        pointer(window, PlatformEventKind.POINTER_MOVE, 100, 100)
        assert coordinates == [(-120, -30, 100, 100)]
        assert window.pointer_capture_component is menu
        pointer(window, PlatformEventKind.POINTER_UP, 100, 100)
        assert window.pointer_capture_component is None
    finally:
        runtime.unmount()
