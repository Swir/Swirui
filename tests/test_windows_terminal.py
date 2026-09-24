from __future__ import annotations

import importlib
import sys

import pytest

from swirui import Terminal
from swirui.rendering.geometry import Rect
from swirui.rendering.scene import SceneNodeKind

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows-native terminal gate")


def test_terminal_compiles_retained_text_with_installed_native_core() -> None:
    native = importlib.import_module("swirui._swirui_native")
    assert native.core_version()
    assert native.enabled_backends()

    terminal = Terminal(
        bounds=Rect(0.0, 0.0, 640.0, 220.0),
        font_family="Consolas",
        accessible_name="Windows terminal",
    )
    terminal.writeln("\x1b[32mWindows retained terminal ready\x1b[0m")
    scene = terminal.build_scene_node()

    assert scene.clip_to_bounds
    text_nodes = [node for node in scene.walk() if node.kind is SceneNodeKind.TEXT]
    assert any(node.text == "Windows retained terminal ready" for node in text_nodes)
    assert terminal.accessible_value_text is not None
