"""Large-source Autocomplete retained-popup regression guard."""

from __future__ import annotations

from time import perf_counter

from swirui.rendering.geometry import Rect
from swirui.widgets.autocomplete import Autocomplete

ITEMS = 20_000
FRAMES = 40


def main() -> None:
    values = tuple(f"item-{index:05d}" for index in range(ITEMS))
    control = Autocomplete(
        "item-19",
        bounds=Rect(0.0, 0.0, 520.0, 44.0),
        items=values,
        max_suggestions=8,
    )
    control.open_suggestions()

    start = perf_counter()
    max_nodes = 0
    max_suggestion_nodes = 0
    for _ in range(FRAMES):
        control.refresh_suggestions()
        scene = control.build_scene_node()
        nodes = list(scene.walk())
        max_nodes = max(max_nodes, len(nodes))
        max_suggestion_nodes = max(
            max_suggestion_nodes,
            sum(1 for node in nodes if ":suggestion:" in node.key),
        )
    elapsed = perf_counter() - start

    if len(control.suggestions) > 8:
        raise RuntimeError(
            f"Autocomplete suggestion cap regression: {len(control.suggestions)}"
        )
    if max_nodes > 32 or max_suggestion_nodes > 16:
        raise RuntimeError(
            "Autocomplete retained-popup regression: "
            f"max_nodes={max_nodes}, suggestion_nodes={max_suggestion_nodes}"
        )
    if elapsed > 5.0:
        raise RuntimeError(
            "Autocomplete source filtering regression: "
            f"{elapsed:.3f}s for {FRAMES} frames"
        )

    print(
        f"Autocomplete source: {ITEMS} items, {FRAMES} refresh/build cycles, "
        f"{elapsed * 1000.0 / FRAMES:.3f} ms/frame, "
        f"max_nodes={max_nodes}, suggestions={len(control.suggestions)}"
    )


if __name__ == "__main__":
    main()
