from __future__ import annotations

import sys

import pytest

from swirui import CodeEditor
from swirui.rendering.geometry import Rect
from swirui.rendering.scene import SceneNodeKind

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows-native code editor gate")


def test_code_editor_compiles_retained_gutter_and_text_with_installed_native_core() -> None:
    import _swirui_native as native

    assert native.core_version()
    assert native.enabled_backends()

    editor = CodeEditor(
        "from swirui import App\n\napp = App(name=\"Editor\")",
        bounds=Rect(0.0, 0.0, 760.0, 320.0),
        font_family="Consolas",
        accessible_name="Windows code editor",
    )
    editor.select(len("from swirui import App\n\n"), len("from swirui import App\n\n"))
    scene = editor.build_scene_node()

    assert scene.clip_to_bounds
    text_nodes = [node for node in scene.walk() if node.kind is SceneNodeKind.TEXT]
    assert any(":line-number:" in node.key for node in text_nodes)
    assert any((node.text or "").startswith("from swirui") for node in text_nodes)
    assert any(node.key.endswith(":current-line") for node in scene.walk())
    assert "caret line 3" in (editor.accessible_value_text or "")
