from __future__ import annotations

import pytest

from swirui import ComputedState, State, computed, state_transaction


def test_computed_state_tracks_sources_and_notifies_only_on_change() -> None:
    left = State(2)
    right = State(3)
    total = computed(lambda: left.value + right.value)
    values: list[int] = []

    total.subscribe(values.append, immediate=True)
    left.set(4)
    right.set(1)

    assert total.value == 5
    assert values == [5, 7, 5]


def test_computed_state_switches_dynamic_dependencies() -> None:
    use_left = State(True)
    left = State(10)
    right = State(20)
    selected = computed(lambda: left.value if use_left.value else right.value)
    values: list[int] = []
    selected.subscribe(values.append)

    right.set(21)
    use_left.set(False)
    left.set(11)
    right.set(22)

    assert selected.value == 22
    assert values == [21, 22]


def test_state_transaction_coalesces_notifications_and_recomputation() -> None:
    left = State(1)
    right = State(2)
    compute_calls = 0

    def calculate() -> int:
        nonlocal compute_calls
        compute_calls += 1
        return left.value + right.value

    total = ComputedState(calculate)
    left_values: list[int] = []
    total_values: list[int] = []
    left.subscribe(left_values.append)
    total.subscribe(total_values.append)

    with state_transaction():
        left.set(2)
        left.set(3)
        right.set(4)
        assert left_values == []
        assert total_values == []
        assert total.value == 3

    assert left_values == [3]
    assert total.value == 7
    assert total_values == [7]
    assert compute_calls == 2


def test_state_transaction_drops_reverted_notification() -> None:
    state = State(1)
    values: list[int] = []
    state.subscribe(values.append)

    with state_transaction():
        state.set(2)
        state.set(1)

    assert values == []


def test_nested_transactions_flush_only_at_outer_boundary() -> None:
    state = State(0)
    values: list[int] = []
    state.subscribe(values.append)

    with state_transaction():
        state.set(1)
        with state_transaction():
            state.set(2)
        assert values == []

    assert values == [2]


def test_computed_chain_recomputes_in_dependency_order_once_per_batch() -> None:
    base = State(1)
    doubled_calls = 0
    combined_calls = 0

    def calculate_doubled() -> int:
        nonlocal doubled_calls
        doubled_calls += 1
        return base.value * 2

    doubled = computed(calculate_doubled)

    def calculate_combined() -> int:
        nonlocal combined_calls
        combined_calls += 1
        return doubled.value + base.value

    combined = computed(calculate_combined)

    with state_transaction():
        base.set(2)
        base.set(3)

    assert doubled.value == 6
    assert combined.value == 9
    assert doubled_calls == 2
    assert combined_calls == 2


def test_transaction_exception_flushes_applied_writes() -> None:
    state = State(0)
    values: list[int] = []
    state.subscribe(values.append)

    with pytest.raises(RuntimeError, match="boom"):
        with state_transaction():
            state.set(1)
            raise RuntimeError("boom")

    assert state.value == 1
    assert values == [1]


def test_computed_dispose_detaches_dependencies_and_subscribers() -> None:
    state = State(1)
    doubled = computed(lambda: state.value * 2)
    values: list[int] = []
    doubled.subscribe(values.append)

    doubled.dispose()
    state.set(2)

    assert doubled.value == 2
    assert values == []
    with pytest.raises(RuntimeError, match="disposed"):
        doubled.subscribe(values.append)
