from swirui import FUTURE_LIGHT
from swirui.rendering import Rect
from swirui.studio_operations import StudioDashboard
from swirui.studio_suite import StudioSuite


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
