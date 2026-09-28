"""Keyboard-first retained Autocomplete demo."""

from __future__ import annotations

from swirui.rendering.geometry import Rect
from swirui.widgets.autocomplete import Autocomplete


def main() -> None:
    control = Autocomplete(
        "Sw",
        bounds=Rect(24.0, 24.0, 420.0, 46.0),
        items=(
            "SwirUI",
            "SwirEngine",
            "SwirPhotoClean",
            "SwirPhoneOS",
            "SwirRoot",
        ),
        max_suggestions=4,
        accessible_name="SWIR project autocomplete",
    )
    control.open_suggestions()
    scene = control.build_scene_node()

    print(
        "Autocomplete "
        f"value={control.value!r}, suggestions={control.suggestions}, "
        f"retained_nodes={sum(1 for _ in scene.walk())}"
    )
    print(control.accessible_value_text)


if __name__ == "__main__":
    main()
