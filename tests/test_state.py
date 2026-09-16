from swirui.core import State


def test_state_notifies_only_on_change() -> None:
    state = State(1)
    values: list[int] = []

    state.subscribe(values.append)

    assert state.set(1) is False
    assert state.set(2) is True
    assert values == [2]


def test_state_immediate_subscription_and_unsubscribe() -> None:
    state = State("ready")
    values: list[str] = []

    unsubscribe = state.subscribe(values.append, immediate=True)
    state.set("running")
    unsubscribe()
    state.set("done")

    assert values == ["ready", "running"]


def test_state_update() -> None:
    state = State(10)

    changed = state.update(lambda value: value + 5)

    assert changed is True
    assert state.value == 15
