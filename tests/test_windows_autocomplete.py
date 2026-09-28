from __future__ import annotations

import sys

import pytest

from swirui.platforms import NativeWindowHandle, PlatformEvent, PlatformEventKind
from swirui.rendering.geometry import Rect
from swirui.rendering.scene import SceneNodeKind
from swirui.widgets.autocomplete import Autocomplete

pytestmark = pytest.mark.skipif(
    sys.platform != "win32",
    reason="Windows-native autocomplete gate",
)

_WINDOW = NativeWindowHandle(1)


def _event(kind: PlatformEventKind, *, key_code: int | None = None) -> PlatformEvent:
    return PlatformEvent(kind=kind, window=_WINDOW, key_code=key_code)


def test_autocomplete_compiles_popup_and_accepts_with_native_core() -> None:
    import _swirui_native as native

    assert native.core_version()
    assert native.enabled_backends()

    control = Autocomplete(
        "Sw",
        bounds=Rect(20.0, 20.0, 420.0, 46.0),
        items=("SwirUI", "SwirEngine", "SwirPhotoClean"),
        accessible_name="Framework autocomplete",
    )
    control.emit("focus_gained")
    scene = control.build_scene_node()
    text_nodes = [
        node
        for node in scene.walk()
        if node.kind is SceneNodeKind.TEXT and ":suggestion:" in node.key
    ]

    assert not scene.clip_to_bounds
    assert [node.text for node in text_nodes] == [
        "SwirUI",
        "SwirEngine",
        "SwirPhotoClean",
    ]

    control.emit(
        "key_down",
        event=_event(PlatformEventKind.KEY_DOWN, key_code=0x28),
    )
    accepted = control.emit(
        "key_down",
        event=_event(PlatformEventKind.KEY_DOWN, key_code=0x0D),
    )
    assert accepted.default_prevented
    assert control.value == "SwirUI"
    assert not control.suggestions_open
