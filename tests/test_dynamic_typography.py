import math

import pytest

from swirui import (
    Button,
    Column,
    CrossAxisAlignment,
    DynamicTypography,
    Input,
    Label,
    ResponsiveValue,
    ViewportClass,
    Window,
    mount,
)
from swirui.rendering import Rect, Scene, Size
from swirui.widgets import compile_component_scene


def _scope() -> tuple[DynamicTypography, Column, Label, Button, Input]:
    title = Label(
        "Dynamic typography",
        key="type-title",
        bounds=Rect(0.0, 0.0, 120.0, 30.0),
        font_size=20.0,
    )
    button = Button(
        "Continue with responsive typography",
        key="type-button",
        bounds=Rect(0.0, 0.0, 120.0, 44.0),
        font_size=16.0,
    )
    field = Input(
        "Responsive typography input",
        key="type-input",
        bounds=Rect(0.0, 0.0, 180.0, 44.0),
        font_size=16.0,
    )
    content = Column(
        key="type-content",
        bounds=Rect(0.0, 0.0, 1.0, 1.0),
        fill_viewport=True,
        spacing=12.0,
        cross_alignment=CrossAxisAlignment.START,
    )
    content.add(title, button, field)
    scope = DynamicTypography(
        content,
        key="type-scope",
        bounds=Rect(0.0, 0.0, 1.0, 1.0),
        fill_viewport=True,
        scales=ResponsiveValue(compact=0.8, desktop=1.0, ultrawide=1.25),
    )
    return scope, content, title, button, field


def _font_sizes(scene: Scene | None) -> dict[str, float]:
    assert scene is not None
    return {node.key: node.font_size for node in scene.walk() if node.text is not None}


def test_dynamic_typography_scales_all_core_text_bearing_widgets() -> None:
    scope, _content, _title, _button, _field = _scope()

    compact = compile_component_scene(scope, width=600.0, height=320.0)
    compact_fonts = _font_sizes(compact)
    assert scope.current_variant is ViewportClass.COMPACT
    assert scope.current_scale == pytest.approx(0.8)
    assert compact_fonts["type-title"] == pytest.approx(16.0)
    assert compact_fonts["type-button:content"] == pytest.approx(12.8)
    assert compact_fonts["type-input:text"] == pytest.approx(12.8)

    desktop = compile_component_scene(scope, width=1000.0, height=320.0, generation=2)
    desktop_fonts = _font_sizes(desktop)
    assert scope.current_variant is ViewportClass.DESKTOP
    assert desktop_fonts["type-title"] == pytest.approx(20.0)
    assert desktop_fonts["type-button:content"] == pytest.approx(16.0)
    assert desktop_fonts["type-input:text"] == pytest.approx(16.0)

    ultrawide = compile_component_scene(scope, width=1800.0, height=320.0, generation=3)
    ultrawide_fonts = _font_sizes(ultrawide)
    assert scope.current_variant is ViewportClass.ULTRAWIDE
    assert ultrawide_fonts["type-title"] == pytest.approx(25.0)
    assert ultrawide_fonts["type-button:content"] == pytest.approx(20.0)
    assert ultrawide_fonts["type-input:text"] == pytest.approx(20.0)


def test_repeated_reflow_does_not_compound_typography_scale() -> None:
    scope, _content, title, _button, _field = _scope()

    first = compile_component_scene(scope, width=600.0, height=320.0)
    second = compile_component_scene(scope, width=600.0, height=320.0, generation=2)

    assert _font_sizes(first)["type-title"] == pytest.approx(16.0)
    assert _font_sizes(second)["type-title"] == pytest.approx(16.0)
    assert title.font_size == pytest.approx(16.0)

    desktop = compile_component_scene(scope, width=1000.0, height=320.0, generation=3)
    assert _font_sizes(desktop)["type-title"] == pytest.approx(20.0)


def test_public_font_size_change_becomes_new_authored_baseline() -> None:
    scope, _content, title, _button, _field = _scope()
    compile_component_scene(scope, width=600.0, height=320.0)

    title.font_size = 30.0
    compact = compile_component_scene(scope, width=600.0, height=320.0, generation=2)
    desktop = compile_component_scene(scope, width=1000.0, height=320.0, generation=3)

    assert _font_sizes(compact)["type-title"] == pytest.approx(24.0)
    assert _font_sizes(desktop)["type-title"] == pytest.approx(30.0)


def test_typography_scale_affects_intrinsic_measurement_before_arrangement() -> None:
    scope, _content, title, button, field = _scope()

    scope.measure(Size(600.0, 320.0))
    compact_title = title.intrinsic_size()
    compact_button = button.intrinsic_size()
    compact_field = field.intrinsic_size(Size(400.0, 200.0))

    scope.measure(Size(1800.0, 320.0))
    ultrawide_title = title.intrinsic_size()
    ultrawide_button = button.intrinsic_size()
    ultrawide_field = field.intrinsic_size(Size(400.0, 200.0))

    assert ultrawide_title.height > compact_title.height
    assert ultrawide_title.width > compact_title.width
    assert ultrawide_button.width > compact_button.width
    assert ultrawide_field.width > compact_field.width


def test_scale_update_invalidates_once_and_applies_on_next_compile() -> None:
    scope, _content, _title, _button, _field = _scope()
    reasons: list[str] = []
    scope.on("invalidated", lambda event: reasons.append(str(event.data["reason"])))

    scope.scales = ResponsiveValue(compact=0.75, desktop=1.05, ultrawide=1.4)
    scene = compile_component_scene(scope, width=1000.0, height=320.0)

    assert reasons == ["dynamic_typography_scales"]
    assert scope.current_scale == pytest.approx(1.05)
    assert _font_sizes(scene)["type-title"] == pytest.approx(21.0)


@pytest.mark.parametrize(
    "scales",
    [
        ResponsiveValue(compact=0.0, desktop=1.0, ultrawide=1.1),
        ResponsiveValue(compact=0.9, desktop=-1.0, ultrawide=1.1),
        ResponsiveValue(compact=0.9, desktop=1.0, ultrawide=math.inf),
    ],
)
def test_invalid_typography_scales_are_rejected(scales: ResponsiveValue[float]) -> None:
    content = Label("Text", bounds=Rect(0.0, 0.0, 100.0, 30.0))
    with pytest.raises(ValueError):
        DynamicTypography(content, bounds=Rect(0.0, 0.0, 100.0, 30.0), scales=scales)


def test_window_resize_preserves_focus_and_component_identity() -> None:
    scope, content, _title, _button, field = _scope()
    window = Window(width=600, height=320)
    runtime = mount(window, scope)
    window.focus_component(field)
    initial_generation = runtime.generation

    window.resize(1000, 320)

    assert runtime.generation > initial_generation
    assert scope.current_variant is ViewportClass.DESKTOP
    assert window.focused_component is field
    assert field.parent is content
    assert content.parent is scope
