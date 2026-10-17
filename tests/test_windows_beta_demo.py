import sys

import pytest

from swirui import App, Window, mount
from swirui.demo import Demo
from swirui.rendering import WgpuRenderer


@pytest.mark.skipif(sys.platform != "win32", reason="Windows/wgpu required")
def test_packaged_demo_materials_and_resize_use_one_native_context(record_property):
    renderer = WgpuRenderer()
    app = App(renderer=renderer)
    window = app.add_window(Window(width=920, height=680))
    demo = Demo()
    window.on("resized", lambda _: demo.resize_to(window.width, window.height))
    mount(window, demo)
    images = []
    try:
        app.start()
        app.process_events()
        context = renderer._contexts[window.native_handle.value]
        demo.field.value = "Preserved across every style"
        window.focus_component(demo.field)
        demo.field.select(0, 9)
        for kind in ("solid", "glass", "acrylic"):
            demo.buttons[kind].emit("click")
            app.render_pending(app._frame_schedulers[window].stats.last_frame_time + 1)
            width, height, rgba = context.read_scene_rgba()
            assert width > 0 and height > 0 and len(rgba) == width * height * 4
            images.append(bytes(rgba))
            assert renderer._contexts[window.native_handle.value] is context
            assert demo.field.selected_text == "Preserved"
            assert window.focused_component is demo.field
        assert len(set(images)) == 3
        window.resize(800, 600)
        app.process_events()
        app.render_pending(app._frame_schedulers[window].stats.last_frame_time + 1)
        assert demo.bounds.width == 800 and demo.bounds.height == 600
        assert demo.result.bounds.bottom <= demo.surface.bounds.bottom
        assert demo.field.value == "Preserved across every style"
        record_property("adapter", renderer.adapter_name)
        record_property("backend", renderer.graphics_backend)
        record_property("materials", "solid, glass, acrylic")
    finally:
        app.stop()
