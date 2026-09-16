import pytest

from swirui.core import AppConfig, VisualQuality, configure_logging


def test_app_config_defaults() -> None:
    config = AppConfig()

    assert config.visual_quality is VisualQuality.AUTO
    assert config.target_fps == 60
    assert config.debug is False


def test_app_config_rejects_invalid_fps() -> None:
    with pytest.raises(ValueError, match="target_fps"):
        AppConfig(target_fps=0)


def test_configure_logging_is_idempotent() -> None:
    first = configure_logging(debug=False)
    before = len(first.handlers)
    second = configure_logging(debug=True)

    assert first is second
    assert len(second.handlers) == before
    assert second.level > 0
