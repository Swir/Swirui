import pytest

from swirui.core import AppConfig, PresentationMode, VisualQuality, configure_logging


def test_app_config_defaults() -> None:
    config = AppConfig()

    assert config.visual_quality is VisualQuality.AUTO
    assert config.target_fps == 60
    assert config.debug is False
    assert config.presentation_mode is PresentationMode.AUTO_VSYNC
    assert config.maximum_frame_latency == 1


def test_app_config_rejects_invalid_fps() -> None:
    with pytest.raises(ValueError, match="target_fps"):
        AppConfig(target_fps=0)


def test_app_config_accepts_low_latency_presentation() -> None:
    config = AppConfig(
        presentation_mode=PresentationMode.AUTO_NO_VSYNC,
        maximum_frame_latency=2,
        target_fps=144,
    )

    assert config.presentation_mode is PresentationMode.AUTO_NO_VSYNC
    assert config.maximum_frame_latency == 2
    assert config.target_fps == 144


def test_app_config_rejects_invalid_frame_latency() -> None:
    with pytest.raises(ValueError, match="maximum_frame_latency"):
        AppConfig(maximum_frame_latency=0)


def test_configure_logging_is_idempotent() -> None:
    first = configure_logging(debug=False)
    before = len(first.handlers)
    second = configure_logging(debug=True)

    assert first is second
    assert len(second.handlers) == before
    assert second.level > 0
