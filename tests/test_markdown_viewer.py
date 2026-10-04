from __future__ import annotations

from swirui import MarkdownViewer
from swirui.platforms import NativeWindowHandle, PlatformEvent, PlatformEventKind
from swirui.rendering.geometry import Rect
from swirui.rendering.scene import SceneNodeKind


_WINDOW = NativeWindowHandle(1)


def _event(
    kind: PlatformEventKind,
    *,
    key_code: int | None = None,
    delta_y: float = 0.0,
) -> PlatformEvent:
    return PlatformEvent(
        kind=kind,
        window=_WINDOW,
        key_code=key_code,
        delta_y=delta_y,
    )


def test_markdown_viewer_sanitizes_remote_media_links_and_raw_markup() -> None:
    viewer = MarkdownViewer(
        """# Safe title

<script>not executed</script>
![remote image](https://example.invalid/pixel.png)
[unsafe target](custom-scheme:payload)
[remote docs](https://example.invalid/docs)
""",
        bounds=Rect(0.0, 0.0, 420.0, 220.0),
    )

    assert "<script>" not in viewer.sanitized_text
    assert "https://example.invalid/pixel.png" not in viewer.sanitized_text
    assert "custom-scheme:payload" not in viewer.sanitized_text
    assert "https://example.invalid/docs" not in viewer.sanitized_text
    assert "[image: remote image]" in viewer.sanitized_text

    scene = viewer.build_scene_node()
    assert scene.hit_testable
    assert scene.clip_to_bounds
    assert all(node.kind is not SceneNodeKind.IMAGE for node in scene.walk())
    assert all("<" not in (node.text or "") for node in scene.walk())


def test_markdown_viewer_supports_headings_lists_quotes_and_code() -> None:
    fence = chr(96) * 3
    source = (
        "# Heading\n\n"
        "- first\n"
        "2. second\n\n"
        "> quoted\n\n"
        f"{fence}python\nprint('safe text')\n{fence}\n"
    )
    viewer = MarkdownViewer(source, bounds=Rect(0.0, 0.0, 360.0, 260.0))
    scene = viewer.build_scene_node()
    texts = [
        node.text
        for node in scene.walk()
        if node.kind is SceneNodeKind.TEXT and node.text is not None
    ]

    assert any("Heading" in text for text in texts)
    assert any("first" in text for text in texts)
    assert any("quoted" in text for text in texts)
    assert any(node.kind is SceneNodeKind.TEXT and node.text == "quoted" and node.bounds.x > scene.bounds.x for node in scene.walk())
    assert any("print('safe text')" in text for text in texts)
    assert all(
        not node.hit_testable
        for node in scene.walk()
        if node.kind is SceneNodeKind.TEXT
    )
    assert viewer.block_count == 5


def test_markdown_viewer_scene_stays_bounded_for_large_documents() -> None:
    source = "\n\n".join(
        f"## Item {index}\nA retained paragraph for item {index}." for index in range(1200)
    )
    viewer = MarkdownViewer(
        source,
        bounds=Rect(0.0, 0.0, 520.0, 220.0),
        max_blocks=3000,
        max_chars=1_000_000,
        max_scene_nodes=48,
    )

    scene = viewer.build_scene_node()
    assert viewer.content_height > viewer.bounds.height
    assert len(scene.children) <= 48
    assert viewer.scroll_to(viewer.max_scroll_y)
    assert len(viewer.build_scene_node().children) <= 48


def test_markdown_viewer_reflows_when_width_changes_and_clamps_scroll() -> None:
    text = " ".join(["responsive markdown content"] * 80)
    viewer = MarkdownViewer(text, bounds=Rect(0.0, 0.0, 700.0, 180.0))
    wide_height = viewer.content_height

    viewer.bounds = Rect(0.0, 0.0, 220.0, 180.0)
    narrow_height = viewer.content_height
    assert narrow_height > wide_height

    viewer.scroll_to(10_000_000.0)
    assert viewer.scroll_y == viewer.max_scroll_y
    viewer.bounds = Rect(0.0, 0.0, 900.0, 500.0)
    viewer.build_scene_node()
    assert 0.0 <= viewer.scroll_y <= viewer.max_scroll_y


def test_markdown_viewer_reports_input_limits_without_unbounded_state() -> None:
    source = "\n\n".join(f"paragraph {index}" for index in range(50))
    viewer = MarkdownViewer(
        source,
        bounds=Rect(0.0, 0.0, 320.0, 140.0),
        max_blocks=8,
        max_chars=10_000,
    )

    assert viewer.block_count == 8
    assert viewer.truncated
    assert viewer.accessible_value_text is not None
    assert "truncated" in viewer.accessible_value_text


def test_markdown_viewer_preserves_code_indentation_and_repeated_spaces() -> None:
    fence = chr(96) * 3
    viewer = MarkdownViewer(
        f"{fence}python\n    if ready:\n        value  =  42\n{fence}",
        bounds=Rect(0.0, 0.0, 700.0, 220.0),
    )
    scene = viewer.build_scene_node()
    code_text = [
        node.text
        for node in scene.walk()
        if node.kind is SceneNodeKind.TEXT and node.text is not None
    ]
    assert "    if ready:" in code_text
    assert "        value  =  42" in code_text


def test_markdown_viewer_long_unbroken_token_stays_bounded() -> None:
    viewer = MarkdownViewer(
        "x" * 200_000,
        bounds=Rect(0.0, 0.0, 360.0, 180.0),
        max_chars=250_000,
        max_scene_nodes=32,
    )
    scene = viewer.build_scene_node()
    assert viewer.content_height > viewer.bounds.height
    assert len(scene.children) <= 32


def test_markdown_viewer_accessibility_tracks_scroll_range() -> None:
    viewer = MarkdownViewer(
        "\n\n".join(f"paragraph {index}" for index in range(120)),
        bounds=Rect(0.0, 0.0, 320.0, 120.0),
    )
    assert viewer.max_scroll_y > 0.0
    assert viewer.accessible_min_value == 0.0
    assert viewer.accessible_max_value == viewer.max_scroll_y
    assert viewer.scroll_to(viewer.max_scroll_y)
    assert viewer.accessible_value == viewer.max_scroll_y
    assert viewer.accessible_value_text is not None
    assert "markdown blocks" in viewer.accessible_value_text


def test_markdown_viewer_scalar_width_cache_stays_bounded() -> None:
    source = "".join(chr(0x400 + index) for index in range(600))
    viewer = MarkdownViewer(
        source,
        bounds=Rect(0.0, 0.0, 240.0, 120.0),
        max_chars=5_000,
    )
    _ = viewer.content_height
    assert len(viewer._scalar_width_cache) <= 256


def test_markdown_viewer_large_prose_wrap_uses_bounded_scalar_cache() -> None:
    viewer = MarkdownViewer(
        ("alpha beta gamma delta " * 20_000).strip(),
        bounds=Rect(0.0, 0.0, 360.0, 180.0),
        max_chars=500_000,
        max_scene_nodes=32,
    )
    scene = viewer.build_scene_node()
    assert viewer.content_height > viewer.bounds.height
    assert len(scene.children) <= 32
    assert len(viewer._scalar_width_cache) <= 256


def test_markdown_viewer_pointer_scroll_consumes_then_bubbles_at_boundary() -> None:
    viewer = MarkdownViewer(
        "\n\n".join(f"paragraph {index}" for index in range(200)),
        bounds=Rect(0.0, 0.0, 360.0, 120.0),
    )
    assert viewer.max_scroll_y > 96.0

    scroll = viewer.emit(
        "pointer_scroll",
        event=_event(PlatformEventKind.POINTER_SCROLL, delta_y=48.0),
    )
    assert scroll.default_prevented
    assert viewer.scroll_y == 48.0
    assert scroll.data["remaining_scroll_delta_y"] == 0.0

    viewer.scroll_to(viewer.max_scroll_y)
    boundary = viewer.emit(
        "pointer_scroll",
        event=_event(PlatformEventKind.POINTER_SCROLL, delta_y=72.0),
    )
    assert not boundary.default_prevented
    assert boundary.data["remaining_scroll_delta_y"] == 72.0


def test_markdown_viewer_keyboard_navigation_is_bounded_and_prevents_default() -> None:
    viewer = MarkdownViewer(
        "\n\n".join(f"paragraph {index}" for index in range(200)),
        bounds=Rect(0.0, 0.0, 360.0, 120.0),
    )

    page_down = viewer.emit(
        "key_down",
        event=_event(PlatformEventKind.KEY_DOWN, key_code=0x22),
    )
    assert page_down.default_prevented
    assert viewer.scroll_y > 0.0

    end = viewer.emit(
        "key_down",
        event=_event(PlatformEventKind.KEY_DOWN, key_code=0x23),
    )
    assert end.default_prevented
    assert viewer.scroll_y == viewer.max_scroll_y

    home = viewer.emit(
        "key_down",
        event=_event(PlatformEventKind.KEY_DOWN, key_code=0x24),
    )
    assert home.default_prevented
    assert viewer.scroll_y == 0.0


def test_markdown_replacement_resets_scroll_and_accessibility_state() -> None:
    viewer = MarkdownViewer(
        "\n\n".join(f"paragraph {index}" for index in range(200)),
        bounds=Rect(0.0, 0.0, 360.0, 120.0),
    )
    viewer.scroll_to(viewer.max_scroll_y)
    assert viewer.scroll_y > 0.0

    viewer.markdown = "# Replacement\n\nshort document"
    assert viewer.scroll_y == 0.0
    assert viewer.block_count == 2
    assert viewer.accessible_value == 0.0
    assert "2 markdown blocks" in (viewer.accessible_value_text or "")
