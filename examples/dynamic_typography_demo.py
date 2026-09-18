"""Show one retained type hierarchy adapting across responsive viewport classes."""

from swirui import (
    Button,
    Column,
    CrossAxisAlignment,
    DynamicTypography,
    Input,
    Insets,
    Label,
    ResponsiveValue,
    Window,
    mount,
)
from swirui.rendering import Rect


def build_demo() -> tuple[Window, DynamicTypography]:
    title = Label(
        "SwirUI dynamic typography",
        key="dynamic-type-title",
        bounds=Rect(0.0, 0.0, 260.0, 42.0),
        font_size=32.0,
    )
    copy = Label(
        "Resize through compact, desktop and ultrawide widths. The same retained text "
        "hierarchy is remeasured before layout and rendered through shaped GPU text.",
        key="dynamic-type-copy",
        bounds=Rect(0.0, 0.0, 420.0, 56.0),
        font_size=18.0,
    )
    field = Input(
        "Responsive input text",
        key="dynamic-type-input",
        bounds=Rect(0.0, 0.0, 320.0, 48.0),
        font_size=16.0,
    )
    action = Button(
        "Continue",
        key="dynamic-type-action",
        bounds=Rect(0.0, 0.0, 160.0, 48.0),
        font_size=16.0,
    )

    content = Column(
        key="dynamic-type-content",
        bounds=Rect(0.0, 0.0, 1.0, 1.0),
        fill_viewport=True,
        padding=Insets.symmetric(horizontal=36.0, vertical=32.0),
        spacing=20.0,
        cross_alignment=CrossAxisAlignment.START,
    )
    content.add(title, copy, field, action)

    typography = DynamicTypography(
        content,
        key="dynamic-type-root",
        bounds=Rect(0.0, 0.0, 1.0, 1.0),
        fill_viewport=True,
        scales=ResponsiveValue(compact=0.85, desktop=1.0, ultrawide=1.2),
    )
    return Window(title="SwirUI — Dynamic Typography", width=960, height=520), typography


if __name__ == "__main__":
    window, root = build_demo()
    runtime = mount(window, root)
    print(f"Scene generation: {runtime.generation}")
    print(f"Initial typography variant: {root.current_variant.value}")
    print(f"Initial typography scale: {root.current_scale:.2f}x")
