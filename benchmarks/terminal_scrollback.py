"""Terminal scrollback virtualization benchmark and regression guard."""

from __future__ import annotations

from time import perf_counter

from swirui import Terminal
from swirui.rendering.geometry import Rect
from swirui.rendering.scene import SceneNodeKind

LINES = 5_000
FRAMES = 250


def main() -> None:
    terminal = Terminal(
        bounds=Rect(0.0, 0.0, 960.0, 420.0),
        max_lines=LINES,
        font_size=13.0,
    )
    for index in range(LINES):
        terminal.writeln(f"[{index:05d}] retained terminal benchmark payload")

    start = perf_counter()
    max_text_nodes = 0
    for _ in range(FRAMES):
        scene = terminal.build_scene_node()
        text_nodes = sum(1 for node in scene.walk() if node.kind is SceneNodeKind.TEXT)
        max_text_nodes = max(max_text_nodes, text_nodes)
    elapsed = perf_counter() - start

    # Rendering work must track viewport rows, never the entire scrollback.
    if max_text_nodes > 32:
        raise RuntimeError(
            f"Terminal virtualization regression: {max_text_nodes} text nodes for one frame."
        )

    print(
        f"Terminal scrollback: {LINES} lines, {FRAMES} scene builds, "
        f"{elapsed * 1000.0 / FRAMES:.3f} ms/frame, max_text_nodes={max_text_nodes}"
    )


if __name__ == "__main__":
    main()
