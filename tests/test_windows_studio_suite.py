import sys

import pytest

from swirui import FUTURE_LIGHT, AnimationController, App, Window, mount
from swirui.platforms import PlatformEvent, PlatformEventKind, PointerButton
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
    animations = AnimationController(app, window)
    interactions = studio.bind_interactions(animations)
    assert len(interactions) == 4
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

        chart = studio.dashboard.chart
        selection = chart.select(0, 5)
        viewport = chart.zoom(1.5)
        studio.toggle_theme()
        app.render_pending(app._frame_schedulers[window].stats.last_frame_time + 1)
        width, height, rgba = context.read_scene_rgba()
        images.append(bytes(rgba))
        x = chart.bounds.x + chart.bounds.width / 2
        y = chart.bounds.y + 3
        offset = (round(y * window.scale) * width + round(x * window.scale)) * 4
        color = FUTURE_LIGHT.text_color("surface")
        assert tuple(rgba[offset:offset + 3]) == pytest.approx(
            tuple(round(v * 255) for v in (color.r, color.g, color.b)), abs=1,
        )
        assert chart.selection == selection and chart.viewport == viewport
        assert renderer._contexts[window.native_handle.value] is context

        studio.activate("settings")
        studio.settings.reduced_motion.checked = True
        studio.show_notification("Native operations verified", kind="success")
        app.render_pending(app._frame_schedulers[window].stats.last_frame_time + 1)
        width, height, rgba = context.read_scene_rgba()
        images.append(bytes(rgba))
        assert renderer._contexts[window.native_handle.value] is context
        assert studio.toast.visible
        assert studio.theme is not None and studio.theme.reduced_motion

        window.resize(1024, 720)
        app.process_events()
        app.render_pending(app._frame_schedulers[window].stats.last_frame_time + 1)
        assert studio.bounds.width == window.width
        assert studio.bounds.height == window.height
        assert studio.workspace.bounds.right <= studio.bounds.right
        assert studio.workspace.bounds.bottom <= studio.bounds.bottom
        studio.activate("dashboard")
        app.render_pending(app._frame_schedulers[window].stats.last_frame_time + 1)
        assert studio.dashboard.chart.plot_bounds.height >= 100
        assert len(set(images)) == 4
        studio.preview.project.value = "My material"
        acrylic = studio.dashboard.material_buttons[1]
        for kind in (PlatformEventKind.POINTER_DOWN, PlatformEventKind.POINTER_UP):
            window._apply_platform_event(PlatformEvent(
                kind, window.native_handle, x=(acrylic.bounds.x + 12) * window.scale,
                y=(acrylic.bounds.y + 12) * window.scale, button=PointerButton.LEFT,
            ))
        assert studio.workspace.active_center_key == "preview"
        assert studio.preview.material == "acrylic"
        assert studio.preview.project.value == "My material"
        assert window.focused_component is studio.preview.project
        app.render_pending(app._frame_schedulers[window].stats.last_frame_time + 1)
        width, height, rgba = context.read_scene_rgba()
        assert bytes(rgba) not in images
        assert studio.preview.result.bounds.bottom <= studio.preview.surface.bounds.bottom
        assert renderer._contexts[window.native_handle.value] is context
        # Sample the card pixels, excluding the tuner, text messages and thumb.
        surface = studio.preview.surface.bounds
        row = int((surface.bottom - 25) * window.scale) * width * 4
        start = row + int((surface.x + 28) * window.scale) * 4
        end = row + int((surface.right - 28) * window.scale) * 4
        previous_card = bytes(rgba[start:end])
        tuner = studio.preview.tint.bounds
        for kind in (PlatformEventKind.POINTER_DOWN, PlatformEventKind.POINTER_UP):
            window._apply_platform_event(PlatformEvent(
                kind, window.native_handle, x=(tuner.x + 12) * window.scale,
                y=(tuner.y + tuner.height / 2) * window.scale, button=PointerButton.LEFT,
            ))
        app.render_pending(app._frame_schedulers[window].stats.last_frame_time + 1)
        assert studio.preview.tint.value < 20
        assert bytes(context.read_scene_rgba()[2][start:end]) != previous_card
        # The corner pixel changes on the actual button while keyboard focus stays on the slider.
        window.focus_component(studio.preview.corners)
        launch = studio.preview.create.bounds
        pixel = 4 * (round((launch.y + 2) * window.scale) * width
                     + round((launch.x + 2) * window.scale))
        corners = []
        for key, expected in ((0x24, 0), (0x23, 24)):  # Home, End
            window._apply_platform_event(PlatformEvent(
                PlatformEventKind.KEY_DOWN, window.native_handle, key_code=key,
            ))
            app.render_pending(app._frame_schedulers[window].stats.last_frame_time + 1)
            assert studio.preview.theme.control_radius == expected
            corners.append(bytes(context.read_scene_rgba()[2][pixel:pixel + 3]))
        assert corners[0] != corners[1]
        assert window.focused_component is studio.preview.corners
        studio.activate("settings")
        window.focus_component(studio.settings.density)
        app.render_pending(app._frame_schedulers[window].stats.last_frame_time + 1)
        assert studio.settings.scroll.scroll_y > 0
        window.focus_component(studio.settings.accent_input)
        studio.settings.accent_input.value = "#FF7ADE"
        studio.settings.accent_input.emit("submitted")
        app.render_pending(app._frame_schedulers[window].stats.last_frame_time + 1)
        assert studio.theme.palette.accent == studio.preview.theme.palette.accent == "#FF7ADE"
        width, height, rgba = context.read_scene_rgba()
        button = studio.settings.apply_accent_button
        scroll = studio.settings.scroll
        x = scroll.bounds.x + button.bounds.x + button.bounds.width / 2
        y = scroll.bounds.y + button.bounds.bottom - scroll.scroll_y - 6
        offset = (round(y * window.scale) * width + round(x * window.scale)) * 4
        assert tuple(rgba[offset:offset + 3]) == pytest.approx((255, 122, 222), abs=1)
        studio.settings.accent_input.value = "#7FE0BF"
        for kind in (PlatformEventKind.POINTER_DOWN, PlatformEventKind.POINTER_UP):
            window._apply_platform_event(PlatformEvent(
                kind, window.native_handle, x=x * window.scale, y=y * window.scale,
                button=PointerButton.LEFT,
            ))
        assert window.focused_component is button
        assert studio.theme.palette.accent == "#7FE0BF"
        assert chart.selection == selection and chart.viewport == viewport
        assert renderer._contexts[window.native_handle.value] is context
        record_property("adapter", renderer.adapter_name)
        record_property("backend", renderer.graphics_backend)
        record_property("center_panes", "dashboard, preview, code, assets, settings")
    finally:
        for interaction in interactions:
            interaction.dispose()
        animations.dispose()
        app.stop()
