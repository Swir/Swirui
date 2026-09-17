from __future__ import annotations

import pytest

from swirui import (
    AccessibilityRole,
    Button,
    Component,
    Dialog,
    DialogResult,
    Window,
    build_accessibility_tree,
)
from swirui.platforms import NativeWindowHandle, PlatformEvent, PlatformEventKind, PointerButton
from swirui.rendering import Rect
from swirui.widgets import compile_component_scene


def _window_with_dialog(*, accept_on_enter: bool = False) -> tuple[Window, Component, Button, Dialog, Button, Button]:
    root = Component("root", key="root")
    outside = Button("Outside", key="outside", bounds=Rect(20.0, 20.0, 120.0, 40.0))
    dialog = Dialog(
        "Delete project?",
        key="delete-dialog",
        bounds=Rect(0.0, 0.0, 640.0, 360.0),
        panel_bounds=Rect(150.0, 80.0, 340.0, 190.0),
        accept_on_enter=accept_on_enter,
    )
    cancel = Button("Cancel", key="cancel", bounds=Rect(28.0, 116.0, 120.0, 42.0))
    confirm = Button("Delete", key="confirm", bounds=Rect(170.0, 116.0, 120.0, 42.0))
    dialog.add(cancel, confirm)
    root.add(outside, dialog)
    window = Window("Dialog test", width=640, height=360)
    window.set_root(root)
    return window, root, outside, dialog, cancel, confirm


def _key(window: Window, key_code: int, *, shift: bool = False) -> None:
    window._apply_platform_event(
        PlatformEvent(
            PlatformEventKind.KEY_DOWN,
            NativeWindowHandle(1),
            key_code=key_code,
            shift=shift,
        )
    )


def _pointer(window: Window, kind: PlatformEventKind, x: float, y: float) -> None:
    window._apply_platform_event(
        PlatformEvent(
            kind,
            NativeWindowHandle(1),
            x=x,
            y=y,
            button=PointerButton.LEFT,
        )
    )


def test_dialog_starts_hidden_and_open_establishes_focus_trap() -> None:
    window, _root, outside, dialog, cancel, confirm = _window_with_dialog()
    window.focus_component(outside)

    assert dialog.visible is False
    assert dialog.is_open is False

    dialog.open(window, initial_focus=confirm)

    assert dialog.visible is True
    assert dialog.is_open is True
    assert dialog.result is None
    assert window.focused_component is confirm
    assert dialog.accessibility_role is AccessibilityRole.DIALOG

    window.focus_component(outside)
    assert window.focused_component is cancel


def test_dialog_tab_and_shift_tab_cycle_inside_modal_subtree() -> None:
    window, _root, outside, dialog, cancel, confirm = _window_with_dialog()
    window.focus_component(outside)
    dialog.open(window, initial_focus=cancel)

    _key(window, 0x09)
    assert window.focused_component is confirm

    _key(window, 0x09)
    assert window.focused_component is cancel

    _key(window, 0x09, shift=True)
    assert window.focused_component is confirm


def test_escape_cancels_dialog_and_restores_previous_focus() -> None:
    window, _root, outside, dialog, cancel, _confirm = _window_with_dialog()
    window.focus_component(outside)
    closed: list[DialogResult] = []
    dialog.on("closed", lambda event: closed.append(event.data["result"]))
    dialog.open(window, initial_focus=cancel)

    _key(window, 0x1B)

    assert dialog.visible is False
    assert dialog.is_open is False
    assert dialog.result is DialogResult.CANCELLED
    assert window.focused_component is outside
    assert closed == [DialogResult.CANCELLED]


def test_enter_can_accept_dialog_when_explicitly_enabled() -> None:
    window, _root, outside, dialog, cancel, _confirm = _window_with_dialog(
        accept_on_enter=True
    )
    window.focus_component(outside)
    dialog.open(window, initial_focus=cancel)

    _key(window, 0x0D)

    assert dialog.result is DialogResult.ACCEPTED
    assert dialog.visible is False
    assert window.focused_component is outside


def test_scrim_click_dismisses_but_panel_click_does_not() -> None:
    window, root, outside, dialog, cancel, _confirm = _window_with_dialog()
    window.focus_component(outside)
    dialog.open(window, initial_focus=cancel)
    scene = compile_component_scene(root, width=640.0, height=360.0)
    assert scene is not None
    window.set_scene(scene)

    _pointer(window, PlatformEventKind.POINTER_DOWN, 40.0, 300.0)
    _pointer(window, PlatformEventKind.POINTER_UP, 40.0, 300.0)
    assert dialog.result is DialogResult.DISMISSED
    assert dialog.visible is False
    assert window.focused_component is outside

    dialog.open(window, initial_focus=cancel)
    scene = compile_component_scene(root, width=640.0, height=360.0)
    assert scene is not None
    window.set_scene(scene)
    _pointer(window, PlatformEventKind.POINTER_DOWN, 300.0, 150.0)
    _pointer(window, PlatformEventKind.POINTER_UP, 300.0, 150.0)
    assert dialog.is_open is True
    assert dialog.result is None


def test_dialog_child_geometry_is_panel_local_and_clipped() -> None:
    window, root, _outside, dialog, cancel, _confirm = _window_with_dialog()
    dialog.open(window, initial_focus=cancel)

    scene = compile_component_scene(root, width=640.0, height=360.0)
    assert scene is not None
    cancel_node = next(node for node in scene.walk() if node.key == "cancel")
    wrapper = next(
        node for node in scene.walk() if node.key == "delete-dialog:content:0"
    )

    assert cancel.bounds == Rect(28.0, 116.0, 120.0, 42.0)
    assert cancel_node.bounds == Rect(178.0, 196.0, 120.0, 42.0)
    assert wrapper.bounds == dialog.panel_bounds
    assert wrapper.clip_to_bounds is True


def test_dialog_accessibility_tree_only_exposes_open_modal() -> None:
    window, root, _outside, dialog, cancel, _confirm = _window_with_dialog()
    closed_tree = build_accessibility_tree(root)
    assert closed_tree is not None
    assert closed_tree.find(dialog.key) is None

    dialog.open(window, initial_focus=cancel)
    open_tree = build_accessibility_tree(root, focused=window.focused_component)
    assert open_tree is not None
    dialog_node = open_tree.find(dialog.key)
    assert dialog_node is not None
    assert dialog_node.role is AccessibilityRole.DIALOG
    assert dialog_node.name == "Delete project?"
    assert dialog_node.find("cancel") is not None


def test_dialog_rejects_foreign_initial_focus() -> None:
    window, _root, outside, dialog, _cancel, _confirm = _window_with_dialog()

    with pytest.raises(ValueError, match="dialog subtree"):
        dialog.open(window, initial_focus=outside)


def test_dialog_rejects_panel_outside_modal_bounds() -> None:
    with pytest.raises(ValueError, match="fully contained"):
        Dialog(
            "Invalid",
            bounds=Rect(0.0, 0.0, 200.0, 120.0),
            panel_bounds=Rect(80.0, 40.0, 180.0, 90.0),
        )
