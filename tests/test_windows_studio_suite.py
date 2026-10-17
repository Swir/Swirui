import sys

import pytest

from swirui import App, Window, mount
from swirui.rendering import WgpuRenderer
from swirui.studio_suite import StudioSuite


@pytest.mark.skipif(sys.platform != "win32", reason="Windows/wgpu required")
def test_studio_suite_dashboard_settings_notifications_keep_one_native_context(
    record_property,
):
    renderer = WgpuRenderer()
    app = App("SwirUI Studio operations native gate", renderer=renderer)
    window = app.add_window(Window(width=1280, height=800, min_width=1024, min_height=720))
    studio = StudioSuite()
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

        studio.dashboard.record_sample(78.0, 66.0, 7.4)
        app.render_pending(app._frame_schedulers[window].stats.last_frame_time + 1)
        width, height, rgba = context.read_scene_rgba()
        images.append(bytes(rgba))
        assert renderer._contexts[window.native_handle.value] is context
        assert studio.dashboard.cpu_stream.latest.value == 78.0

        studio.activate("settings")
        studio.settings.reduced_motion.checked = True
        studio.show_notification("Native operations verified", kind="success")
        app.render_pending(app._frame_schedulers[window].stats.last_frame_time + 1)
        width, height, rgba = context.read_scene_rgba()
        images.append(bytes(rgba))
        assert renderer._contexts[window.native_handle.value] is context
        assert studio.toast.visible
        assert studio.theme is not None and studio.theme.reduced_motion

        window.resize(1100, 720)
        app.process_events()
        app.render_pending(app._frame_schedulers[window].stats.last_frame_time + 1)
        assert studio.bounds.width == window.width
        assert studio.bounds.height == window.height
        assert studio.workspace.bounds.right <= studio.bounds.right
        assert studio.workspace.bounds.bottom <= studio.bounds.bottom
        assert len(set(images)) == 3
        record_property("adapter", renderer.adapter_name)
        record_property("backend", renderer.graphics_backend)
        record_property("center_panes", "dashboard, preview, code, assets, settings")
    finally:
        app.stop()
