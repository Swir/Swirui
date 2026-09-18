import sys
import time

import pytest

from swirui import (
    AdaptiveNavigation,
    App,
    Button,
    NavigationMode,
    ViewportClass,
    Window,
    mount,
)
from swirui.platforms.windows import Win32PlatformBackend
from swirui.rendering import Rect, WgpuRenderer


def _isolated_backend() -> Win32PlatformBackend:
    backend = Win32PlatformBackend()
    backend._class_name = f"SwirUI.AdaptiveNavigation.{id(backend):x}"
    return backend


@pytest.mark.skipif(sys.platform != "win32", reason="Adaptive navigation smoke requires Windows")
def test_adaptive_navigation_reflows_on_real_win32_wgpu_resize() -> None:
    renderer = WgpuRenderer()
    backend = _isolated_backend()
    app = App("SwirUI adaptive navigation smoke", platform_backend=backend, renderer=renderer)
    window = app.add_window(Window(title="SwirUI adaptive navigation", width=680, height=420))
    navigation = Button(
        "Navigation",
        key="adaptive-native-navigation",
        bounds=Rect(0.0, 0.0, 80.0, 64.0),
    )
    content = Button(
        "Content",
        key="adaptive-native-content",
        bounds=Rect(0.0, 0.0, 300.0, 220.0),
    )
    shell = AdaptiveNavigation(
        navigation,
        content,
        key="adaptive-native-root",
        bounds=Rect(0.0, 0.0, 1.0, 1.0),
        fill_viewport=True,
    )
    runtime = mount(window, shell)

    try:
        app.start()
        assert renderer.frames_rendered == 1
        assert renderer.persistent_context_count == 1
        assert shell.current_variant is ViewportClass.COMPACT
        assert shell.current_spec.mode is NavigationMode.BOTTOM
        assert navigation.bounds.y >= content.bounds.bottom
        initial_contexts = renderer.persistent_context_count
        initial_generation = runtime.generation

        window.focus_component(content)
        window.resize(1040, 520)
        assert runtime.generation > initial_generation
        assert shell.current_variant is ViewportClass.DESKTOP
        assert shell.current_spec.mode is NavigationMode.RAIL
        assert navigation.bounds.x < content.bounds.x
        assert navigation.bounds.height == pytest.approx(content.bounds.height)
        assert window.focused_component is content

        app.invalidate(window)
        assert app.render_pending(time.monotonic() + 1.0) == 1
        assert renderer.persistent_context_count == initial_contexts
        assert renderer.frames_rendered >= 2
        assert window.scene is not None
        keys = {node.key for node in window.scene.walk()}
        assert {
            "adaptive-native-root",
            "adaptive-native-navigation",
            "adaptive-native-content",
        }.issubset(keys)
    finally:
        app.stop()
