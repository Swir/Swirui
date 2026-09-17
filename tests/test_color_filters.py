import math

import pytest

from swirui.rendering import ColorFilter


def _apply(color_filter: ColorFilter, rgba: tuple[float, float, float, float]) -> tuple[float, ...]:
    matrix = color_filter.matrix
    return tuple(
        sum(matrix[row * 5 + column] * rgba[column] for column in range(4))
        + matrix[row * 5 + 4]
        for row in range(4)
    )


def test_identity_and_native_packing_preserve_rgba() -> None:
    color_filter = ColorFilter.identity()
    rgba = (0.2, 0.4, 0.8, 0.65)
    assert _apply(color_filter, rgba) == pytest.approx(rgba)
    packed = color_filter.native_values()
    assert len(packed) == 20
    assert packed[:16] == (
        1.0,
        0.0,
        0.0,
        0.0,
        0.0,
        1.0,
        0.0,
        0.0,
        0.0,
        0.0,
        1.0,
        0.0,
        0.0,
        0.0,
        0.0,
        1.0,
    )
    assert packed[16:] == (0.0, 0.0, 0.0, 0.0)


def test_presets_keep_alpha_and_have_expected_endpoints() -> None:
    rgba = (0.1, 0.4, 0.9, 0.35)
    gray = _apply(ColorFilter.grayscale(), rgba)
    assert gray[0] == pytest.approx(gray[1])
    assert gray[1] == pytest.approx(gray[2])
    assert gray[3] == pytest.approx(rgba[3])

    inverted = _apply(ColorFilter.invert(), rgba)
    assert inverted == pytest.approx((0.9, 0.6, 0.1, 0.35))
    assert _apply(ColorFilter.invert(0.0), rgba) == pytest.approx(rgba)
    assert _apply(ColorFilter.sepia(0.0), rgba) == pytest.approx(rgba)


def test_composition_matches_two_sequential_affine_transforms() -> None:
    rgba = (0.18, 0.53, 0.82, 0.7)
    first = ColorFilter.contrast(1.35)
    second = ColorFilter.hue_rotate(42.0)
    sequential = _apply(second, _apply(first, rgba))
    combined = _apply(first.then(second), rgba)
    assert combined == pytest.approx(sequential)


def test_hue_rotation_is_periodic() -> None:
    color = (0.17, 0.61, 0.43, 1.0)
    assert _apply(ColorFilter.hue_rotate(45.0), color) == pytest.approx(
        _apply(ColorFilter.hue_rotate(405.0), color)
    )


def test_rejects_invalid_matrix_and_preset_parameters() -> None:
    with pytest.raises(ValueError, match="exactly 20"):
        ColorFilter((1.0,) * 19)  # type: ignore[arg-type]
    values = list(ColorFilter.identity().matrix)
    values[3] = math.inf
    with pytest.raises(ValueError, match="finite"):
        ColorFilter(tuple(values))  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="between"):
        ColorFilter.grayscale(1.1)
    with pytest.raises(ValueError, match="between"):
        ColorFilter.brightness(-0.1)
    with pytest.raises(ValueError, match="finite"):
        ColorFilter.hue_rotate(math.nan)
