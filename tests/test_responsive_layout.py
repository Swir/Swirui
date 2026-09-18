import pytest

from swirui import (
    Button,
    CrossAxisAlignment,
    Insets,
    LayoutDirection,
    ResponsiveBreakpoints,
    ResponsiveLayout,
    ResponsiveLayoutSpec,
    ResponsiveValue,
    ViewportClass,
)
from swirui.rendering import Rect, Size
from swirui.widgets import compile_component_scene


def _layout() -> tuple[ResponsiveLayout, Button, Button]:
    first = Button("Primary", key="primary", bounds=Rect(0.0, 0.0, 120.0, 44.0))
    second = Button("Secondary", key="secondary", bounds=Rect(0.0, 0.0, 140.0, 44.0))
    layout = ResponsiveLayout(
        key="responsive",
        bounds=Rect(0.0, 0.0, 1.0, 1.0),
        fill_viewport=True,
        compact=ResponsiveLayoutSpec(
            direction=LayoutDirection.COLUMN,
            spacing=10.0,
            padding=Insets.all(16.0),
            cross_alignment=CrossAxisAlignment.STRETCH,
        ),
        desktop=ResponsiveLayoutSpec(
            direction=LayoutDirection.ROW,
            spacing=18.0,
            padding=Insets.symmetric(horizontal=28.0, vertical=20.0),
            cross_alignment=CrossAxisAlignment.CENTER,
        ),
        ultrawide=ResponsiveLayoutSpec(
            direction=LayoutDirection.ROW,
            spacing=24.0,
            padding=32.0,
            cross_alignment=CrossAxisAlignment.CENTER,
            max_content_width=1000.0,
        ),
    )
    layout.add(first, second)
    return layout, first, second


def test_breakpoints_classify_logical_width_boundaries() -> None:
    breakpoints = ResponsiveBreakpoints(compact_max=720.0, ultrawide_min=1440.0)

    assert breakpoints.classify(0.0) is ViewportClass.COMPACT
    assert breakpoints.classify(719.99) is ViewportClass.COMPACT
    assert breakpoints.classify(720.0) is ViewportClass.DESKTOP
    assert breakpoints.classify(1439.99) is ViewportClass.DESKTOP
    assert breakpoints.classify(1440.0) is ViewportClass.ULTRAWIDE


@pytest.mark.parametrize(
    ("compact_max", "ultrawide_min"),
    [
        (0.0, 1440.0),
        (720.0, 720.0),
        (720.0, 600.0),
        (float("inf"), 1440.0),
    ],
)
def test_breakpoint_validation_rejects_ambiguous_ranges(
    compact_max: float,
    ultrawide_min: float,
) -> None:
    with pytest.raises(ValueError):
        ResponsiveBreakpoints(compact_max=compact_max, ultrawide_min=ultrawide_min)


def test_responsive_value_resolves_against_same_breakpoint_policy() -> None:
    value = ResponsiveValue(compact=12.0, desktop=16.0, ultrawide=20.0)
    breakpoints = ResponsiveBreakpoints(compact_max=700.0, ultrawide_min=1500.0)

    assert value.resolve(ViewportClass.COMPACT) == 12.0
    assert value.resolve_width(900.0, breakpoints=breakpoints) == 16.0
    assert value.resolve_width(1800.0, breakpoints=breakpoints) == 20.0


def test_responsive_layout_switches_direction_and_spacing_without_replacing_children() -> None:
    layout, first, second = _layout()
    first_preferred = first.preferred_size
    second_preferred = second.preferred_size

    compact = compile_component_scene(layout, width=600.0, height=420.0)
    assert compact is not None
    assert layout.current_variant is ViewportClass.COMPACT
    assert first.bounds.x == pytest.approx(16.0)
    assert second.bounds.x == pytest.approx(16.0)
    assert second.bounds.y > first.bounds.bottom
    assert first.bounds.width == pytest.approx(568.0)
    assert second.bounds.width == pytest.approx(568.0)

    desktop = compile_component_scene(layout, width=1000.0, height=420.0, generation=2)
    assert desktop is not None
    assert layout.current_variant is ViewportClass.DESKTOP
    assert first.bounds.x == pytest.approx(28.0)
    assert second.bounds.x > first.bounds.right
    assert first.bounds.y > 20.0
    assert second.bounds.y > 20.0

    assert first.preferred_size == first_preferred
    assert second.preferred_size == second_preferred
    assert first.parent is layout
    assert second.parent is layout


def test_ultrawide_variant_centers_bounded_content_region() -> None:
    layout, first, second = _layout()

    scene = compile_component_scene(layout, width=1800.0, height=500.0)

    assert scene is not None
    assert layout.current_variant is ViewportClass.ULTRAWIDE
    assert layout.bounds == Rect(0.0, 0.0, 1800.0, 500.0)
    assert first.bounds.x == pytest.approx(400.0)
    assert second.bounds.x > first.bounds.right
    assert second.bounds.right <= 1400.0


def test_responsive_layout_measurement_uses_available_width_variant() -> None:
    layout, _first, _second = _layout()

    compact_size = layout.measure(Size(600.0, 500.0))
    compact_variant = layout.current_variant
    desktop_size = layout.measure(Size(900.0, 500.0))
    desktop_variant = layout.current_variant

    assert compact_variant is ViewportClass.COMPACT
    assert desktop_variant is ViewportClass.DESKTOP
    assert compact_size.height > desktop_size.height


def test_variant_update_invalidates_retained_tree_and_applies_on_next_layout() -> None:
    layout, first, second = _layout()
    reasons: list[str] = []
    layout.on("invalidated", lambda event: reasons.append(str(event.data["reason"])))

    layout.set_variant_spec(
        ViewportClass.DESKTOP,
        ResponsiveLayoutSpec(
            direction=LayoutDirection.COLUMN,
            spacing=30.0,
            padding=40.0,
        ),
    )
    compile_component_scene(layout, width=1000.0, height=500.0)

    assert reasons == ["responsive_variant"]
    assert layout.current_variant is ViewportClass.DESKTOP
    assert first.bounds.x == pytest.approx(40.0)
    assert second.bounds.y >= first.bounds.bottom + 30.0
