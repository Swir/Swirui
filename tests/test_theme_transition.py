from dataclasses import replace

import pytest

from swirui import (
    FUTURE_DARK,
    FUTURE_LIGHT,
    THEME_PRESETS,
    AnimationController,
    AnimationStatus,
    App,
    Input,
    Panel,
    ThemeController,
    ThemeTransition,
    Tween,
    Window,
    mount,
)
from swirui.animation import linear
from swirui.platforms import NullPlatformBackend
from swirui.rendering import Rect


def test_linear_light_midpoint_exact_endpoints_and_font_switch():
    first = replace(FUTURE_DARK, palette=replace(FUTURE_DARK.palette, surface="#000000"))
    last = replace(FUTURE_LIGHT, palette=replace(FUTURE_LIGHT.palette, surface="#FFFFFF"),
                   font_family="Other", control_radius=20)
    samples, completed = [], []
    transition = ThemeTransition(first, last, 1, samples.append, easing=linear,
                                 on_complete=lambda: completed.append(True)).start()
    assert samples[-1] is first
    transition.advance(.5)
    assert samples[-1].palette.surface == "#BCBCBC"
    assert samples[-1].font_family == first.font_family
    assert samples[-1].control_radius == (first.control_radius + 20) / 2
    assert transition.advance(.75) == pytest.approx(.25)
    transition.advance(1)
    assert samples[-1] is last and completed == [True]
    assert transition.status is AnimationStatus.COMPLETED


def test_alpha_interpolation_is_premultiplied_and_zero_alpha_is_valid():
    first = replace(FUTURE_DARK, palette=replace(FUTURE_DARK.palette, surface="#FF000000",
                                               canvas="#FF000000"))
    last = replace(first, palette=replace(first.palette, surface="#0000FF", canvas="#00FF0000"))
    samples = []
    transition = ThemeTransition(first, last, 1, samples.append, easing=linear).start()
    transition.advance(.5)
    assert samples[-1].palette.surface == "#0000FF80"
    assert samples[-1].palette.canvas == "#00000000"


def test_partitioned_time_matches_one_step_and_cancel_freezes_sample():
    a, b, completed = [], [], []
    one = ThemeTransition(FUTURE_DARK, FUTURE_LIGHT, 1, a.append).start()
    many = ThemeTransition(FUTURE_DARK, FUTURE_LIGHT, 1, b.append,
                           on_complete=lambda: completed.append(True)).start()
    one.advance(.5)
    for _ in range(4):
        many.advance(.125)
    assert a[-1] == b[-1]
    assert many.cancel() and not many.cancel()
    sample_count = len(b)
    many.advance(10)
    assert len(b) == sample_count and not completed


@pytest.mark.parametrize("source", [True, False])
def test_either_endpoint_can_request_reduced_motion(source):
    first = replace(FUTURE_DARK, reduced_motion=source)
    last = replace(FUTURE_LIGHT, reduced_motion=not source)
    samples = []
    transition = ThemeTransition(first, last, 1, samples.append).start()
    assert samples[-1] is last and transition.status is AnimationStatus.COMPLETED
    with pytest.raises(ValueError):
        ThemeTransition(first, last, float("nan"), samples.append)


def test_contrast_guard_avoids_equal_grey_text_on_grey_surface():
    first = replace(FUTURE_DARK, palette=replace(FUTURE_DARK.palette, surface="#000000",
                    canvas="#000000", raised="#000000", hover="#000000", pressed="#000000",
                    selection="#000000", text="#FFFFFF"))
    last = replace(first, palette=replace(first.palette, surface="#FFFFFF", canvas="#FFFFFF",
                   raised="#FFFFFF", hover="#FFFFFF", pressed="#FFFFFF", selection="#FFFFFF",
                   text="#000000"))
    raw, guarded = [], []
    ThemeTransition(first, last, 1, raw.append, protect_text_contrast=False).start().advance(.5)
    ThemeTransition(first, last, 1, guarded.append).start().advance(.5)
    assert raw[-1].palette.text == raw[-1].palette.surface == "#BCBCBC"
    assert guarded[-1].palette.text == "#000000"


@pytest.fixture
def animated_window():
    app = App(platform_backend=NullPlatformBackend())
    window = app.add_window(Window())
    root = Panel(bounds=Rect(0, 0, 600, 300))
    field = Input("Unsaved draft", bounds=Rect(20, 20, 300, 44))
    local = Input("Local", bounds=Rect(20, 90, 300, 44), theme=FUTURE_DARK)
    root.add(field, local)
    mount(window, root)
    driver = AnimationController(app, window)
    controller = ThemeController(window, mode="dark", animations=driver)
    app.start()
    window.focus_component(field)
    field.select(0, 7)
    yield app, window, root, driver, controller
    controller.close()
    driver.dispose()
    app.stop()


def test_controller_animates_retargets_and_preserves_widget_state(animated_window):
    _, window, root, driver, controller = animated_window
    controller.mode = "light"
    assert root.theme is FUTURE_DARK and controller.effective_theme is FUTURE_LIGHT
    assert controller.transitioning
    driver.tick(FUTURE_LIGHT.motion_duration / 2)
    midpoint = root.theme
    assert midpoint not in (FUTURE_DARK, FUTURE_LIGHT)
    controller.refresh()
    assert root.theme is midpoint and driver.active_count == 1
    controller.mode = "dark"
    assert root.theme is midpoint
    for key in list(THEME_PRESETS) * 3:
        theme = THEME_PRESETS[key]
        controller.set_themes(light=theme, dark=theme)
        assert driver.active_count <= 1
    driver.tick(1)
    assert root.theme is theme and driver.active_count == 0 and not controller.transitioning
    field, local = root.children
    assert field.value == "Unsaved draft" and field.selected_text == "Unsaved"
    assert window.focused_component is field and local.effective_theme is FUTURE_DARK


def test_close_cancels_only_appearance_animation(animated_window):
    _, _, root, driver, controller = animated_window
    other = driver.play(Tween(0, 1, 2, lambda _: None))
    controller.mode = "light"
    driver.tick(.05)
    midpoint = root.theme
    controller.close()
    assert driver.active_count == 1 and other.status is AnimationStatus.RUNNING
    driver.tick(1)
    assert root.theme is midpoint
    assert driver.cancel(other) and not driver.cancel(other)


def test_hidden_window_finishes_and_disposed_driver_snaps(animated_window):
    _, window, root, driver, controller = animated_window
    controller.mode = "light"
    window.hide()
    assert root.theme is FUTURE_LIGHT and not controller.transitioning
    controller.mode = "dark"
    assert root.theme is FUTURE_DARK
    window.show()
    driver.dispose()
    controller.mode = "light"
    assert root.theme is FUTURE_LIGHT and not controller.transitioning


def test_native_unbind_during_animation_applies_fallback_immediately(animated_window):
    app, window, root, driver, controller = animated_window
    controller.mode = "light"
    handle = window.native_handle
    app.platform_backend.destroy_window(handle)
    window._unbind_native()
    assert root.theme is FUTURE_LIGHT and driver.active_count == 0


def test_root_replacement_cancels_previous_target(animated_window):
    _, window, root, driver, controller = animated_window
    controller.mode = "light"
    driver.tick(.05)
    old = root.theme
    replacement = Panel(bounds=root.bounds)
    window.set_root(replacement)
    driver.tick(1)
    assert replacement.theme is FUTURE_LIGHT and root.theme is old


def test_reduced_motion_policy_does_not_schedule_frames(animated_window):
    _, _, root, driver, controller = animated_window
    theme = replace(FUTURE_LIGHT, reduced_motion=True)
    controller.set_themes(light=theme, dark=theme)
    assert root.theme is theme and not controller.transitioning and driver.active_count == 0


def test_controller_rejects_driver_from_another_window():
    app = App(platform_backend=NullPlatformBackend())
    window = Window()
    with pytest.raises(ValueError, match="belong"):
        ThemeController(window, animations=AnimationController(app, Window()))
    assert window._theme_controller is None


def test_completion_observer_can_replace_policy_without_stale_frame(animated_window):
    _, _, root, driver, controller = animated_window
    target = replace(FUTURE_DARK, reduced_motion=True)

    def changed(event):
        if event.data["theme"] is FUTURE_LIGHT:
            controller.set_themes(light=target, dark=target)

    root.on("theme_changed", changed)
    controller.mode = "light"
    driver.tick(1)
    assert root.theme is target and controller.effective_theme is target
    assert driver.active_count == 0
