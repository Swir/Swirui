from dataclasses import replace

import pytest

from swirui import (
    FUTURE_DARK,
    FUTURE_LIGHT,
    AnimationController,
    App,
    Button,
    Panel,
    SurfaceInteraction,
    SurfaceStyle,
    ThemeSurface,
    Window,
    mount,
)
from swirui.platforms import NullPlatformBackend, PlatformEvent, PlatformEventKind, PointerButton
from swirui.rendering import NullRenderer, Rect


def setup_surface():
    app = App(platform_backend=NullPlatformBackend(), renderer=NullRenderer())
    window = app.add_window(Window(width=500, height=300))
    root = Panel(bounds=Rect(0, 0, 500, 300), theme=FUTURE_DARK)
    surface = ThemeSurface(bounds=Rect(40, 40, 300, 180))
    button = Button("Keep working", bounds=Rect(70, 90, 180, 40))
    surface.add(button)
    root.add(surface)
    mount(window, root)
    driver = AnimationController(app, window)
    effect = SurfaceInteraction(driver, surface)
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
