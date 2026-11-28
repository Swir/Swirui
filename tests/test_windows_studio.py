import sys

import pytest

from swirui import FUTURE_LIGHT, NEON_BLUE, App, ThemePackage, Window, mount
from swirui import __main__ as cli
from swirui.platforms import PlatformEvent, PlatformEventKind, PointerButton
from swirui.rendering import WgpuRenderer
from swirui.studio import Studio
from swirui.studio_comparison import AppearanceComparison, bind_comparison


def _exercise_save_dialog(target):
    import ctypes
    import threading
    import time

    from swirui.rendering import NullRenderer

    user32 = ctypes.WinDLL("user32")
    hwnd = ctypes.c_void_p
    uint = ctypes.c_uint
    text_buffer = ctypes.c_wchar_p
    enum_proc = ctypes.WINFUNCTYPE(ctypes.c_int, hwnd, ctypes.c_ssize_t)
    user32.GetLastActivePopup.argtypes, user32.GetLastActivePopup.restype = [hwnd], hwnd
    user32.GetWindow.argtypes, user32.GetWindow.restype = [hwnd, uint], hwnd
    user32.GetWindowTextW.argtypes = [hwnd, text_buffer, ctypes.c_int]
    user32.GetClassNameW.argtypes = [hwnd, text_buffer, ctypes.c_int]
    user32.EnumChildWindows.argtypes = [hwnd, enum_proc, ctypes.c_ssize_t]
    user32.IsWindowVisible.argtypes = [hwnd]
    user32.IsWindowEnabled.argtypes = [hwnd]
    user32.GetDlgItem.argtypes, user32.GetDlgItem.restype = [hwnd, ctypes.c_int], hwnd
    user32.SendMessageW.argtypes = [hwnd, uint, ctypes.c_size_t, ctypes.c_void_p]
    user32.PostMessageW.argtypes = [hwnd, uint, ctypes.c_size_t, ctypes.c_ssize_t]
    title = "SwirUI theme export test"
    suggested = "studio-theme.json"
    app = App(title, renderer=NullRenderer())
    window = app.add_window(Window(width=320, height=200))

    def answer(owner, accept):
        edit = None

        def read(function, handle):
            buf = ctypes.create_unicode_buffer(1024)
            function(handle, buf, len(buf))
            return buf.value

        @enum_proc
        def find_filename(child, _):
            nonlocal edit
            if (read(user32.GetClassNameW, child) == "Edit"
                    and read(user32.GetWindowTextW, child) in (suggested, "studio-theme")):
                edit = child
                return 0
            return 1

        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            dialog = user32.GetLastActivePopup(owner)
            if (dialog and dialog != owner and user32.GetWindow(dialog, 4) == owner
                    and user32.IsWindowVisible(dialog)
                    and read(user32.GetWindowTextW, dialog) == title):
                if not accept:
                    user32.PostMessageW(dialog, 0x0010, 0, 0)  # WM_CLOSE
                    return
                ok = user32.GetDlgItem(dialog, 1)
                if ok and user32.IsWindowEnabled(ok):
                    if edit is None:
                        user32.EnumChildWindows(dialog, find_filename, 0)
                    if edit:
                        # EM_SETSEL + EM_REPLACESEL trigger the same edit notifications as typing.
                        typed = str(target.with_suffix(""))
                        if read(user32.GetWindowTextW, edit) == typed:
                            user32.PostMessageW(dialog, 0x0111, 1, ok)  # BN_CLICKED, IDOK
                            return
                        user32.SendMessageW(edit, 0x00B1, 0, -1)
                        user32.SendMessageW(edit, 0x00C2, 1, ctypes.create_unicode_buffer(typed))
            time.sleep(0.05)

    try:
        app.start()
        for accept in (False, True):
            thread = threading.Thread(target=answer, args=(window.native_handle.value, accept),
                                      daemon=True)
            thread.start()
            result = window.choose_save_file(suggested, title=title)
            thread.join(2)
            if accept:
                assert result is not None, "Accepting the destination returned Cancel"
                assert result.name == target.name, (result, target)
                assert result.parent.samefile(target.parent), (result, target)
            else:
                assert result is None, f"Cancel returned {result!r}"
            assert not target.exists()
    finally:
        app.stop()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows Save As dialog required")
def test_owned_save_dialog_cancels_and_returns_unicode_json_path(tmp_path):
    from multiprocessing import get_context

    child = get_context("spawn").Process(target=_exercise_save_dialog,
                                         args=(tmp_path / "Zażółć motif.json",))
    child.start()
    try:
        child.join(35)
        assert child.exitcode == 0, "Windows Save As failed or timed out"
    finally:
        if child.is_alive():
            child.kill()
            child.join()
        child.close()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows/wgpu required")
def test_saved_theme_cli_renders_both_authored_accents_in_requested_order(tmp_path, monkeypatch):
    path = tmp_path / "Copper and mint.json"
    day = FUTURE_LIGHT.with_accent("#E38044")
    night = NEON_BLUE.with_accent("#7FE0BF")
    ThemePackage("Copper and mint", {"day": day, "night": night}, "night").save(path)
    original = path.read_bytes()

    def inspect_frame(app):
        app.start()
        app.process_events()
        window, = app.windows
        first, second = window.root.panes
        assert (first.mode, second.mode) == ("day", "night")
        context = app.renderer._contexts[window.native_handle.value]
        window.focus_component(first.field)
        first.field.value = "Local edit"
        first.field.select(10, 6)
        for w, h in ((960, 460), (320, 390), (720, 420)):
            window.resize(w, h)
            app.process_events()
            # Resizing can leave the native pointer over a newly positioned button.
            # Sample the resting accent in each layout at the same pointer position.
            window._apply_platform_event(PlatformEvent(
                PlatformEventKind.POINTER_MOVE, window.native_handle, x=2, y=2,
            ))
            app.render_pending(app._frame_schedulers[window].stats.last_frame_time + 1)
            assert window.width == w and window.height == h
            assert app.renderer._contexts[window.native_handle.value] is context
            assert window.focused_component is first.field and first.field.selected_text == "edit"
            if w == 320:
                assert first.bounds.bottom == second.bounds.y
            else:
                assert first.bounds.right == second.bounds.x
            width, _, pixels = context.read_scene_rgba()
            for pane, color in ((first, (227, 128, 68)), (second, (127, 224, 191))):
                assert not pane.apply.hovered
                button = pane.apply.bounds
                offset = 4 * (round((button.bottom - 6) * window.scale) * width
                              + round((button.x + button.width / 2) * window.scale))
                assert tuple(pixels[offset:offset + 3]) == pytest.approx(color, abs=1)
        window._apply_platform_event(PlatformEvent(
            PlatformEventKind.KEY_DOWN, window.native_handle, key_code=13,
        ))
        assert first.title.text == second.title.text == "Local edit"
        return 0

    monkeypatch.setattr(App, "run", inspect_frame)
    assert cli.main(["preview-theme", str(path), "--variant", "day", "--variant", "night"]) == 0
    assert path.read_bytes() == original


@pytest.mark.skipif(sys.platform != "win32", reason="Windows/wgpu required")
def test_file_preview_switches_one_form_to_its_disabled_palette(tmp_path, monkeypatch):
    import ctypes
    from dataclasses import replace

    path = tmp_path / "Field notes.json"
    ink = replace(NEON_BLUE, palette=replace(NEON_BLUE.palette, disabled="#35283D",
                                              disabled_text="#F1C7DE"))
    ThemePackage("Field notes", {"ink": ink, "paper": FUTURE_LIGHT}, "ink").save(path)
    saved = path.read_bytes()

    def inspect(app):
        app.start()
        app.process_events()
        window, = app.windows
        dark, light = window.root.panes
        dark.field.value = "My draft"
        window.focus_component(dark.field)
        hwnd = window.native_handle.value
        context = app.renderer._contexts[hwnd]
        send = app.platform_backend._user32.SendMessageW
        send.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t]
        send.restype = ctypes.c_ssize_t

        def press(key):
            send(hwnd, 0x0100, key, 1)
            send(hwnd, 0x0101, key, 1)
            app.process_events()

        def samples():
            window._apply_platform_event(PlatformEvent(
                PlatformEventKind.POINTER_MOVE, window.native_handle, x=2, y=2))
            app.render_pending(app._frame_schedulers[window].stats.last_frame_time + 1)
            width, _, rgba = context.read_scene_rgba()
            colors = []
            for widget in (dark.field, dark.apply, light.field, light.apply):
                b = widget.bounds
                offset = 4 * (round((b.bottom - 6) * window.scale) * width
                              + round((b.x + b.width / 2) * window.scale))
                colors.append(bytes(rgba[offset:offset + 3]))
            b = dark.field.bounds
            x1, x2 = round((b.x + 8) * window.scale), round((b.right - 8) * window.scale)
            y1, y2 = round((b.y + 6) * window.scale), round((b.bottom - 6) * window.scale)
            text_area = b"".join(rgba[4 * (y * width + x1):4 * (y * width + x2)]
                                 for y in range(y1, y2))
            return colors, text_area

        press(0x09)
        press(0x09)
        assert window.focused_component is dark.disable_form
        normal, _ = samples()
        press(0x20)
        assert dark.disable_form.checked and not light.disable_form.checked
        disabled, text_area = samples()
        assert disabled[:2] == [bytes.fromhex("35283D")] * 2
        assert disabled[2:] == normal[2:] and disabled[:2] != normal[:2]
        assert any(text_area[i:i + 3] == bytes.fromhex("F1C7DE")
                   for i in range(0, len(text_area), 4))
        press(0x20)
        assert samples()[0] == normal and dark.field.value == "My draft"
        assert app.renderer._contexts[hwnd] is context
        return 0

    monkeypatch.setattr(App, "run", inspect)
    assert cli.main(["preview-theme", str(path)]) == 0
    assert path.read_bytes() == saved


@pytest.mark.skipif(sys.platform != "win32", reason="Windows/wgpu required")
def test_f5_reloads_saved_material_in_the_open_native_window(tmp_path, monkeypatch):
    import ctypes
    from dataclasses import replace

    from swirui import SurfaceStyle

    path = tmp_path / "Motyw szkła.json"
    initial = NEON_BLUE.with_accent("#D493FF")
    styled = replace(initial.with_accent("#79E5BC"), control_radius=18, surface_style=SurfaceStyle(
        kind="glass", depth_layers=5, tilt_x=24, tilt_y=-28))
    ThemePackage("Atlas", {"ink": initial}, "ink").save(path)

    def inspect(app):
        app.start()
        app.process_events()
        window, = app.windows
        pane, = window.root.panes
        hwnd = window.native_handle.value
        context = app.renderer._contexts[hwnd]
        send = app.platform_backend._user32.SendMessageW
        send.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t]
        send.restype = ctypes.c_ssize_t

        def refresh():
            send(hwnd, 0x0100, 0x74, 1)
            send(hwnd, 0x0101, 0x74, 1)
            app.process_events()

        def accent():
            # Measure the resting button near its center, clear of its caption.
            window._apply_platform_event(PlatformEvent(PlatformEventKind.POINTER_MOVE,
                                                      window.native_handle, x=2, y=2))
            app.render_pending(app._frame_schedulers[window].stats.last_frame_time + 1)
            width, _, pixels = context.read_scene_rgba()
            b = pane.apply.bounds
            offset = 4 * (round((b.bottom - 6) * window.scale) * width
                          + round((b.x + b.width / 2) * window.scale))
            return tuple(pixels[offset:offset + 3])

        pane.field.value = "Atlas workbench"
        pane.field.select(15, 6)
        window.focus_component(pane.field)
        assert accent() == pytest.approx((212, 147, 255), abs=1)
        path.write_text("{", encoding="utf-8")
        refresh()
        assert "F5 to retry" in window.title and accent() == pytest.approx((212, 147, 255), abs=1)
        ThemePackage("Atlas glass", {"ink": styled, "paper": FUTURE_LIGHT}, "paper").save(path)
        saved = path.read_bytes()
        refresh()
        assert window.root.panes == (pane,) and window.focused_component is pane.field
        assert pane.field.selected_text == "workbench" and pane.field.caret_index == 6
        assert pane.card.effective_style == styled.surface_style
        assert accent() == pytest.approx((121, 229, 188), abs=1)
        assert window.native_handle.value == hwnd and app.renderer._contexts[hwnd] is context
        assert path.read_bytes() == saved
        return 0

    monkeypatch.setattr(App, "run", inspect)
    assert cli.main(["preview-theme", str(path), "--variant", "ink"]) == 0


@pytest.mark.skipif(sys.platform != "win32", reason="Windows/wgpu required")
def test_search_saved_variants_in_a_resized_preview(tmp_path, monkeypatch):
    import ctypes

    path = tmp_path / "Materials.json"
    ink = NEON_BLUE.with_accent("#6CE2C5")
    copper = FUTURE_LIGHT.with_accent("#CB784A")
    ThemePackage("Field notes", {"ink": ink, "paper": FUTURE_LIGHT, "copper": copper},
                 "ink").save(path)
    original = path.read_bytes()

    def inspect(app):
        app.start()
        app.process_events()
        window, = app.windows
        first, second = window.root.panes
        context = app.renderer._contexts[window.native_handle.value]
        first.field.value = "Keep my draft"
        first.field.select(8, 13)
        send = app.platform_backend._user32.SendMessageW
        send.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t]
        send.restype = ctypes.c_ssize_t
        hwnd = window.native_handle.value
        bounds = first.mode_label.bounds
        point = (round((bounds.y + bounds.height / 2) * window.scale) << 16
                 | round((bounds.x + bounds.width / 2) * window.scale))
        send(hwnd, 0x0201, 1, point)
        send(hwnd, 0x0202, 0, point)
        app.process_events()
        dialog = window.root._variant_dialog
        assert window.focused_component is dialog.search
        assert [item.key for item in dialog.search.items] == ["ink", "copper"]
        window.resize(320, 390)
        app.process_events()
        assert 0 < dialog.dialog_bounds.x < dialog.dialog_bounds.right <= window.width
        for char in "copp":
            send(hwnd, 0x0102, ord(char), 1)
        app.process_events()
        assert [item.key for item in dialog.search.filtered_items] == ["copper"]
        send(hwnd, 0x0100, 0x0D, 1)
        app.process_events()
        window._apply_platform_event(PlatformEvent(PlatformEventKind.POINTER_MOVE,
                                                  window.native_handle, x=2, y=2))
        app.render_pending(app._frame_schedulers[window].stats.last_frame_time + 1)
        assert window.root._variant_dialog is None and window.focused_component is first.mode_label
        assert (first.mode, second.mode) == ("copper", "paper")
        assert first.field.value == "Keep my draft" and first.field.selected_text == "draft"
        assert app.renderer._contexts[window.native_handle.value] is context
        width, _, rgba = context.read_scene_rgba()
        for pane, theme in ((first, copper), (second, FUTURE_LIGHT)):
            b = pane.apply.bounds
            offset = 4 * (round((b.bottom - 6) * window.scale) * width
                          + round((b.x + b.width / 2) * window.scale))
            color = theme.text_color("accent")
            expected = tuple(round(c * 255) for c in (color.r, color.g, color.b))
            assert tuple(rgba[offset:offset + 3]) == pytest.approx(expected, abs=1)
        second.mode_label.emit("click")
        dialog = window.root._variant_dialog
        assert [item.key for item in dialog.search.items] == ["paper", "ink"]
        row = dialog.search.row_bounds(1)
        x = dialog.dialog_bounds.x + row.x + row.width / 2
        y = dialog.dialog_bounds.y + row.y + row.height / 2
        point = round(y * window.scale) << 16 | round(x * window.scale)
        send(hwnd, 0x0201, 1, point)
        send(hwnd, 0x0202, 0, point)
        app.process_events()
        assert (first.mode, second.mode) == ("copper", "ink")
        assert window.root._variant_dialog is None and window.focused_component is second.mode_label
        return 0

    monkeypatch.setattr(App, "run", inspect)
    assert cli.main(["preview-theme", str(path)]) == 0
    assert path.read_bytes() == original


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

        initial_client = (window.width, window.height)
        window.resize(1100, 720)
        app.process_events()
        app.render_pending(app._frame_schedulers[window].stats.last_frame_time + 1)
        assert renderer._contexts[window.native_handle.value] is context
        assert (window.width, window.height) != initial_client
        assert studio.bounds.width == window.width
        assert studio.bounds.height == window.height
        assert studio.workspace.bounds.right <= studio.bounds.right
        assert studio.workspace.bounds.bottom <= studio.bounds.bottom
        record_property("adapter", renderer.adapter_name)
        record_property("backend", renderer.graphics_backend)
        record_property("panes", "hierarchy, inspector, console, preview, code, assets")
    finally:
        app.stop()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows/wgpu required")
def test_launch_compare_refresh_and_close_real_preview_windows(record_property):
    renderer = WgpuRenderer()
    app = App("Studio proof test", renderer=renderer)
    owner = app.add_window(Window(width=1280, height=800))
    studio = Studio()
    mount(owner, studio)
    bind_comparison(app, owner, studio.preview)
    try:
        app.start()
        app.process_events()
        studio.preview.project.value = "Projekt"
        studio.preview.create.emit("click")
        owner_context = renderer._contexts[owner.native_handle.value]
        child, = [window for window in app.windows if window is not owner]
        app.process_events()
        proof = child.root
        assert isinstance(proof, AppearanceComparison)
        context = renderer._contexts[child.native_handle.value]
        assert context is not owner_context
        dark, light = proof.panes
        assert dark.theme == studio.preview.theme_package().themes["dark"]
        assert light.theme == studio.preview.theme_package().themes["light"]
        width, height, pixels = context.read_scene_rgba()
        # Clear canvas just below each top edge must differ in the real GPU frame.
        left_pixel = 4 * (width * 5 + 10)
        right_pixel = left_pixel + (width // 2) * 4
        assert pixels[left_pixel:left_pixel + 3] != pixels[right_pixel:right_pixel + 3]

        child.resize(380, 480)
        app.process_events()
        assert child.width == 380 and dark.bounds.bottom == light.bounds.y
        assert light.mode_label.text == "Light"
        assert light.mode_label.accessible_name == "Light appearance"
        assert light.apply.bounds.right <= child.width
        assert dark.card.bounds.bottom <= child.height
        light.field.value = "Renamed"
        button = light.apply.bounds
        for kind in (PlatformEventKind.POINTER_DOWN, PlatformEventKind.POINTER_UP):
            child._apply_platform_event(PlatformEvent(
                kind, child.native_handle, x=(button.x + 16) * child.scale,
                y=(button.y + 12) * child.scale, button=PointerButton.LEFT,
            ))
        assert dark.title.text == light.title.text == "Renamed"
        assert studio.preview.project.value == "Projekt"
        studio.preview.project.value = "x" * 121
        studio.preview.create.emit("click")
        assert dark.title.text == "Renamed" and len(app.windows) == 2
        # Change the geometry while the source name is invalid and the sample is being edited.
        child.focus_component(light.field)
        light.field.value = "Unsubmitted sample"
        light.field.select(0, 11)
        app.render_pending(app._frame_schedulers[child].stats.last_frame_time + 1)
        width, _, before = context.read_scene_rgba()
        offsets = [
            4 * (round((pane.apply.bounds.y + 2) * child.scale) * width
                 + round((pane.apply.bounds.x + 2) * child.scale))
            for pane in proof.panes
        ]
        studio.preview.corners.value = 0
        studio.inspector.set_value("title", "Live headline")
        app.render_pending(app._frame_schedulers[child].stats.last_frame_time + 1)
        after = context.read_scene_rgba()[2]
        assert all(before[i:i + 3] != after[i:i + 3] for i in offsets)
        assert dark.headline.text == light.headline.text == "Live headline"
        assert child.focused_component is light.field and light.field.selected_text == "Unsubmitted"
        assert light.field.value == "Unsubmitted sample" and dark.title.text == "Renamed"
        studio.preview.project.value = "New design"
        studio.inspector.set_value("material", "acrylic")
        assert dark.theme.surface_style.kind == light.theme.surface_style.kind == "acrylic"
        studio.preview.create.emit("click")
        assert child.root is proof and len(app.windows) == 2
        assert renderer._contexts[child.native_handle.value] is context
        assert dark.title.text == light.title.text == "New design"
        assert light.theme.surface_style.kind == "acrylic"
        assert dark.theme.control_radius == light.theme.control_radius == 0
        child_handle = child.native_handle.value
        child.close()
        assert app.windows == [owner] and child_handle not in renderer._contexts
        studio.preview.create.emit("click")
        replacement = app.windows[-1]
        assert replacement is not child and replacement is not owner
        owner.close()
        assert replacement.closed and not renderer._contexts
        record_property("comparison_backend", renderer.graphics_backend)
    finally:
        app.stop()
