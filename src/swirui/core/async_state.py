"""Async reactive state primitives for SwirUI."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Generic, TypeVar

from .state import State

T = TypeVar("T")


class AsyncStatus(StrEnum):
    """Lifecycle state for one :class:`AsyncState` operation."""

    IDLE = "idle"
    RUNNING = "running"
    READY = "ready"
    ERROR = "error"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class AsyncSnapshot(Generic[T]):
    """Immutable observable snapshot published by :class:`AsyncState`."""

    status: AsyncStatus
    value: T | None = None
    error: BaseException | None = None

    @property
    def loading(self) -> bool:
        return self.status is AsyncStatus.RUNNING


class AsyncState(Generic[T]):
    """Reactive latest-operation state integrated with ``asyncio``.

    ``run()`` owns one active operation at a time. Starting a replacement cancels the
    previous task and uses a generation guard so stale completions can never overwrite
    newer state. Exceptions remain visible through the returned task while the reactive
    snapshot records the failure for UI bindings.
    """

    __slots__ = ("_generation", "_state", "_task")

    def __init__(self, initial: T | None = None) -> None:
        self._generation = 0
        self._state = State(AsyncSnapshot(AsyncStatus.IDLE, value=initial))
        self._task: asyncio.Task[T] | None = None

    @property
    def snapshot(self) -> AsyncSnapshot[T]:
        return self._state.value

    @property
    def status(self) -> AsyncStatus:
        return self.snapshot.status

    @property
    def value(self) -> T | None:
        return self.snapshot.value

    @property
    def error(self) -> BaseException | None:
        return self.snapshot.error

    @property
    def loading(self) -> bool:
        return self.snapshot.loading

    @property
    def active_task(self) -> asyncio.Task[T] | None:
        task = self._task
        if task is None or task.done():
            return None
        return task

    def subscribe(
        self,
        subscriber: Callable[[AsyncSnapshot[T]], None],
        *,
        immediate: bool = False,
    ) -> Callable[[], None]:
        """Subscribe to immutable async snapshots."""

        return self._state.subscribe(subscriber, immediate=immediate)

    def run(
        self,
        operation: Callable[[], Awaitable[T]],
        *,
        cancel_previous: bool = True,
    ) -> asyncio.Task[T]:
        """Schedule ``operation`` on the current event loop and publish its lifecycle.

        By default a still-running previous operation is cancelled. Passing
        ``cancel_previous=False`` rejects overlapping work instead of making completion
        order ambiguous.
        """

        previous = self.active_task
        if previous is not None:
            if not cancel_previous:
                raise RuntimeError("AsyncState already has an active operation.")
            previous.cancel()

        self._generation += 1
        generation = self._generation
        current_value = self.snapshot.value
        self._state.set(AsyncSnapshot(AsyncStatus.RUNNING, value=current_value))

        async def execute() -> T:
            try:
                result = await operation()
            except asyncio.CancelledError:
                if self._generation == generation:
                    self._state.set(
                        AsyncSnapshot(AsyncStatus.CANCELLED, value=self.snapshot.value)
                    )
                raise
            except BaseException as exc:
                if self._generation == generation:
                    self._state.set(
                        AsyncSnapshot(
                            AsyncStatus.ERROR,
                            value=self.snapshot.value,
                            error=exc,
                        )
                    )
                raise
            else:
                if self._generation == generation:
                    self._state.set(AsyncSnapshot(AsyncStatus.READY, value=result))
                return result
            finally:
                if self._generation == generation and self._task is asyncio.current_task():
                    self._task = None

        task = asyncio.create_task(execute())
        self._task = task
        return task

    def cancel(self) -> bool:
        """Request cancellation of the active operation, if any."""

        task = self.active_task
        if task is None:
            return False
        return task.cancel()

    def __repr__(self) -> str:
        snapshot = self.snapshot
        return f"AsyncState(status={snapshot.status.value!r}, value={snapshot.value!r})"
