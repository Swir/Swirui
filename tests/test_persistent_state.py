from __future__ import annotations

import json
from pathlib import Path

import pytest

from swirui import PersistentState


def test_persistent_state_starts_from_default_without_eager_file(tmp_path: Path) -> None:
    path = tmp_path / "settings" / "theme.json"
    state = PersistentState(path, "dark")

    assert state.value == "dark"
    assert state.path == path
    assert not path.exists()


def test_persistent_state_set_is_atomic_and_reactive(tmp_path: Path) -> None:
    path = tmp_path / "volume.json"
    state = PersistentState(path, 25)
    values: list[int] = []
    state.subscribe(values.append)

    assert state.set(70) is True
    assert state.value == 70
    assert values == [70]
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "schema": 1,
        "value": 70,
    }
    assert not list(tmp_path.glob(".*.tmp"))

    restored = PersistentState(path, 0)
    assert restored.value == 70


def test_persistent_state_reload_observes_external_compatible_change(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    state = PersistentState(path, {"count": 1})
    state.persist()
    values: list[dict[str, int]] = []
    state.subscribe(values.append)

    path.write_text('{"schema": 1, "value": {"count": 9}}\n', encoding="utf-8")

    assert state.reload() is True
    assert state.value == {"count": 9}
    assert values == [{"count": 9}]

    path.unlink()
    assert state.reload() is True
    assert state.value == {"count": 1}


def test_persistent_state_custom_codec_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "coordinates.json"

    state = PersistentState(
        path,
        (1, 2),
        encode=lambda value: list(value),
        decode=lambda value: tuple(int(item) for item in value),
    )
    state.set((7, 8))

    restored = PersistentState(
        path,
        (0, 0),
        encode=lambda value: list(value),
        decode=lambda value: tuple(int(item) for item in value),
    )
    assert restored.value == (7, 8)


def test_persistent_state_failed_encoding_does_not_publish_change(tmp_path: Path) -> None:
    path = tmp_path / "safe.json"

    def encode(value: int) -> object:
        if value == 2:
            raise ValueError("cannot encode")
        return value

    state = PersistentState(path, 1, encode=encode)
    values: list[int] = []
    state.subscribe(values.append)

    with pytest.raises(ValueError, match="cannot encode"):
        state.set(2)

    assert state.value == 1
    assert values == []
    assert not path.exists()


def test_persistent_state_rejects_corrupt_or_unknown_schema(tmp_path: Path) -> None:
    path = tmp_path / "broken.json"
    path.write_text("not json", encoding="utf-8")

    with pytest.raises(ValueError, match="Could not read persistent state"):
        PersistentState(path, 1)

    path.write_text('{"schema": 999, "value": 5}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="unsupported or invalid schema"):
        PersistentState(path, 1)
