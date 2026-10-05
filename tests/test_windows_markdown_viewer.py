from __future__ import annotations

import math
import sys

import pytest

import swirui
from swirui import MarkdownViewer
from swirui.rendering.geometry import Rect
from swirui.rendering.scene import SceneNodeKind
from swirui.widgets import MarkdownViewer as WidgetsMarkdownViewer

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows-native Markdown gate")


def test_markdown_viewer_public_api_and_native_core_contract() -> None:
    import _swirui_native as native

    assert native.core_version()
    assert native.enabled_backends()
    assert swirui.MarkdownViewer is MarkdownViewer
    assert WidgetsMarkdownViewer is MarkdownViewer

    viewer = MarkdownViewer(
        "# Native Markdown\n\n- retained\n- bounded\n- local-only",
        bounds=Rect(0.0, 0.0, 640.0, 260.0),
        accessible_name="Windows Markdown viewer",
    )
    scene = viewer.build_scene_node()

    assert scene.clip_to_bounds
    text_nodes = [node for node in scene.walk() if node.kind is SceneNodeKind.TEXT]
    assert any(node.text == "Native Markdown" for node in text_nodes)
    assert viewer.accessible_value_text is not None


def test_markdown_viewer_fractional_dip_resize_reflows_on_windows() -> None:
    source = " ".join(["fractional DPI-safe retained markdown"] * 280)
    viewer = MarkdownViewer(
        source,
        bounds=Rect(0.25, 0.5, 641.5, 260.25),
        font_size=15.5,
        max_scene_nodes=40,
    )

    wide_height = viewer.content_height
    wide_scene = viewer.build_scene_node()
    assert len(wide_scene.children) <= 40

    viewer.bounds = Rect(0.25, 0.5, 239.75, 260.25)
    narrow_height = viewer.content_height
    narrow_scene = viewer.build_scene_node()

    assert narrow_height > wide_height
    assert len(narrow_scene.children) <= 40
    assert all(
        math.isfinite(value)
        for node in narrow_scene.walk()
        for value in (node.bounds.x, node.bounds.y, node.bounds.width, node.bounds.height)
    )
    assert viewer.accessible_max_value == viewer.max_scroll_y
