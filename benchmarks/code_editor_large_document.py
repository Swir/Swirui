"""Large-document CodeEditor + syntax-highlighting regression guard."""

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
        language="python",
    )
    editor.scroll_to_line(LINES // 2)

    start = perf_counter()
    max_nodes = 0
    max_line_number_nodes = 0
    max_syntax_nodes = 0
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
        max_syntax_nodes = max(
            max_syntax_nodes,
            sum(1 for node in nodes if ":syntax:" in node.key),
        )
    elapsed = perf_counter() - start

    # Retained work must track visible rows/tokens, not the entire source file.
    if max_nodes > 256 or max_line_number_nodes > 48 or max_syntax_nodes > 192:
        raise RuntimeError(
            "CodeEditor syntax virtualization regression: "
            f"max_nodes={max_nodes}, line_numbers={max_line_number_nodes}, "
            f"syntax_nodes={max_syntax_nodes}"
        )

    print(
        f"CodeEditor syntax viewport: {LINES} lines, {FRAMES} scene builds, "
        f"{elapsed * 1000.0 / FRAMES:.3f} ms/frame, "
        f"max_nodes={max_nodes}, syntax_nodes={max_syntax_nodes}"
    )


if __name__ == "__main__":
    main()
