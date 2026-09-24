"""Large-document CodeEditor viewport benchmark and regression guard."""

from __future__ import annotations

from time import perf_counter

from swirui import CodeEditor
from swirui.rendering.geometry import Rect
from swirui.rendering.scene import SceneNodeKind

LINES = 20_000
FRAMES = 200


def main() -> None:
    document = "\n".join(
        f"def generated_{index:05d}(): return {index}" for index in range(LINES)
    )
    editor = CodeEditor(
        document,
        bounds=Rect(0.0, 0.0, 1100.0, 620.0),
        font_size=13.0,
        padding=8.0,
    )
    editor.scroll_to_line(LINES // 2)

    start = perf_counter()
    max_nodes = 0
    max_line_number_nodes = 0
    for _ in range(FRAMES):
        scene = editor.build_scene_node()
        nodes = list(scene.walk())
        max_nodes = max(max_nodes, len(nodes))
        max_line_number_nodes = max(
            max_line_number_nodes,
            sum(
                1
                for node in nodes
                if node.kind is SceneNodeKind.TEXT and ":line-number:" in node.key
            ),
        )
    elapsed = perf_counter() - start

    # Retained work must track viewport rows, not the entire source document.
    if max_nodes > 96 or max_line_number_nodes > 48:
        raise RuntimeError(
            "CodeEditor virtualization regression: "
            f"max_nodes={max_nodes}, max_line_number_nodes={max_line_number_nodes}"
        )

    print(
        f"CodeEditor viewport: {LINES} lines, {FRAMES} scene builds, "
        f"{elapsed * 1000.0 / FRAMES:.3f} ms/frame, "
        f"max_nodes={max_nodes}, max_line_number_nodes={max_line_number_nodes}"
    )


if __name__ == "__main__":
    main()
