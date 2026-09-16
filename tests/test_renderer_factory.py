import pytest

from swirui.rendering import NullRenderer, WgpuRenderer, Win32PreviewRenderer, factory


def test_renderer_factory_is_headless_off_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(factory.sys, "platform", "linux")

    renderer = factory.create_renderer()

    assert isinstance(renderer, NullRenderer)


def test_renderer_factory_prefers_wgpu_on_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    native = object()
    monkeypatch.setattr(factory.sys, "platform", "win32")
    monkeypatch.setattr(factory.importlib, "import_module", lambda _name: native)

    renderer = factory.create_renderer()

    assert isinstance(renderer, WgpuRenderer)


def test_renderer_factory_uses_preview_when_native_core_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(factory.sys, "platform", "win32")

    def missing_native(_name: str) -> object:
        raise ImportError("native core not installed")

    monkeypatch.setattr(factory.importlib, "import_module", missing_native)

    renderer = factory.create_renderer()

    assert isinstance(renderer, Win32PreviewRenderer)
