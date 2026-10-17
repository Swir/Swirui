from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from swirui import (
    FUTURE_DARK,
    FUTURE_LIGHT,
    App,
    ColorScheme,
    Input,
    Panel,
    ThemeController,
    ThemeMode,
    Window,
    mount,
)
from swirui.platforms import NullPlatformBackend, PlatformEvent, PlatformEventKind
from swirui.platforms.windows_appearance import _PERSONALIZE, _registry_scheme
from swirui.rendering import Rect


class AppearanceBackend(NullPlatformBackend):
    scheme = ColorScheme.LIGHT
    reads = 0

    def get_system_color_scheme(self):
        self.reads += 1
        return self.scheme


def root_panel():
    root = Panel(bounds=Rect(0, 0, 600, 300))
    root.add(Input("Unsaved selection", bounds=Rect(20, 20, 280, 44)))
    return root


def notify(app, window):
    app._dispatch_platform_event(PlatformEvent(
        PlatformEventKind.SYSTEM_APPEARANCE_CHANGED, window.native_handle))


def test_system_controller_initial_binding_changes_and_manual_override():
    backend = AppearanceBackend()
    app = App(platform_backend=backend)
    window = app.add_window(Window())
    root = root_panel()
    mount(window, root)
    controller = ThemeController(window)
    assert root.theme is FUTURE_DARK and controller.system_scheme is None
    try:
        app.start()
        assert root.theme is FUTURE_LIGHT and controller.system_scheme is ColorScheme.LIGHT
        field = root.children[0]
        window.focus_component(field)
        field.select(0, 7)
        backend.scheme = ColorScheme.DARK
        notify(app, window)
        assert root.theme is FUTURE_DARK
        controller.mode = "light"
        assert root.theme is FUTURE_LIGHT
        notify(app, window)
        assert root.theme is FUTURE_LIGHT and controller.system_scheme is ColorScheme.DARK
        controller.mode = ThemeMode.SYSTEM
        assert root.theme is FUTURE_DARK
        assert field.value == "Unsaved selection" and field.selected_text == "Unsaved"
        assert window.focused_component is field
    finally:
        app.stop()
    assert controller.closed and window._theme_controller is None


def test_repeated_notifications_do_not_recompile_scene_or_emit_changed():
    app = App(platform_backend=AppearanceBackend())
    window = app.add_window(Window())
    mount(window, root_panel())
    controller = ThemeController(window)
    try:
        app.start()
        scenes, changes = [], []
        window.on("scene_changed", scenes.append)
        controller.on("changed", changes.append)
        for _ in range(8):
            notify(app, window)
        assert not scenes and not changes
    finally:
        app.stop()


def test_controller_handles_late_root_replacement_local_scopes_and_package_pair():
    window = Window()
    controller = ThemeController(window, mode="light")
    first = root_panel()
    local = Input("Own scope", bounds=Rect(20, 90, 280, 44), theme=FUTURE_DARK)
    first.add(local)
    window.set_root(first)
    assert first.theme is FUTURE_LIGHT and local.effective_theme is FUTURE_DARK
    new_light = replace(FUTURE_LIGHT, control_radius=3)
    new_dark = replace(FUTURE_DARK, control_radius=6)
    controller.set_themes(light=new_light, dark=new_dark)
    assert first.theme is new_light and local.effective_theme is FUTURE_DARK
    second = root_panel()
    window.set_root(second)
    controller.mode = "dark"
    assert second.theme is new_dark and first.theme is new_light
    window.set_root(None)
    controller.refresh()
    controller.close()


@pytest.mark.parametrize("reported", [None, "invalid", 5, object()])
def test_unavailable_or_invalid_backend_uses_explicit_fallback(reported):
    backend = AppearanceBackend()
    backend.scheme = reported
    app = App(platform_backend=backend)
    window = app.add_window(Window())
    root = root_panel()
    mount(window, root)
    controller = ThemeController(window, fallback="light")
    try:
        app.start()
        assert controller.system_scheme is None and root.theme is FUTURE_LIGHT
        controller.fallback = "dark"
        assert root.theme is FUTURE_DARK
        controller.mode = "light"
        assert root.theme is FUTURE_LIGHT
    finally:
        app.stop()


def test_missing_and_failing_backend_capability_does_not_break_window(monkeypatch):
    backend = NullPlatformBackend()
    app = App(platform_backend=backend)
    window = app.add_window(Window())
    mount(window, root_panel())
    controller = ThemeController(window)
    try:
        app.start()
        assert window.get_system_color_scheme() is None

        def denied():
            raise PermissionError("No access")

        monkeypatch.setattr(backend, "get_system_color_scheme", denied, raising=False)
        controller.refresh()
        assert controller.system_scheme is None and controller.effective_theme is FUTURE_DARK
    finally:
        app.stop()


def test_detach_removes_listeners_retains_theme_and_allows_new_controller():
    window = Window()
    root = root_panel()
    window.set_root(root)
    baseline = dict(window._listeners)
    controller = ThemeController(window, mode="light")
    with pytest.raises(ValueError, match="already"):
        ThemeController(window)
    controller.close()
    controller.close()
    assert dict(window._listeners) == baseline and root.theme is FUTURE_LIGHT
    for action in (lambda: controller.refresh(), lambda: setattr(controller, "mode", "dark"),
                   lambda: controller.set_themes(light=FUTURE_LIGHT, dark=FUTURE_DARK)):
        with pytest.raises(RuntimeError, match="closed"):
            action()
    replacement = ThemeController(window, mode="dark")
    assert root.theme is FUTURE_DARK
    window.close()
    assert replacement.closed
    with pytest.raises(ValueError, match="closed"):
        ThemeController(window)


def test_two_windows_keep_independent_policy_and_no_idle_polling():
    backend = AppearanceBackend()
    app = App(platform_backend=backend)
    one, two = app.add_window(Window()), app.add_window(Window())
    first, second = root_panel(), root_panel()
    mount(one, first)
    mount(two, second)
    auto = ThemeController(one)
    manual = ThemeController(two, mode="dark")
    try:
        app.start()
        assert first.theme is FUTURE_LIGHT and second.theme is FUTURE_DARK
        reads = backend.reads
        for _ in range(3):
            app.render_pending()
        assert backend.reads == reads
        backend.scheme = ColorScheme.DARK
        notify(app, one)
        assert first.theme is FUTURE_DARK
        assert manual.mode is ThemeMode.DARK and auto.mode is ThemeMode.SYSTEM
    finally:
        app.stop()


@pytest.mark.parametrize("kwargs", [{"mode": "bad"}, {"fallback": "bad"},
                                   {"light": None}, {"dark": object()}])
def test_invalid_constructor_does_not_attach_or_change_root(kwargs):
    window = Window()
    root = root_panel()
    window.set_root(root)
    with pytest.raises((ValueError, TypeError)):
        ThemeController(window, **kwargs)
    assert window._theme_controller is None and root.theme is None


def test_failed_pair_update_and_invalid_mode_preserve_current_appearance():
    window = Window()
    root = root_panel()
    window.set_root(root)
    controller = ThemeController(window, mode="light")
    with pytest.raises(TypeError):
        controller.set_themes(light=FUTURE_DARK, dark=None)
    with pytest.raises(ValueError):
        controller.mode = "invalid"
    assert controller.mode is ThemeMode.LIGHT and root.theme is FUTURE_LIGHT
    controller.close()


def test_reentrant_root_observer_does_not_announce_stale_theme():
    window = Window()
    root = root_panel()
    mount(window, root)
    controller = ThemeController(window)
    changes, scenes = [], []
    controller.on("changed", changes.append)
    window.on("scene_changed", scenes.append)

    def choose_dark(event):
        if event.data["theme"] is FUTURE_LIGHT:
            controller.mode = "dark"

    root.on("theme_changed", choose_dark)
    controller.mode = "light"
    assert root.theme is FUTURE_DARK and controller.mode is ThemeMode.DARK
    assert len(scenes) == 1
    assert len(changes) == 1 and changes[0].data["theme"] is FUTURE_DARK
    controller.close()


def test_attach_after_native_bind_and_unbind_uses_fallback():
    backend = AppearanceBackend()
    app = App(platform_backend=backend)
    window = app.add_window(Window())
    mount(window, root_panel())
    try:
        app.start()
        controller = ThemeController(window)
        assert controller.system_scheme is ColorScheme.LIGHT
        handle = window.native_handle
        backend.destroy_window(handle)
        window._unbind_native()
        assert controller.system_scheme is None and window.root.theme is FUTURE_DARK
    finally:
        app.stop()


@pytest.mark.parametrize("value,kind,expected", [(0, 4, ColorScheme.DARK),
    (1, 4, ColorScheme.LIGHT), (2, 4, None), ("0", 1, None), (0, 1, None), (True, 4, None)])
def test_windows_registry_reader_uses_app_preference_and_closes_handle(value, kind, expected):
    key = MagicMock()
    registry = SimpleNamespace(HKEY_CURRENT_USER=123, KEY_READ=7, REG_DWORD=4,
                               OpenKey=MagicMock(return_value=key),
                               QueryValueEx=MagicMock(return_value=(value, kind)))
    assert _registry_scheme(registry) is expected
    registry.OpenKey.assert_called_once_with(123, _PERSONALIZE, 0, 7)
    registry.QueryValueEx.assert_called_once_with(key.__enter__.return_value, "AppsUseLightTheme")
    key.__exit__.assert_called_once()


@pytest.mark.parametrize("stage", ["open", "read"])
def test_missing_or_denied_windows_preference_is_unknown(stage):
    key = MagicMock()
    registry = SimpleNamespace(HKEY_CURRENT_USER=123, KEY_READ=7, REG_DWORD=4,
                               OpenKey=MagicMock(return_value=key), QueryValueEx=MagicMock())
    if stage == "open":
        registry.OpenKey.side_effect = FileNotFoundError()
    else:
        registry.QueryValueEx.side_effect = PermissionError()
    assert _registry_scheme(registry) is None
    assert key.__exit__.call_count == int(stage == "read")
