from swirui import (
    FUTURE_LIGHT,
    App,
    ClipboardError,
    MemoryClipboard,
    ThemePackage,
    Window,
    mount,
    state_transaction,
)
from swirui.platforms import NullPlatformBackend
from swirui.rendering import Rect
from swirui.studio_comparison import bind_comparison
from swirui.studio_operations import StudioDashboard
from swirui.studio_suite import StudioSuite


def test_open_comparison_follows_edits_and_detaches_on_close():
    app = App(platform_backend=NullPlatformBackend())
    owner = app.add_window(Window())
    studio = StudioSuite()
    mount(owner, studio)
    preview = studio.preview
    bind_comparison(app, owner, preview)
    try:
        app.start()
        studio.settings.set_accent("#7FE0BF")
        assert app.windows == [owner]
        preview.create.emit("click")
        child = app.windows[-1]
        dark, light = child.root.panes
        seen = []
        dark.on("theme_changed", lambda event: seen.append(event.data["theme"]))
        with state_transaction():
            studio.settings.set_accent("#FF9DAF")
            preview.tint.value = 43
            preview.glow.value = 18
            studio.inspector.set_value("depth", 6)
            studio.settings.reduced_motion.checked = True
        exported = preview.theme_package()
        assert seen == [exported.themes["dark"]]
        assert light.theme == exported.themes["light"]
        assert light.theme.palette.accent == "#FF9DAF" and light.theme.reduced_motion
        with state_transaction():
            preview.corners.value = 0
            child.close()
        assert app.windows == [owner] and dark.theme == exported.themes["dark"]
        preview.create.emit("click")
        next_dark, _ = app.windows[-1].root.panes
        assert next_dark.theme.control_radius == 0
        studio.execute_command("reset")
        assert next_dark.theme == preview.theme_package().themes["dark"]
        assert dark.theme == exported.themes["dark"]
    finally:
        app.stop()


def test_preview_copies_both_authored_finishes_and_preserves_input(tmp_path):
    clipboard = MemoryClipboard("previous text")
    window = Window(clipboard=clipboard)
    studio = StudioSuite()
    runtime = mount(window, studio)
    try:
        preview = studio.preview
        preview.project.value = "Szkło"
        studio.toggle_theme()
        studio.settings.set_accent("#DB237C")
        studio.inspector.set_value("material", "acrylic")
        studio.inspector.set_value("depth", 5)
        studio.settings.reduced_motion.checked = True
        preview.tint.value = 32
        preview.glow.value = 18
        preview.corners.value = 24
        preview.copy_theme.emit("click")
        package = ThemePackage.loads(clipboard.read_text())
        package.save(tmp_path / "finish.json")
        assert ThemePackage.load(tmp_path / "finish.json").default == preview.theme
        assert package.default_theme == "light" and package.name == "Szkło"
        for variant in package.themes.values():
            assert variant.control_radius == 24
            assert variant.surface_style == preview.theme.surface_style
            assert variant.surface_style.tint_opacity == .32
            assert variant.surface_style.glow_opacity == .18
            assert variant.palette.accent == "#DB237C" and variant.reduced_motion
        assert package.themes["dark"].palette.canvas != package.default.palette.canvas
        saved = clipboard.read_text()
        preview.project.value = "X" * 121
        preview.copy_theme.emit("click")
        assert clipboard.read_text() == saved
        assert "120" in preview.result.text
        studio.inspector.set_value("material", "solid")
        assert not preview.tint.enabled and preview.glow.enabled
        studio.inspector.set_value("material", "glass")
        assert preview.tint.enabled and preview.tint.value == 32
        studio.execute_command("reset")
        assert (preview.tint.value, preview.glow.value) == (74, 5.5)
        assert preview.corners.value == 12 and preview.theme.control_radius == 12
    finally:
        runtime.unmount()


def test_export_reports_unavailable_clipboard_and_retries(monkeypatch):
    clipboard = MemoryClipboard("original")
    window = Window(clipboard=clipboard)
    studio = StudioSuite()
    runtime = mount(window, studio)
    try:
        def busy(_text):
            raise ClipboardError("busy")

        with monkeypatch.context() as patch:
            patch.setattr(clipboard, "write_text", busy)
            studio.preview.copy_theme.emit("click")
        assert "unavailable" in studio.preview.result.text and clipboard.read_text() == "original"
        studio.preview.copy_theme.emit("click")
        assert ThemePackage.loads(clipboard.read_text()).default == studio.preview.theme
    finally:
        runtime.unmount()


def test_save_theme_preserves_authored_variants_and_recovers_from_cancel_or_io_error(
    tmp_path, monkeypatch,
):
    clipboard = MemoryClipboard("previous text")
    window = Window(clipboard=clipboard)
    studio = StudioSuite()
    runtime = mount(window, studio)
    try:
        preview = studio.preview
        studio.toggle_theme()
        studio.settings.set_accent("#DB237C")
        preview.set_material("acrylic")
        preview.corners.value = 19
        preview.project.value = "Szkło"
        preview.project.select(1, 3)
        expected = preview.theme_package()
        target = tmp_path / "moje szkło.json"
        target.write_text("previous file", encoding="utf-8")
        destinations = iter([None, tmp_path / "missing" / "theme.json", target])

        def choose(name, *, title):
            assert name == "studio-theme.json" and title == "Save SwirUI theme"
            return next(destinations)

        monkeypatch.setattr(window, "choose_save_file", choose)
        preview.save_theme.emit("click")
        assert preview.result.text == "Save cancelled."
        assert target.read_text(encoding="utf-8") == "previous file"
        preview.save_theme.emit("click")
        assert "Could not save" in preview.result.text
        preview.save_theme.emit("click")
        assert ThemePackage.load(target) == expected
        assert preview.result.text == f"Saved {target.name}."
        assert clipboard.read_text() == "previous text" and preview.project.selected_text == "zk"
        preview.project.value = "x" * 121
        preview.save_theme.emit("click")
        assert "project name" in preview.result.text and ThemePackage.load(target) == expected
    finally:
        runtime.unmount()


def test_save_and_copy_buttons_fit_beside_the_material_badge():
    preview = StudioSuite().preview
    for width in (320, 400, 460, 900):
        bounds = Rect(44, 25, width, 500)
        preview.prepare_layout(bounds)
        assert bounds.x <= preview.status.bounds.x
        assert preview.status.bounds.right <= preview.copy_theme.bounds.x
        assert preview.status.visible == (width == 900)
        assert preview.copy_theme.bounds.right < preview.save_theme.bounds.x
        assert preview.save_theme.bounds.right <= bounds.right


def test_studio_accent_survives_theme_material_and_motion_changes():
    studio = StudioSuite()
    studio.preview.project.value = "My own look"
    studio.settings.accent_input.value = "#FF7ADE"
    studio.settings.apply_accent_button.emit("click")
    assert studio.theme.palette.accent == studio.preview.theme.palette.accent == "#FF7ADE"
    studio.toggle_theme()
    studio.preview.set_material("acrylic")
    studio.settings.reduced_motion.checked = True
    assert studio.theme.palette.accent == studio.preview.theme.palette.accent == "#FF7ADE"
    assert studio.preview.theme.reduced_motion and studio.theme.reduced_motion
    assert studio.preview.project.value == "My own look"
    theme = studio.theme
    assert not studio.settings.set_accent("#wrong")
    assert studio.theme is theme
    studio.settings.reset_accent_button.emit("click")
    assert studio.theme.palette == FUTURE_LIGHT.palette
    assert studio.preview.theme.palette == FUTURE_LIGHT.palette
    assert studio.settings.accent_input.value == FUTURE_LIGHT.palette.accent


def test_compact_settings_reveal_keyboard_focus_without_recreating_controls():
    window = Window(width=1024, height=720)
    studio = StudioSuite()
    studio.resize_to(1024, 720)
    studio.activate("settings")
    runtime = mount(window, studio)
    settings = studio.settings
    assert settings.scroll.max_scroll_y > 0
    window.focus_component(settings.density)
    assert settings.scroll.scroll_y > 0
    assert settings.density.bounds.bottom <= (
        settings.scroll.scroll_y + settings.scroll.bounds.height
    )
    window.focus_component(settings.accent_input)
    assert settings.accent_input.bounds.y >= settings.scroll.scroll_y
    runtime.unmount()


def test_studio_navigation_does_not_overlap_at_supported_window_sizes() -> None:
    studio = StudioSuite()
    buttons = (studio.dashboard_button, studio.preview_button, studio.code_button,
               studio.assets_button, studio.settings_button, studio.theme_button,
               studio.command_button)
    for width, height in ((1024, 720), (1100, 720), (1280, 800), (1440, 900), (1920, 1080)):
        studio.resize_to(width, height)
        for index, button in enumerate(buttons):
            a = button.bounds
            assert a.right <= width and a.bottom <= studio.workspace.bounds.y
            for other in buttons[index + 1:]:
                b = other.bounds
                assert a.right <= b.x or b.right <= a.x or a.bottom <= b.y or b.bottom <= a.y
        assert not studio.active.visible


def test_studio_motion_and_sample_settings_control_the_visible_actions() -> None:
    studio = StudioSuite()
    studio.preview.motion.checked = False
    assert studio.preview.theme.reduced_motion
    studio.preview.set_material("acrylic")
    assert studio.preview.theme.reduced_motion
    studio.preview.motion.checked = True
    assert not studio.preview.theme.reduced_motion
    studio.settings.reduced_motion.checked = True
    studio.preview.set_material("glass")
    assert studio.preview.theme.reduced_motion
    studio.toggle_theme()
    assert studio.preview.theme.reduced_motion
    studio.settings.live_metrics.checked = False
    assert not studio.dashboard.pulse_button.enabled
    before = studio.dashboard.sample_index
    studio.execute_command("pulse")
    assert studio.dashboard.sample_index == before
    studio.settings.live_metrics.checked = True
    assert studio.dashboard.pulse_button.enabled


def test_dashboard_sections_remain_ordered_when_compact_or_offset() -> None:
    dashboard = StudioDashboard()
    for viewport in (Rect(269, 160, 408, 338), Rect(269, 150, 824, 556),
                     Rect(0, 0, 1184, 760), Rect(0, 0, 1184, 338), Rect(0, 0, 1184, 440)):
        dashboard.prepare_layout(viewport)
        cards = dashboard.metric_cards
        assert dashboard.hero.bounds.bottom < cards[0].bounds.y
        assert cards[0].bounds.right < cards[1].bounds.x
        assert cards[1].bounds.right < cards[2].bounds.x
        assert cards[2].bounds.right <= viewport.right
        assert cards[0].bounds.bottom < dashboard.chart.bounds.y
        assert dashboard.chart.bounds.bottom < dashboard.pulse_button.bounds.y
        assert dashboard.pulse_button.bounds.bottom <= viewport.bottom
        assert dashboard.chart.plot_bounds.height > 0
        for value in (dashboard.cpu_label, dashboard.gpu_label, dashboard.frame_label):
            assert value.bounds.height >= value.font_size * 1.2


def test_dashboard_mini_histories_follow_samples_and_theme_without_intercepting_input() -> None:
    dashboard = StudioDashboard()
    dashboard.prepare_layout(Rect(200, 150, 984, 716))
    bars = dashboard.sample_bars[0]
    before = bars.build_scene_node()
    dashboard.record_sample(100, 0, 8)
    after = bars.build_scene_node()
    assert after.children[-1].bounds.height == bars.bounds.height
    assert before.children[-1].bounds.height < after.children[-1].bounds.height
    assert len(after.children) == 12
    assert all(not node.hit_testable for node in after.walk())
    dashboard.theme = FUTURE_LIGHT
    themed = bars.build_scene_node()
    assert themed.children[-1].fill != after.children[-1].fill
    assert all(not node.hit_testable for node in dashboard.hero.build_scene_node().walk())


def test_preview_controls_fit_the_material_card_at_supported_sizes() -> None:
    studio = StudioSuite()
    for width, height in ((1024, 720), (1280, 800), (1600, 1000), (1920, 1080)):
        studio.resize_to(width, height)
        studio.workspace.prepare_layout(studio.workspace.bounds)
        preview = studio.preview
        preview.prepare_layout(preview.bounds)
        surface = preview.surface.bounds
        assert surface.width <= 680 and surface.height <= 380
        assert surface.x >= preview.bounds.x and surface.right <= preview.bounds.right
        assert preview.result.bounds.bottom <= surface.bottom
        assert preview.create.bounds.bottom < preview.result.bounds.y
        assert preview.project.bounds.bottom < preview.motion.bounds.y
        assert preview.tint.bounds.right < preview.glow.bounds.x
        assert preview.glow.bounds.right < preview.corners.bounds.x
        assert preview.corners.bounds.right <= preview.footer.bounds.right


def test_studio_suite_adds_dashboard_settings_and_notification_center() -> None:
    studio = StudioSuite()

    assert tuple(pane.key for pane in studio.workspace.panes) == (
        "hierarchy",
        "inspector",
        "console",
        "dashboard",
        "preview",
        "code",
        "assets",
        "settings",
    )
    assert studio.workspace.active_center_key == "dashboard"
    assert studio.active.text == "DASHBOARD"
    assert studio.dashboard_button.variant.value == "primary"
    assert not studio.toast.visible

    studio.activate("settings")
    assert studio.workspace.active_center_key == "settings"
    assert studio.settings_button.variant.value == "primary"

    studio.activate("preview")
    assert studio.workspace.active_center_key == "preview"
    assert studio.preview_button.variant.value == "primary"


def test_dashboard_records_bounded_samples_and_updates_accessibility() -> None:
    dashboard = StudioDashboard()
    before = dashboard.sample_index

    dashboard.record_sample(73.0, 64.0, 8.0)

    assert dashboard.sample_index == before + 1
    assert dashboard.cpu_stream.latest.value == 73.0
    assert dashboard.gpu_stream.latest.value == 64.0
    assert dashboard.cpu_label.text == "CPU 73%"
    assert dashboard.gpu_label.text == "GPU 64%"
    assert dashboard.frame_label.text == "125 FPS · 8.0 ms"
    assert dashboard.frame_ring.value > 80.0
    assert dashboard.chart.series[0].points[-1].key == before
    assert dashboard.chart.series[1].points[-1].key == before

    for _ in range(80):
        dashboard.pulse()

    assert dashboard.cpu_stream.point_count == 60
    assert dashboard.gpu_stream.point_count == 60
    assert dashboard.cpu_stream.dropped_count > 0
    assert dashboard.gpu_stream.dropped_count > 0
    snapshot = dashboard.chart.accessibility_snapshot()
    assert snapshot.name == "Sample activity · CPU / GPU"
    assert dashboard.status.text == "DEMO DATA"


def test_settings_are_retained_and_drive_notifications_and_reduced_motion() -> None:
    studio = StudioSuite()
    assert studio.show_notification("Build ready", kind="success")
    assert studio.toast.visible
    assert studio.toast.message == "Build ready"
    assert studio.toast.kind == "success"
    assert studio.toast.advance(4.0)
    assert not studio.toast.visible

    studio.toast.dismiss()
    studio.settings.notifications.checked = False
    assert not studio.show_notification("Hidden")
    assert not studio.toast.visible

    studio.settings.reduced_motion.checked = True
    assert studio.theme is not None and studio.theme.reduced_motion
    assert studio.preview.theme is not None and studio.preview.theme.reduced_motion

    before = {pane.key: pane.extent for pane in studio.workspace.panes}
    studio.settings.density.value = 125
    after = {pane.key: pane.extent for pane in studio.workspace.panes}
    assert studio.settings.snapshot["density"] == 125
    assert studio.settings.density_label.text == "Workspace density · 125%"
    assert after["hierarchy"] > before["hierarchy"]
    assert after["inspector"] > before["inspector"]
    assert after["console"] > before["console"]


def test_studio_suite_commands_drive_dashboard_settings_theme_and_metrics() -> None:
    studio = StudioSuite()
    before = studio.dashboard.sample_index

    studio.execute_command("pulse")
    assert studio.dashboard.sample_index == before + 1

    studio.execute_command("settings")
    assert studio.workspace.active_center_key == "settings"

    studio.execute_command("theme")
    assert studio.light
    assert studio.theme == FUTURE_LIGHT

    studio.execute_command("notify")
    assert studio.toast.visible

    studio.execute_command("dashboard")
    assert studio.workspace.active_center_key == "dashboard"


def test_studio_suite_resizes_dashboard_settings_workspace_and_toast() -> None:
    studio = StudioSuite()

    for width, height in ((1024, 720), (1440, 900), (1760, 1040)):
        studio.resize_to(width, height)
        studio.workspace.prepare_layout(studio.workspace.bounds)
        studio.dashboard.prepare_layout(studio.dashboard.bounds)
        studio.settings.prepare_layout(studio.settings.bounds)

        assert studio.bounds == Rect(0, 0, width, height)
        assert studio.workspace.bounds.right <= width
        assert studio.workspace.bounds.bottom <= height
        assert studio.dashboard.chart.bounds.right <= studio.dashboard.bounds.right
        assert studio.settings.density.bounds.right <= studio.settings.bounds.right
        assert studio.toast.bounds.right <= width
