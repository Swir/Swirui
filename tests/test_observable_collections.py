from __future__ import annotations

from swirui import ObservableDict, ObservableList, computed, state_transaction


def test_observable_list_reads_drive_computed_state() -> None:
    values = ObservableList([1, 2])
    total = computed(lambda: sum(values))
    observed: list[int] = []
    total.subscribe(observed.append)

    values.append(3)
    values.set(0, 4)

    assert values.snapshot() == (4, 2, 3)
    assert total.value == 9
    assert observed == [6, 9]


def test_observable_list_batches_notifications_with_state_transaction() -> None:
    values = ObservableList([1])
    snapshots: list[tuple[int, ...]] = []
    values.subscribe(snapshots.append)

    with state_transaction():
        values.append(2)
        values.append(3)
        values.remove(1)
        assert snapshots == []

    assert snapshots == [(2, 3)]


def test_observable_dict_defends_internal_snapshot() -> None:
    values = ObservableDict({"a": 1})
    snapshots: list[dict[str, int]] = []
    values.subscribe(snapshots.append, immediate=True)

    snapshots[0]["a"] = 99
    assert values["a"] == 1

    values.set("b", 2)
    assert values.snapshot() == {"a": 1, "b": 2}
    assert snapshots[-1] == {"a": 1, "b": 2}


def test_observable_dict_reads_drive_computed_state() -> None:
    values = ObservableDict({"x": 2, "y": 3})
    product = computed(lambda: values["x"] * values["y"])

    values.set("x", 4)
    assert product.value == 12

    values.set("z", 5)
    assert product.value == 12
    assert values.pop("z") == 5
    assert "z" not in values
