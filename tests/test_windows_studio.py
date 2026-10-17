import sys

import pytest

from swirui import App, Window, mount
from swirui.rendering import Rect, WgpuRenderer
from swirui.studio import ShowcaseEditor


@pytest.mark.skipif(sys.platform != "win32", reason="Windows/wgpu required")
def test_integrated_studio_keeps_one_native_context_across_live_workflow(record_property):
    renderer = WgpuRenderer()
    app = App("SwirUI Studio native gate", renderer=renderer)
    window = app.add_window(
        Window(
            title="SwirUI Studio native gate",
            width=1440,
            height=900,
            min_width=960,
            min_height=680,
        )
    )
    studio = ShowcaseEditor()
    window.on(
        "resized", lambda _: studio.prepare_layout(Rect(0, 0, window.width, window.height))
    )
    mount(window, studio)
    captures: list[bytes] = []
    try:
        app.start()
        app.process_events()
        context = renderer._contexts[window.native_handle.value]
        width, height, rgba = context.read_scene_rgba()
        assert width > 0 and height > 0 and len(rgba) == width * height * 4
        captures.append(bytes(rgba))

        studio.editor.value = "# retained through native theme and resize"
        studio.center_tabs.select_key("code")
        studio.mode.emit("click")
        studio.run_button.emit("click")
        app.render_pending(app._frame_schedulers[window].stats.last_frame_time + 1)
        width, height, rgba = context.read_scene_rgba()
        assert len(rgba) == width * height * 4
        captures.append(bytes(rgba))
        assert renderer._contexts[window.native_handle.value] is context
        assert studio.light and studio.preview_running
        assert studio.editor.value == "# retained through native theme and resize"

        window.resize(1000, 720)
        app.process_events()
        app.render_pending(app._frame_schedulers[window].stats.last_frame_time + 1)
        assert studio.compact
        assert studio.workspace.pane_bounds("inspector").width > 0
        assert studio.preview.card.bounds.right <= studio.preview.bounds.right
        assert renderer._contexts[window.native_handle.value] is context
        assert studio.editor.value == "# retained through native theme and resize"
        assert len(set(captures)) == 2

        record_property("adapter", renderer.adapter_name)
        record_property("backend", renderer.graphics_backend)
        record_property("frames", renderer.frames_rendered)
    finally:
        app.stop()
