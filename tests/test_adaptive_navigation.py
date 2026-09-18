import pytest

from swirui import (
    AdaptiveNavigation,
    AdaptiveNavigationSpec,
    Button,
    Insets,
    NavigationMode,
    ResponsiveBreakpoints,
    ViewportClass,
    Window,
    mount,
)
from swirui.rendering import Rect, Size
from swirui.widgets import compile_component_scene


def _navigation() -> tuple[AdaptiveNavigation, Button, Button]:
    navigation = Button("Navigation", key="navigation", bounds=Rect(0.0, 0.0, 80.0, 64.0))
    content = Button("Content", key="content", bounds=Rect(0.0, 0.0, 300.0, 220.0))
    shell = AdaptiveNavigation(
        navigation,
        content,
        key="adaptive-navigation",
        bounds=Rect(0.0, 0.0, 1.0, 1.0),
        fill_viewport=True,
        padding=Insets.all(12.0),
        compact=AdaptiveNavigationSpec(NavigationMode.BOTTOM, 64.0, gap=8.0),
        desktop=AdaptiveNavigationSpec(NavigationMode.RAIL, 88.0, gap=12.0),
        ultrawide=AdaptiveNavigationSpec(NavigationMode.SIDEBAR, 280.0, gap=20.0),
    )
    return shell, navigation, content


def test_adaptive_navigation_places_bottom_bar_for_compact_widths() -> None:
    shell, navigation, content = _navigation()
    scene = compile_component_scene(shell, width=600.0, height=420.0)
    assert scene is not None
    assert shell.current_variant is ViewportClass.COMPACT
    assert shell.current_spec.mode is NavigationMode.BOTTOM
    assert content.bounds == Rect(12.0, 12.0, 576.0, 324.0)
    assert navigation.bounds == Rect(12.0, 344.0, 576.0, 64.0)


def test_adaptive_navigation_places_left_rail_for_desktop_widths() -> None:
    shell, navigation, content = _navigation()
    compile_component_scene(shell, width=1000.0, height=520.0)
    assert shell.current_variant is ViewportClass.DESKTOP
    assert shell.current_spec.mode is NavigationMode.RAIL
    assert navigation.bounds == Rect(12.0, 12.0, 88.0, 496.0)
    assert content.bounds == Rect(112.0, 12.0, 876.0, 496.0)


def test_adaptive_navigation_expands_sidebar_for_ultrawide_widths() -> None:
    shell, navigation, content = _navigation()
    compile_component_scene(shell, width=1800.0, height=800.0)
    assert shell.current_variant is ViewportClass.ULTRAWIDE
    assert shell.current_spec.mode is NavigationMode.SIDEBAR
    assert navigation.bounds == Rect(12.0, 12.0, 280.0, 776.0)
    assert content.bounds == Rect(312.0, 12.0, 1476.0, 776.0)


def test_custom_breakpoints_and_variant_specs_reflow_same_children() -> None:
    shell, navigation, content = _navigation()
    shell.breakpoints = ResponsiveBreakpoints(compact_max=800.0, ultrawide_min=1600.0)
    shell.set_variant_spec(
        ViewportClass.DESKTOP,
        AdaptiveNavigationSpec(NavigationMode.SIDEBAR, 220.0, gap=16.0),
    )
    navigation_preferred = navigation.preferred_size
    content_preferred = content.preferred_size
    compile_component_scene(shell, width=1200.0, height=700.0)
    assert shell.current_variant is ViewportClass.DESKTOP
    assert shell.current_spec.mode is NavigationMode.SIDEBAR
    assert navigation.bounds.width == pytest.approx(220.0)
    assert content.bounds.x == pytest.approx(248.0)
    assert navigation.preferred_size == navigation_preferred
    assert content.preferred_size == content_preferred
    assert navigation.parent is shell
    assert content.parent is shell


def test_measure_accounts_for_navigation_extent_and_padding() -> None:
    shell, _nav_widget, _content_widget = _navigation()
    compact = shell.measure(Size(600.0, 420.0))
    desktop = shell.measure(Size(1000.0, 520.0))
    assert compact.width <= 600.0
    assert compact.height <= 420.0
    assert desktop.width <= 1000.0
    assert desktop.height <= 520.0


def test_focus_is_preserved_when_navigation_changes_mode_after_resize() -> None:
    shell, navigation, content = _navigation()
    window = Window(width=600, height=420)
    runtime = mount(window, shell)
    window.focus_component(content)
    initial_generation = runtime.generation
    window.resize(1000, 520)
    assert runtime.generation > initial_generation
    assert shell.current_variant is ViewportClass.DESKTOP
    assert window.focused_component is content
    assert content.parent is shell
    assert navigation.parent is shell


@pytest.mark.parametrize(
    ("extent", "gap"),
    [(0.0, 0.0), (-1.0, 0.0), (64.0, -1.0), (float("inf"), 0.0)],
)
def test_adaptive_navigation_spec_rejects_invalid_geometry(extent: float, gap: float) -> None:
    with pytest.raises(ValueError):
        AdaptiveNavigationSpec(NavigationMode.BOTTOM, extent, gap)
