import sys
import time

import pytest

from swirui import (
    App,
    Button,
    Column,
    CrossAxisAlignment,
    DynamicTypography,
    Input,
    Label,
    LayoutDirection,
    ResponsiveLayout,
    ResponsiveLayoutSpec,
    ResponsiveValue,
    ViewportClass,
    Window,
    mount,
)
from swirui.platforms.windows import Win32PlatformBackend
from swirui.rendering import Rect, WgpuRenderer


def _isolated_backend() -> Win32PlatformBackend:
    backend = Win32PlatformBackend()
    backend._class_name = f"SwirUI.ResponsiveLayout.{id(backend):x}"
    return backend


@pytest.mark.skipif(sys.platform != "win32", reason="Responsive layout smoke requires Windows")
def test_responsive_layout_reflows_across_real_win32_wgpu_resize() -> None:
    renderer = WgpuRenderer()
    backend = _isolated_backend()
    app = App("SwirUI responsive layout smoke", platform_backend=backend, renderer=renderer)
    window = app.add_window(Window(title="SwirUI responsive layout", width=680, height=360))

    primary = Button("Primary action", key="responsive-primary", bounds=Rect(0.0, 0.0, 150.0, 48.0))
    secondary = Button(
        "Secondary action",
        key="responsive-secondary",
        bounds=Rect(0.0, 0.0, 170.0, 48.0),
    )
    layout = ResponsiveLayout(
        key="responsive-root",
        bounds=Rect(0.0, 0.0, 1.0, 1.0),
        fill_viewport=True,
        compact=ResponsiveLayoutSpec(
            direction=LayoutDirection.COLUMN,
            padding=24.0,
            spacing=14.0,
            cross_alignment=CrossAxisAlignment.STRETCH,
        ),
        desktop=ResponsiveLayoutSpec(
            direction=LayoutDirection.ROW,
            padding=32.0,
            spacing=20.0,
            cross_alignment=CrossAxisAlignment.CENTER,
        ),
        ultrawide=ResponsiveLayoutSpec(
            direction=LayoutDirection.ROW,
            padding=40.0,
            spacing=28.0,
            cross_alignment=CrossAxisAlignment.CENTER,
            max_content_width=1100.0,
        ),
    )
    layout.add(primary, secondary)
    runtime = mount(window, layout)

    try:
        app.start()
        assert renderer.frames_rendered == 1
        assert renderer.persistent_context_count == 1
        assert layout.current_variant is ViewportClass.COMPACT
        assert secondary.bounds.y > primary.bounds.bottom
        assert primary.bounds.width == pytest.approx(632.0)
        initial_contexts = renderer.persistent_context_count
        initial_generation = runtime.generation

        window.resize(980, 360)
        assert runtime.generation > initial_generation
        assert layout.current_variant is ViewportClass.DESKTOP
        assert secondary.bounds.x > primary.bounds.right

        app.invalidate(window)
        assert app.render_pending(time.monotonic() + 1.0) == 1
        assert renderer.persistent_context_count == initial_contexts
        assert renderer.frames_rendered >= 2
        assert window.scene is not None
        keys = {node.key for node in window.scene.walk()}
        assert {"responsive-root", "responsive-primary", "responsive-secondary"}.issubset(keys)
    finally:
        app.stop()


@pytest.mark.skipif(sys.platform != "win32", reason="Dynamic typography smoke requires Windows")
def test_dynamic_typography_remeasures_on_real_win32_wgpu_resize() -> None:
    renderer = WgpuRenderer()
    backend = _isolated_backend()
    app = App("SwirUI dynamic typography smoke", platform_backend=backend, renderer=renderer)
    window = app.add_window(Window(title="SwirUI dynamic typography", width=680, height=360))

    title = Label(
        "Dynamic typography",
        key="dynamic-type-title",
        bounds=Rect(0.0, 0.0, 220.0, 36.0),
        font_size=24.0,
    )
    field = Input(
        "Retained input",
        key="dynamic-type-input",
        bounds=Rect(0.0, 0.0, 220.0, 48.0),
        font_size=16.0,
    )
    action = Button(
        "Continue",
        key="dynamic-type-button",
        bounds=Rect(0.0, 0.0, 160.0, 48.0),
        font_size=16.0,
    )
    content = Column(
        key="dynamic-type-content",
        bounds=Rect(0.0, 0.0, 1.0, 1.0),
        fill_viewport=True,
        padding=28.0,
        spacing=16.0,
    )
    content.add(title, field, action)
    typography = DynamicTypography(
        content,
        key="dynamic-type-root",
        bounds=Rect(0.0, 0.0, 1.0, 1.0),
        fill_viewport=True,
        scales=ResponsiveValue(compact=0.8, desktop=1.0, ultrawide=1.25),
    )
    runtime = mount(window, typography)
    window.focus_component(field)

    try:
        app.start()
        assert renderer.frames_rendered == 1
        assert renderer.persistent_context_count == 1
        assert typography.current_variant is ViewportClass.COMPACT
        assert window.focused_component is field
        assert window.scene is not None
        compact_title = next(
            node for node in window.scene.walk() if node.key == "dynamic-type-title"
        )
        assert compact_title.font_size == pytest.approx(19.2)
        initial_contexts = renderer.persistent_context_count
        initial_generation = runtime.generation

        window.resize(980, 360)
        assert runtime.generation > initial_generation
        assert typography.current_variant is ViewportClass.DESKTOP
        assert window.focused_component is field
        assert window.scene is not None
        desktop_title = next(
            node for node in window.scene.walk() if node.key == "dynamic-type-title"
        )
        assert desktop_title.font_size == pytest.approx(24.0)

        app.invalidate(window)
        assert app.render_pending(time.monotonic() + 1.0) == 1
        assert renderer.persistent_context_count == initial_contexts
        assert renderer.frames_rendered >= 2
    finally:
        app.stop()
