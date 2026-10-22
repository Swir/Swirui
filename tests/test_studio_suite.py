from swirui import FUTURE_LIGHT
from swirui.rendering import Rect
from swirui.studio_operations import StudioDashboard
from swirui.studio_suite import StudioSuite


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


def test_dashboard_records_bounded_live_metrics_and_updates_accessibility() -> None:
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
    assert snapshot.name == "Live performance"


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
