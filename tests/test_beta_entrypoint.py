import json
from types import SimpleNamespace

import pytest

from swirui import __main__ as cli
from swirui import __version__, diagnostics
from swirui.demo import Demo


def windows(monkeypatch):
    monkeypatch.setattr(diagnostics.sys, "platform", "win32")
    monkeypatch.setattr(diagnostics.platform, "machine", lambda: "AMD64")


def test_doctor_does_not_claim_gpu_evidence_for_a_loaded_extension(monkeypatch):
    windows(monkeypatch)
    monkeypatch.setattr(diagnostics.importlib, "import_module", lambda _: SimpleNamespace(
        core_version=lambda: __version__.replace("b", "-beta.")))
    report = diagnostics.installation_report()
    assert report["ready"] and report["native_available"]
    assert not report["gpu_tested"]


@pytest.mark.parametrize("error", [ImportError("missing"), OSError("DLL load failed")])
def test_broken_native_installation_has_actionable_diagnostics(monkeypatch, error):
    windows(monkeypatch)

    def missing(_):
        raise error

    monkeypatch.setattr(diagnostics.importlib, "import_module", missing)
    report = diagnostics.installation_report()
    assert not report["ready"]
    assert "--only-binary" in report["message"]
    assert str(error) in report["message"]


def test_stale_native_extension_is_not_reported_ready(monkeypatch):
    windows(monkeypatch)
    monkeypatch.setattr(diagnostics.importlib, "import_module", lambda _: SimpleNamespace(
        core_version=lambda: "0.0.1"))
    report = diagnostics.installation_report()
    assert not report["ready"] and report["native_available"]
    assert "versions differ" in report["message"]


def test_unsupported_platform_never_opens_demo(monkeypatch, capsys):
    monkeypatch.setattr(diagnostics.sys, "platform", "linux")
    assert cli.main(["doctor", "--json"]) == 1
    report = json.loads(capsys.readouterr().out)
    assert not report["supported_beta_platform"]
    assert cli.main(["demo"]) == 1
    assert "Windows x64" in capsys.readouterr().err


def test_demo_preserves_edits_and_updates_material_depth_on_resize():
    demo = Demo()
    demo.field.value = "A real user draft"
    demo.field.select(2, 6)
    demo.keep_ideas.checked = False
    demo.depth.value = 6
    for width, height in ((800, 600), (1400, 900), (920, 680)):
        demo.resize_to(width, height)
        for kind in ("solid", "glass", "acrylic"):
            demo.buttons[kind].emit("click")
            demo.mode.emit("click")
            assert demo.theme.surface_style.kind == kind
            assert demo.theme.surface_style.depth_layers == 6
            assert demo.field.value == "A real user draft" and demo.field.selected_text == "real"
            assert not demo.keep_ideas.checked
            assert demo.field.bounds.right < width
            assert demo.result.bounds.bottom <= demo.surface.bounds.bottom
    demo.create.emit("click")
    assert demo.result.text == "Ready to build!"
    demo.field.value = " "
    demo.create.emit("click")
    assert demo.result.text == "Give your idea a name."
