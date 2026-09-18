from __future__ import annotations

from swirui import ReactiveProperty, State, bind, bind_bidirectional, computed


class Settings:
    volume = ReactiveProperty(50)
    title = ReactiveProperty("SwirUI")


def test_reactive_property_keeps_independent_state_per_instance() -> None:
    left = Settings()
    right = Settings()
    values: list[int] = []
    Settings.volume.subscribe(left, values.append, immediate=True)

    left.volume = 70

    assert left.volume == 70
    assert right.volume == 50
    assert values == [50, 70]


def test_one_way_binding_syncs_immediately_and_disposes_cleanly() -> None:
    source = State(1)
    target = State(0)
    binding = bind(source, target)

    assert target.value == 1
    source.set(2)
    assert target.value == 2

    target.set(3)
    assert source.value == 2

    binding.dispose()
    source.set(4)
    assert target.value == 3
    assert binding.active is False


def test_computed_state_can_drive_one_way_binding() -> None:
    left = State(2)
    right = State(3)
    total = computed(lambda: left.value + right.value)
    target = State(0)

    with bind(total, target):
        assert target.value == 5
        left.set(4)
        assert target.value == 7

    right.set(5)
    assert target.value == 7


def test_bidirectional_binding_propagates_both_directions_without_looping() -> None:
    left = State("left")
    right = State("right")
    binding = bind_bidirectional(left, right)

    assert right.value == "left"
    right.set("new")
    assert left.value == "new"
    left.set("again")
    assert right.value == "again"

    binding.dispose()
    left.set("stopped")
    assert right.value == "again"


def test_bidirectional_binding_can_choose_right_as_initial_source() -> None:
    left = State(1)
    right = State(2)

    binding = bind_bidirectional(left, right, initial="right")

    assert left.value == 2
    binding.dispose()
