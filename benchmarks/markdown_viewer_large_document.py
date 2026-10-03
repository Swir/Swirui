from __future__ import annotations

from time import perf_counter

from swirui import MarkdownViewer
from swirui.rendering.geometry import Rect
from swirui.rendering.scene import SceneNodeKind


def main() -> None:
    source = "\n\n".join(
        f"## Entry {index}\nSafe local Markdown line {index}." for index in range(20_000)
    )
    started = perf_counter()
    viewer = MarkdownViewer(
        source,
        bounds=Rect(0.0, 0.0, 720.0, 360.0),
        max_blocks=45_000,
        max_chars=2_500_000,
        max_scene_nodes=96,
    )
    scene = viewer.build_scene_node()
    assert scene.clip_to_bounds
    assert scene.kind is SceneNodeKind.RECTANGLE
    elapsed_ms = (perf_counter() - started) * 1000.0

    assert viewer.block_count == 40_000
    assert not viewer.truncated
    assert viewer.content_height > viewer.bounds.height
    assert len(scene.children) <= 96
    assert len({child.key for child in scene.children}) == len(scene.children)
    viewer.scroll_to(viewer.max_scroll_y)
    bottom_started = perf_counter()
    bottom_scene = viewer.build_scene_node()
    bottom_render_ms = (perf_counter() - bottom_started) * 1000.0
    assert len(bottom_scene.children) <= 96

    repeat_started = perf_counter()
    for _ in range(50):
        assert len(viewer.build_scene_node().children) <= 96
    repeat_bottom_ms = (perf_counter() - repeat_started) * 1000.0

    print(
        f"markdown_viewer_20k_entries elapsed_ms={elapsed_ms:.1f} "
        f"bottom_render_ms={bottom_render_ms:.3f} "
        f"repeat_bottom_50_ms={repeat_bottom_ms:.1f} "
        f"scene_nodes={len(scene.children)} blocks={viewer.block_count}"
    )


if __name__ == "__main__":
    main()
