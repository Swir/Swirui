from types import SimpleNamespace

import pytest

from swirui import Window
from swirui.rendering import Color, Rect, Scene, SceneNode, SceneNodeKind, WgpuRenderer
from swirui.rendering.effect_cache import _clone_tree


def text_node(spans=()):
    return SceneNode(
        key="text",
        kind=SceneNodeKind.TEXT,
        bounds=Rect(0, 0, 100, 30),
        text="Aé😀",
        fill=Color(1, 1, 1),
        text_spans=spans,
        opacity=0.5,
    )


@pytest.mark.parametrize("ranges", [((-1, 1),), ((0, 4),), ((1, 1),), ((0, 2), (1, 3))])
def test_scene_rejects_invalid_color_spans(ranges):
    with pytest.raises(ValueError, match="spans"):
        text_node(tuple((a, b, Color(1, 0, 0)) for a, b in ranges))


def test_rich_payload_preserves_plain_contract_and_applies_opacity_once():
    window = Window()
    node = text_node(((1, 3, Color(1, 0, 0, 0.6)),))
    window.set_scene(Scene(400, 240, node))
    renderer = WgpuRenderer(native_module=SimpleNamespace(supports_text_color_spans=True))
    base, spans = renderer._text_instances(window)[0]
    assert len(base) == 12 and base[0] == "Aé😀" and base[9] == 0.5
    assert spans == [(1, 3, 1, 0, 0, 0.3)]
    node.text_spans = ()
    assert len(renderer._text_instances(window)[0]) == 12


def test_old_native_core_reports_missing_rich_text_support():
    window = Window()
    window.set_scene(Scene(400, 240, text_node(((0, 1, Color(1, 0, 0)),))))
    renderer = WgpuRenderer(native_module=SimpleNamespace())
    with pytest.raises(RuntimeError, match="color spans"):
        renderer._text_instances(window)


def test_effect_clone_preserves_immutable_text_spans():
    node = text_node(((1, 3, Color(1, 0, 0)),))
    clone = _clone_tree(node, "text", "reflection")
    assert clone.text_spans == node.text_spans
    assert clone.key == "reflection"
