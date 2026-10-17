import json
from dataclasses import FrozenInstanceError, replace

import pytest

from swirui import FUTURE_DARK, FUTURE_LIGHT, Input, Panel, ThemePackage, Window, mount
from swirui.rendering import Rect


def package():
    return ThemePackage(
        "Aurora – światło", {"night": FUTURE_DARK, "day": replace(
            FUTURE_LIGHT, palette=replace(FUTURE_LIGHT.palette, accent="#087B83CC"),
            font_family="Arial", monospace_family="Consolas", control_radius=8,
            motion_duration=0.2, reduced_motion=True)}, "night",
        author="Swir", description="Two appearances.\nOne workspace.", version="2.0.0",
    )


def test_package_round_trip_all_tokens_and_utf8_file(tmp_path):
    original = package()
    text = original.dumps()
    assert "światło" in text
    restored = ThemePackage.loads(text)
    assert restored == original and restored.dumps() == text
    target = tmp_path / "aurora.swirui-theme.json"
    original.save(target)
    assert target.read_text(encoding="utf-8") == text
    assert ThemePackage.load(target) == original
    assert restored.themes["day"].surface_color("accent").a == pytest.approx(0.8)


def test_package_defensively_copies_variants_and_is_immutable():
    variants = {"night": FUTURE_DARK}
    value = ThemePackage("Immutable", variants, "night")
    variants["night"] = FUTURE_LIGHT
    assert value.default is FUTURE_DARK
    with pytest.raises(TypeError):
        value.themes["night"] = FUTURE_LIGHT
    with pytest.raises(FrozenInstanceError):
        value.name = "Changed"


@pytest.mark.parametrize("field,value", [
    ("format", "other"), ("format_version", 2), ("format_version", True),
    ("name", " "), ("name", 3), ("author", None), ("version", ""),
    ("description", "x" * 2049), ("default_theme", "missing"),
    ("themes", {}), ("themes", []),
])
def test_invalid_package_metadata_is_rejected(field, value):
    document = json.loads(package().dumps())
    document[field] = value
    with pytest.raises(ValueError):
        ThemePackage.loads(json.dumps(document))


@pytest.mark.parametrize("field,value", [
    ("control_radius", True), ("control_radius", -1), ("control_radius", "12"),
    ("control_radius", 10 ** 400), ("motion_duration", float("inf")),
    ("motion_duration", float("nan")), ("reduced_motion", 1),
    ("font_family", ""), ("font_family", []), ("monospace_family", "x" * 257),
], ids=lambda value: str(value)[:32])
def test_invalid_theme_token_is_rejected(field, value):
    document = json.loads(package().dumps())
    document["themes"]["night"][field] = value
    with pytest.raises(ValueError):
        ThemePackage.loads(json.dumps(document))


@pytest.mark.parametrize("swatch", ["#123", "red", "#123456789", "#GG0000", 5, None])
def test_invalid_palette_swatch_is_rejected(swatch):
    document = json.loads(package().dumps())
    document["themes"]["night"]["palette"]["accent"] = swatch
    with pytest.raises(ValueError):
        ThemePackage.loads(json.dumps(document))


@pytest.mark.parametrize("level", ["package", "theme", "palette"])
@pytest.mark.parametrize("missing", [True, False])
def test_unknown_and_missing_fields_are_not_silently_ignored(level, missing):
    document = json.loads(package().dumps())
    target = document
    if level != "package":
        target = document["themes"]["night"]
    if level == "palette":
        target = target["palette"]
    if missing:
        target.pop(next(iter(target)))
    else:
        target["unknown_token"] = 1
    with pytest.raises(ValueError):
        ThemePackage.loads(json.dumps(document))


@pytest.mark.parametrize("source", [
    "{}", "[]", "null", '{"name":"a","name":"b"}',
    '[' * 2000 + ']' * 2000, ' ' * (256 * 1024 + 1), '"\\ud800"',
], ids=["empty", "array", "null", "duplicate", "deep", "oversized", "surrogate"])
def test_malformed_or_unbounded_json_is_rejected(source):
    with pytest.raises(ValueError):
        ThemePackage.loads(source)


def test_duplicate_nested_keys_and_nonfinite_exponents_are_rejected():
    source = package().dumps()
    with pytest.raises(ValueError, match="Duplicate JSON key"):
        ThemePackage.loads(source.replace('"control_radius": 12.0',
                                         '"control_radius": 12, "control_radius": 4'))
    with pytest.raises(ValueError, match="finite"):
        ThemePackage.loads(source.replace('"control_radius": 12.0', '"control_radius": 1e999'))


@pytest.mark.parametrize("variants,default", [
    ({"Night": FUTURE_DARK}, "Night"), ({"../night": FUTURE_DARK}, "../night"),
    ({"night": object()}, "night"), ({"night": FUTURE_DARK}, "day"),
    ({f"theme{i}": FUTURE_DARK for i in range(33)}, "theme0"),
])
def test_invalid_direct_package_is_rejected(variants, default):
    with pytest.raises(ValueError):
        ThemePackage("Invalid", variants, default)


def test_failed_atomic_save_preserves_previous_file_and_cleans_temporary(tmp_path, monkeypatch):
    target = tmp_path / "theme.json"
    target.write_bytes(b"previous content")

    def fail_replace(*args):
        raise PermissionError("simulated replacement failure")

    monkeypatch.setattr("swirui.theme_package.os.replace", fail_replace)
    with pytest.raises(PermissionError, match="replacement"):
        package().save(target)
    assert target.read_bytes() == b"previous content"
    assert list(tmp_path.iterdir()) == [target]


def test_file_decode_size_errors_and_successful_replacement(tmp_path):
    target = tmp_path / "theme.json"
    target.write_bytes(b"\xff")
    with pytest.raises(ValueError, match="UTF-8"):
        ThemePackage.load(target)
    target.write_bytes(b" " * (256 * 1024 + 1))
    with pytest.raises(ValueError, match="256 KiB"):
        ThemePackage.load(target)
    package().save(target)
    assert ThemePackage.load(target) == package()
    assert list(tmp_path.iterdir()) == [target]


def test_loaded_variants_preserve_active_input_and_local_theme(tmp_path):
    target = tmp_path / "theme.json"
    package().save(target)
    loaded = ThemePackage.load(target)
    root = Panel(bounds=Rect(0, 0, 500, 240), theme=loaded.default)
    edit = Input("Keep my draft", bounds=Rect(10, 10, 300, 44))
    local = Input("Independent", bounds=Rect(10, 80, 300, 44), theme=FUTURE_DARK)
    root.add(edit, local)
    window = Window()
    runtime = mount(window, root)
    try:
        window.focus_component(edit)
        edit.select(2, 6)
        root.theme = loaded.themes["day"]
        assert edit.value == "Keep my draft"
        assert (edit.selection_start, edit.selection_end) == (2, 6)
        assert window.focused_component is edit
        assert edit.effective_theme is loaded.themes["day"]
        assert any(node.text == "Keep my draft" and node.font_family == "Arial"
                   for node in edit.build_scene_node().walk())
        assert local.effective_theme is FUTURE_DARK
        with pytest.raises(ValueError):
            root.theme = ThemePackage.loads('{"format_version":99}').default
        assert root.theme is loaded.themes["day"]
    finally:
        runtime.unmount()
