"""Show content-driven retained sizing and constrained text reflow."""

from swirui import Button, Column, CrossAxisAlignment, Insets, Label, Row, Window, mount
from swirui.rendering import Rect


def build_demo() -> tuple[Window, Column]:
    title = Label(
        "SwirUI intrinsic sizing",
        key="title",
        bounds=Rect(0.0, 0.0, 40.0, 24.0),
        font_size=28.0,
    )
    copy = Label(
        "Text now contributes a content-aware desired size and reflows when a layout "
        "container constrains the available width.",
        key="copy",
        bounds=Rect(0.0, 0.0, 80.0, 24.0),
        font_size=18.0,
    )
    action = Button(
        "Continue with SwirUI",
        key="action",
        bounds=Rect(0.0, 0.0, 60.0, 40.0),
        font_size=17.0,
        padding=16.0,
    )

    split = Row(
        key="split",
        bounds=Rect(0.0, 0.0, 1.0, 140.0),
        spacing=16.0,
        cross_alignment=CrossAxisAlignment.START,
    )
    split.add(
        Label(
            "A long left label demonstrates a second measurement after Row resolves "
            "the final main-axis width.",
            key="left",
            bounds=Rect(0.0, 0.0, 30.0, 20.0),
            font_size=16.0,
        ),
        Label(
            "The right label independently reflows without overwriting its authored "
            "preferred size.",
            key="right",
            bounds=Rect(0.0, 0.0, 30.0, 20.0),
            font_size=16.0,
        ),
    )

    root = Column(
        key="root",
        bounds=Rect(0.0, 0.0, 1.0, 1.0),
        fill_viewport=True,
        padding=Insets.symmetric(horizontal=32.0, vertical=28.0),
        spacing=18.0,
        cross_alignment=CrossAxisAlignment.START,
    )
    root.add(title, copy, action, split)
    return Window(title="SwirUI — Intrinsic Sizing", width=760, height=520), root


if __name__ == "__main__":
    window, root = build_demo()
    runtime = mount(window, root)
    print(f"Scene generation: {runtime.generation}")
    print(f"Measured root: {root.measure(window.logical_size)}")
