from __future__ import annotations

import asyncio
from contextlib import suppress

import pytest

from swirui import AsyncState, AsyncStatus, computed


def test_async_state_success_publishes_loading_and_ready() -> None:
    async def scenario() -> None:
        state = AsyncState[int]()
        gate = asyncio.Event()
        statuses: list[AsyncStatus] = []
        state.subscribe(lambda snapshot: statuses.append(snapshot.status), immediate=True)

        async def load() -> int:
            await gate.wait()
            return 42

        task = state.run(load)
        await asyncio.sleep(0)

        assert state.loading is True
        assert state.status is AsyncStatus.RUNNING
        assert state.value is None

        gate.set()
        assert await task == 42
        assert state.loading is False
        assert state.status is AsyncStatus.READY
        assert state.value == 42
        assert state.error is None
        assert statuses == [AsyncStatus.IDLE, AsyncStatus.RUNNING, AsyncStatus.READY]

    asyncio.run(scenario())


def test_async_state_failure_is_reactive_and_still_propagates() -> None:
    async def scenario() -> None:
        state = AsyncState[str]("cached")
        failure = RuntimeError("network down")

        async def load() -> str:
            raise failure

        task = state.run(load)
        with pytest.raises(RuntimeError, match="network down"):
            await task

        assert state.status is AsyncStatus.ERROR
        assert state.value == "cached"
        assert state.error is failure

    asyncio.run(scenario())


def test_async_state_replacement_cancels_stale_operation() -> None:
    async def scenario() -> None:
        state = AsyncState[int](1)
        first_gate = asyncio.Event()

        async def first() -> int:
            await first_gate.wait()
            return 2

        async def second() -> int:
            await asyncio.sleep(0)
            return 3

        first_task = state.run(first)
        await asyncio.sleep(0)
        second_task = state.run(second)

        with suppress(asyncio.CancelledError):
            await first_task
        assert await second_task == 3
        assert state.status is AsyncStatus.READY
        assert state.value == 3
        assert state.active_task is None

    asyncio.run(scenario())


def test_async_state_rejects_overlap_when_cancellation_is_disabled() -> None:
    async def scenario() -> None:
        state = AsyncState[int]()
        gate = asyncio.Event()

        async def load() -> int:
            await gate.wait()
            return 1

        task = state.run(load)
        await asyncio.sleep(0)
        with pytest.raises(RuntimeError, match="active operation"):
            state.run(load, cancel_previous=False)

        gate.set()
        assert await task == 1

    asyncio.run(scenario())


def test_async_state_value_participates_in_computed_dependencies() -> None:
    async def scenario() -> None:
        state = AsyncState[int](2)
        doubled = computed(lambda: (state.value or 0) * 2)
        values: list[int] = []
        doubled.subscribe(values.append)

        async def load() -> int:
            return 5

        assert await state.run(load) == 5
        assert doubled.value == 10
        assert values == [10]

    asyncio.run(scenario())
