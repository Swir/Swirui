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
        width, _, pixels = context.read_scene_rgba()
        for pane, color in ((first, (227, 128, 68)), (second, (127, 224, 191))):
            button = pane.apply.bounds
            offset = 4 * (round((button.bottom - 6) * window.scale) * width
                          + round((button.x + button.width / 2) * window.scale))
            assert tuple(pixels[offset:offset + 3]) == pytest.approx(color, abs=1)
        window.focus_component(first.field)
        first.field.value = "Local edit"
        window._apply_platform_event(PlatformEvent(
            PlatformEventKind.KEY_DOWN, window.native_handle, key_code=13,
        ))
        assert first.title.text == second.title.text == "Local edit"
        return 0

    monkeypatch.setattr(App, "run", inspect_frame)
    assert cli.main(["preview-theme", str(path), "--variant", "day", "--variant", "night"]) == 0
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

        child.resize(640, 390)
        app.process_events()
        assert dark.bounds.right <= light.bounds.x
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
