"""Show one retained tree adapting across compact, desktop and ultrawide widths."""

from swirui import (
    Button,
    Column,
    CrossAxisAlignment,
    Insets,
    Label,
    LayoutDirection,
    ResponsiveBreakpoints,
    ResponsiveLayout,
    ResponsiveLayoutSpec,
    ResponsiveValue,
    Window,
    mount,
)
from swirui.rendering import Rect


def build_demo() -> tuple[Window, Column, ResponsiveLayout]:
    breakpoints = ResponsiveBreakpoints(compact_max=720.0, ultrawide_min=1440.0)
    heading_sizes = ResponsiveValue(compact=24.0, desktop=30.0, ultrawide=36.0)

    heading = Label(
        "Responsive SwirUI",
        key="responsive-title",
        bounds=Rect(0.0, 0.0, 120.0, 34.0),
        font_size=heading_sizes.desktop,
    )
    copy = Label(
        "Resize the window through 720 and 1440 logical DIPs. The same retained component "
        "tree switches between compact, desktop and ultrawide layout policies.",
        key="responsive-copy",
        bounds=Rect(0.0, 0.0, 180.0, 30.0),
        font_size=17.0,
    )
    primary = Button(
        "Primary action",
        key="responsive-primary",
        bounds=Rect(0.0, 0.0, 160.0, 48.0),
    )
    secondary = Button(
        "Secondary action",
        key="responsive-secondary",
        bounds=Rect(0.0, 0.0, 180.0, 48.0),
    )

    actions = ResponsiveLayout(
        key="responsive-actions",
        bounds=Rect(0.0, 0.0, 1.0, 120.0),
        breakpoints=breakpoints,
        compact=ResponsiveLayoutSpec(
            direction=LayoutDirection.COLUMN,
            spacing=12.0,
            cross_alignment=CrossAxisAlignment.STRETCH,
        ),
        desktop=ResponsiveLayoutSpec(
            direction=LayoutDirection.ROW,
            spacing=18.0,
            cross_alignment=CrossAxisAlignment.CENTER,
        ),
        ultrawide=ResponsiveLayoutSpec(
            direction=LayoutDirection.ROW,
            spacing=24.0,
            cross_alignment=CrossAxisAlignment.CENTER,
            max_content_width=1000.0,
        ),
    )
    actions.add(primary, secondary)

    root = Column(
        key="responsive-demo-root",
        bounds=Rect(0.0, 0.0, 1.0, 1.0),
        fill_viewport=True,
        padding=Insets.symmetric(horizontal=32.0, vertical=28.0),
        spacing=20.0,
        cross_alignment=CrossAxisAlignment.STRETCH,
    )
    root.add(heading, copy, actions)
    return Window(title="SwirUI — Responsive Layout", width=960, height=520), root, actions


if __name__ == "__main__":
    window, root, actions = build_demo()
    runtime = mount(window, root)
    print(f"Scene generation: {runtime.generation}")
    print(f"Initial responsive variant: {actions.current_variant.value}")
