from dataclasses import replace

import pytest

from swirui import (
    FUTURE_DARK,
    FUTURE_LIGHT,
    AnimationController,
    App,
    Button,
    Modal,
    Panel,
    SurfaceInteraction,
    SurfaceStyle,
    ThemeSurface,
    Window,
    mount,
)
from swirui.platforms import NullPlatformBackend, PlatformEvent, PlatformEventKind, PointerButton
from swirui.rendering import NullRenderer, Rect


def setup_surface(**options):
    app = App(platform_backend=NullPlatformBackend(), renderer=NullRenderer())
    window = app.add_window(Window(width=500, height=300))
    root = Panel(bounds=Rect(0, 0, 500, 300), theme=FUTURE_DARK)
    surface = ThemeSurface(bounds=Rect(40, 40, 300, 180))
    button = Button("Keep working", bounds=Rect(70, 90, 180, 40))
    surface.add(button)
    root.add(surface)
    mount(window, root)
    driver = AnimationController(app, window)
    effect = SurfaceInteraction(driver, surface, **options)
    app.start()
    return app, window, root, surface, button, driver, effect


def pointer(window, kind=PlatformEventKind.POINTER_MOVE, x=55, y=55):
    window._apply_platform_event(PlatformEvent(
        kind, window.native_handle, x=x, y=y, button=PointerButton.LEFT,
    ))


def test_surface_feedback_uses_real_hit_paths_preserves_children_and_retargets():
    app, window, root, surface, button, driver, effect = setup_surface()
    bounds = button.bounds
    authored = SurfaceStyle(kind="glass", elevation=14, depth_layers=3)
    surface.style = authored
    try:
        pointer(window)
        driver.tick(.04)
        first = effect.progress
        assert 0 < first < 1
        for _ in range(100):
            pointer(window, x=400, y=260)
            pointer(window)
        assert driver.active_count == 1 and effect.progress == first
        driver.tick(1)
        assert effect.progress == 1 and driver.active_count == 0
        scene = surface.build_scene_node()
        assert len(tuple(scene.walk())) < 80
        assert all(not n.hit_testable for n in scene.walk() if n is not scene)
        assert surface.style is authored and button.bounds == bounds
        clicks = []
        button.on("click", clicks.append)
        pointer(window, PlatformEventKind.POINTER_DOWN, 100, 110)
        driver.tick(1)
        assert effect.progress == .35
        pointer(window, PlatformEventKind.POINTER_UP, 100, 110)
        driver.tick(1)
        assert len(clicks) == 1 and effect.progress == 1
        pointer(window, x=400, y=260)
        driver.tick(1)
        assert effect.progress == .65  # Keyboard focus inside the surface remains visible.
        window.focus_component(None)
        driver.tick(1)
        assert effect.progress == 0 and surface.style is authored
        root.theme = FUTURE_LIGHT
        assert surface.effective_theme is FUTURE_LIGHT
    finally:
        effect.dispose()
        driver.dispose()
        app.stop()


def test_reduced_motion_disable_and_unmount_cancel_without_losing_authored_style():
    app, window, root, surface, button, driver, effect = setup_surface()
    try:
        pointer(window)
        driver.tick(.02)
        root.theme = replace(FUTURE_LIGHT, reduced_motion=True)
        assert effect.progress == 1 and driver.active_count == 0
        surface.enabled = False
        assert effect.progress == 0 and driver.active_count == 0
        surface.enabled = True
        pointer(window)
        assert effect.progress == 1
        surface.style = SurfaceStyle(glow_radius=30)
        assert surface.effective_style.glow_radius == 30
        root.remove(surface)
        assert effect.disposed and effect.progress == 0 and driver.active_count == 0
        assert not surface.build_scene_node().hit_testable
        effect.dispose()
        assert surface.style.glow_radius == 30 and button.parent is surface
    finally:
        driver.dispose()
        app.stop()


def test_pointer_tilt_tracks_child_hits_and_returns_to_rest_with_keyboard_focus():
    app, window, root, surface, button, driver, effect = setup_surface(tilt_degrees=20)
    authored = SurfaceStyle(kind="glass", depth_layers=4, tilt_x=3, tilt_y=-4)
    surface.style = authored

    def plane():
        return next(n for n in surface.build_scene_node().walk() if n.key.endswith(":depth:0"))

    def expected(x, y):
        style = replace(authored, tilt_x=x, tilt_y=y)
        return style.to_scene_node(surface.key, surface.bounds, FUTURE_DARK).children[0]

    try:
        window.focus_component(button)
        driver.tick(1)
        pointer(window, x=115, y=85)  # quarter-width, quarter-height
        for _ in range(12):
            pointer(window, x=120, y=90)
            pointer(window, x=115, y=85)
        assert driver.active_count == 1
        driver.tick(1)
        assert plane().path == expected(13, -14).path
        pointer(window, x=190, y=130)  # over the button, at the card center
        driver.tick(1)
        assert plane().path == expected(3, -4).path
        for x in (210, 220, 230, 250):
            pointer(window, x=x, y=175)
        pointer(window, x=265, y=175)
        assert driver.active_count == 1 and plane().path == expected(3, -4).path
        driver.tick(1)
        assert plane().path == expected(-7, 6).path
        pointer(window, x=460, y=245)
        driver.tick(.04)
        assert plane().path not in (expected(-7, 6).path, expected(3, -4).path)
        driver.tick(1)
        assert effect.progress == .65 and plane().path == expected(3, -4).path
        root.theme = replace(FUTURE_LIGHT, reduced_motion=True)
        pointer(window, x=115, y=85)
        assert effect.progress == 1 and driver.active_count == 0
        assert plane().path == expected(3, -4).path
        assert surface.style is authored and window.focused_component is button
    finally:
        effect.dispose()
        driver.dispose()
        app.stop()


def test_binding_requires_correct_mount_and_rejects_duplicate_owner():
    app, window, root, surface, _, driver, effect = setup_surface()
    try:
        with pytest.raises(ValueError, match="already"):
            SurfaceInteraction(driver, surface)
        other = ThemeSurface(bounds=surface.bounds)
        with pytest.raises(ValueError, match="Mount"):
            SurfaceInteraction(driver, other)
        window.emit("focus_changed", focused=False)
        assert effect.progress == 0
        effect.dispose()
        rebound = SurfaceInteraction(driver, surface)
        window.close()
        assert rebound.disposed
    finally:
        effect.dispose()
        driver.dispose()
        app.stop()


def test_client_exit_resets_material_tilt_and_keeps_keyboard_focus():
    app, window, _, surface, button, driver, effect = setup_surface(tilt_degrees=20)
    surface.style = SurfaceStyle(kind="glass", depth_layers=3)
    try:
        pointer(window, x=88, y=100)
        pointer(window, PlatformEventKind.POINTER_DOWN, x=88, y=100)
        driver.tick(1)
        assert window.focused_component is button and effect.progress == .35
        assert surface._interaction_tilt != (0, 0)
        window._apply_platform_event(PlatformEvent(PlatformEventKind.POINTER_EXIT,
                                                  window.native_handle))
        driver.tick(.04)
        assert .35 < effect.progress < .65
        driver.tick(1)
        assert effect.progress == .65 and surface._interaction_tilt == (0, 0)
        assert window.focused_component is button and not button.hovered and not button.pressed
        pointer(window, x=88, y=100)
        driver.tick(1)
        assert effect.progress == 1 and surface._interaction_tilt != (0, 0)
    finally:
        effect.dispose()
        driver.dispose()
        app.stop()


def test_dialog_tilt_uses_local_coordinates_and_clamps_the_authored_angles():
    app = App(platform_backend=NullPlatformBackend(), renderer=NullRenderer())
    window = app.add_window(Window(width=580, height=400))
    style = SurfaceStyle(depth_layers=3, tilt_x=28, tilt_y=-28)
    surface = ThemeSurface(bounds=Rect(20, 20, 200, 100), style=style)
    dialog = Modal(bounds=Rect(0, 0, 580, 400), dialog_bounds=Rect(150, 90, 260, 180),
                   content=surface, theme=FUTURE_DARK)
    mount(window, dialog)
    driver = AnimationController(app, window)
    effect = SurfaceInteraction(driver, surface, tilt_degrees=24)
    try:
        app.start()
        # Use the rendered origin because a modal arranges its content to its dialog bounds.
        b = surface.bounds
        x, y = dialog.dialog_bounds.x + b.x, dialog.dialog_bounds.y + b.y
        pointer(window, x=x + b.width / 4, y=y + b.height / 4)
        driver.tick(1)
        actual = surface.build_scene_node().children[0]
        clipped = replace(style, tilt_x=35, tilt_y=-35)
        assert actual.path == clipped.to_scene_node(surface.key, b, FUTURE_DARK).children[0].path
        effect.dispose()
        assert surface.build_scene_node().children[0].path == (
            style.to_scene_node(surface.key, b, FUTURE_DARK).children[0].path)
    finally:
        effect.dispose()
        driver.dispose()
        app.stop()
