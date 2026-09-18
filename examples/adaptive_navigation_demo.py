"""Show navigation moving from bottom bar to rail/sidebar as the window grows."""

from swirui import (
    AdaptiveNavigation,
    Button,
    Column,
    CrossAxisAlignment,
    Insets,
    Label,
    Window,
    mount,
)
from swirui.rendering import Rect


def build_demo() -> tuple[Window, AdaptiveNavigation]:
    navigation = Column(
        key="demo-navigation",
        bounds=Rect(0.0, 0.0, 80.0, 64.0),
        padding=Insets.all(8.0),
        spacing=8.0,
        cross_alignment=CrossAxisAlignment.STRETCH,
    )
    navigation.add(
        Button("Home", key="nav-home", bounds=Rect(0.0, 0.0, 100.0, 42.0)),
        Button("Projects", key="nav-projects", bounds=Rect(0.0, 0.0, 100.0, 42.0)),
        Button("Settings", key="nav-settings", bounds=Rect(0.0, 0.0, 100.0, 42.0)),
    )

    content = Column(
        key="demo-content",
        bounds=Rect(0.0, 0.0, 480.0, 320.0),
        padding=Insets.all(28.0),
        spacing=18.0,
        cross_alignment=CrossAxisAlignment.START,
    )
    content.add(
        Label(
            "Adaptive navigation",
            key="adaptive-title",
            bounds=Rect(0.0, 0.0, 220.0, 38.0),
            font_size=30.0,
        ),
        Label(
            "Resize through 720 and 1440 logical DIPs. The same retained navigation and "
            "content widgets move from a compact bottom region to a desktop rail and an "
            "ultrawide sidebar without losing component identity or focus.",
            key="adaptive-copy",
            bounds=Rect(0.0, 0.0, 420.0, 80.0),
            font_size=17.0,
        ),
    )

    shell = AdaptiveNavigation(
        navigation,
        content,
        key="adaptive-shell",
        bounds=Rect(0.0, 0.0, 1.0, 1.0),
        fill_viewport=True,
        padding=12.0,
    )
    return Window(title="SwirUI — Adaptive Navigation", width=960, height=600), shell


if __name__ == "__main__":
    window, shell = build_demo()
    runtime = mount(window, shell)
    print(f"Scene generation: {runtime.generation}")
    print(f"Initial navigation mode: {shell.current_spec.mode.value}")
