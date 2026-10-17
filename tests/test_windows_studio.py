import sys

import pytest

from swirui import App, Window, mount
from swirui.rendering import WgpuRenderer
from swirui.studio import Studio


@pytest.mark.skipif(sys.platform != "win32", reason="Windows/wgpu required")
def test_integrated_studio_keeps_one_native_context_across_tools_and_theme(record_property):
    renderer = WgpuRenderer()
    app = App("SwirUI Studio native gate", renderer=renderer)
    window = app.add_window(Window(width=1280, height=800, min_width=1024, min_height=720))
    studio = Studio()
    window.on("resized", lambda _: studio.resize_to(window.width, window.height))
    mount(window, studio)
    images = []
    try:
        app.start()
        app.process_events()
        context = renderer._contexts[window.native_handle.value]
        width, height, rgba = context.read_scene_rgba()
        assert width > 0 and height > 0 and len(rgba) == width * height * 4
        images.append(bytes(rgba))

        studio.activate("code")
        app.render_pending(app._frame_schedulers[window].stats.last_frame_time + 1)
        assert renderer._contexts[window.native_handle.value] is context
        assert studio.workspace.active_center_key == "code"

        studio.activate("preview")
        studio.inspector.set_value("title", "Native retained studio")
        studio.inspector.set_value("material", "acrylic")
        studio.inspector.set_value("depth", 5)
        app.render_pending(app._frame_schedulers[window].stats.last_frame_time + 1)
        width, height, rgba = context.read_scene_rgba()
        images.append(bytes(rgba))
        assert renderer._contexts[window.native_handle.value] is context
        assert studio.preview.heading.text == "Native retained studio"
        assert studio.preview.theme.surface_style.kind == "acrylic"

        studio.toggle_theme()
        app.render_pending(app._frame_schedulers[window].stats.last_frame_time + 1)
        width, height, rgba = context.read_scene_rgba()
        images.append(bytes(rgba))
        assert len(set(images)) == 3

        window.resize(1100, 720)
        app.process_events()
        app.render_pending(app._frame_schedulers[window].stats.last_frame_time + 1)
        assert renderer._contexts[window.native_handle.value] is context
        assert studio.bounds.width == 1100 and studio.bounds.height == 720
        assert studio.workspace.bounds.right <= studio.bounds.right
        assert studio.workspace.bounds.bottom <= studio.bounds.bottom
        record_property("adapter", renderer.adapter_name)
        record_property("backend", renderer.graphics_backend)
        record_property("panes", "hierarchy, inspector, console, preview, code, assets")
    finally:
        app.stop()
