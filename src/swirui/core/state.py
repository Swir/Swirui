"""Reactive state primitives for SwirUI."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager, suppress
from contextvars import ContextVar, Token
from threading import RLock, local
from typing import Any, Generic, Protocol, TypeVar, cast

T = TypeVar("T")
S_co = TypeVar("S_co", covariant=True)
Subscriber = Callable[[T], None]


class _ReactiveSource(Protocol[S_co]):
    @property
    def value(self) -> S_co: ...

    def subscribe(
        self,
        subscriber: Subscriber[S_co],
        *,
        immediate: bool = False,
    ) -> Callable[[], None]: ...


_Dependency = _ReactiveSource[Any]
_dependency_collector: ContextVar[list[_Dependency] | None] = ContextVar(
    "swirui_dependency_collector",
    default=None,
)
_evaluation_stack: ContextVar[tuple[int, ...]] = ContextVar(
    "swirui_computed_evaluation_stack",
    default=(),
)


def _record_dependency(source: _Dependency) -> None:
    collector = _dependency_collector.get()
    if collector is not None:
        collector.append(source)


class _BatchRuntime(local):
    def __init__(self) -> None:
        self.depth = 0
        self.flushing = False
        self.pending_notifications: dict[object, Callable[[], None]] = {}
        self.pending_computed: dict[ComputedState[Any], None] = {}


_batch_runtime = _BatchRuntime()


def _defer_notifications() -> bool:
    return _batch_runtime.depth > 0 or _batch_runtime.flushing


def _schedule_notification(source: object, callback: Callable[[], None]) -> None:
    _batch_runtime.pending_notifications.setdefault(source, callback)


def _schedule_computed(state: ComputedState[Any]) -> None:
    if _defer_notifications():
        _batch_runtime.pending_computed.setdefault(state, None)
        return
    state._recompute()


def _flush_computed() -> None:
    pending = _batch_runtime.pending_computed
    while pending:
        ready = [
            state
            for state in pending
            if not any(
                isinstance(dependency, ComputedState) and dependency in pending
                for dependency in state._dependencies_snapshot()
            )
        ]
        if not ready:
            raise RuntimeError("Reactive dependency cycle detected while flushing computed state.")
        for state in ready:
            pending.pop(state, None)
            state._recompute()


def _flush_batch() -> None:
    if _batch_runtime.flushing:
        return

    _batch_runtime.flushing = True
    try:
        while _batch_runtime.pending_notifications or _batch_runtime.pending_computed:
            if _batch_runtime.pending_notifications:
                callbacks = tuple(_batch_runtime.pending_notifications.values())
                _batch_runtime.pending_notifications.clear()
                for callback in callbacks:
                    callback()
            _flush_computed()
    finally:
        _batch_runtime.flushing = False


@contextmanager
def state_transaction() -> Iterator[None]:
    """Batch state notifications and computed updates until the outer transaction exits.

    Transactions coalesce notifications; they are not rollback boundaries. If an exception
    leaves the block, writes that already happened remain applied and are flushed normally.
    """

    _batch_runtime.depth += 1
    try:
        yield
    finally:
        _batch_runtime.depth -= 1
        if _batch_runtime.depth == 0:
            _flush_batch()


class State(Generic[T]):
    """Thread-safe observable value used by the reactive runtime."""

    __slots__ = ("_value", "_subscribers", "_lock")

    def __init__(self, value: T) -> None:
        self._value = value
        self._subscribers: list[Subscriber[T]] = []
        self._lock = RLock()

    @property
    def value(self) -> T:
        _record_dependency(cast(_Dependency, self))
        with self._lock:
            return self._value

    def get(self) -> T:
        return self.value

    def set(self, value: T) -> bool:
        with self._lock:
            if value == self._value:
                return False
            previous = self._value
            self._value = value

        if _defer_notifications():
            _schedule_notification(
                self,
                lambda: self._notify_if_changed(previous),
            )
        else:
            self._notify_subscribers(value)
        return True

    def update(self, updater: Callable[[T], T]) -> bool:
        return self.set(updater(self.value))

    def subscribe(
        self,
        subscriber: Subscriber[T],
        *,
        immediate: bool = False,
    ) -> Callable[[], None]:
        with self._lock:
            if subscriber not in self._subscribers:
                self._subscribers.append(subscriber)
            current = self._value

        if immediate:
            subscriber(current)

        def unsubscribe() -> None:
            with self._lock, suppress(ValueError):
                self._subscribers.remove(subscriber)

        return unsubscribe

    def _notify_if_changed(self, previous: T) -> None:
        with self._lock:
            current = self._value
        if current != previous:
            self._notify_subscribers(current)

    def _notify_subscribers(self, value: T) -> None:
        with self._lock:
            subscribers = tuple(self._subscribers)
        for subscriber in subscribers:
            subscriber(value)

    def __repr__(self) -> str:
        return f"State({self.value!r})"


class ComputedState(Generic[T]):
    """Read-only state derived from automatically tracked reactive dependencies."""

    __slots__ = (
        "_compute",
        "_dependencies",
        "_dependency_unsubscribers",
        "_disposed",
        "_lock",
        "_subscribers",
        "_value",
    )

    def __init__(self, compute: Callable[[], T]) -> None:
        self._compute = compute
        self._dependencies: tuple[_Dependency, ...] = ()
        self._dependency_unsubscribers: dict[_Dependency, Callable[[], None]] = {}
        self._disposed = False
        self._lock = RLock()
        self._subscribers: list[Subscriber[T]] = []
        self._value = self._evaluate_and_bind()

    @property
    def value(self) -> T:
        _record_dependency(cast(_Dependency, self))
        with self._lock:
            return self._value

    def get(self) -> T:
        return self.value

    def subscribe(
        self,
        subscriber: Subscriber[T],
        *,
        immediate: bool = False,
    ) -> Callable[[], None]:
        with self._lock:
            if self._disposed:
                raise RuntimeError("Cannot subscribe to a disposed ComputedState.")
            if subscriber not in self._subscribers:
                self._subscribers.append(subscriber)
            current = self._value

        if immediate:
            subscriber(current)

        def unsubscribe() -> None:
            with self._lock, suppress(ValueError):
                self._subscribers.remove(subscriber)

        return unsubscribe

    def dispose(self) -> None:
        """Detach this computed value from its dependencies."""

        with self._lock:
            if self._disposed:
                return
            self._disposed = True
            unsubscribers = tuple(self._dependency_unsubscribers.values())
            self._dependency_unsubscribers.clear()
            self._dependencies = ()
            self._subscribers.clear()
        for unsubscribe in unsubscribers:
            unsubscribe()

    def _dependency_changed(self, _value: object) -> None:
        with self._lock:
            if self._disposed:
                return
        _schedule_computed(cast(ComputedState[Any], self))

    def _dependencies_snapshot(self) -> tuple[_Dependency, ...]:
        with self._lock:
            return self._dependencies

    def _recompute(self) -> None:
        with self._lock:
            if self._disposed:
                return
            previous = self._value

        current = self._evaluate_and_bind()
        with self._lock:
            self._value = current
            if current == previous:
                return
            subscribers = tuple(self._subscribers)

        for subscriber in subscribers:
            subscriber(current)

    def _evaluate_and_bind(self) -> T:
        identity = id(self)
        stack = _evaluation_stack.get()
        if identity in stack:
            raise RuntimeError("Reactive dependency cycle detected while evaluating computed state.")

        collector: list[_Dependency] = []
        collector_token: Token[list[_Dependency] | None] = _dependency_collector.set(collector)
        stack_token: Token[tuple[int, ...]] = _evaluation_stack.set((*stack, identity))
        try:
            value = self._compute()
        finally:
            _evaluation_stack.reset(stack_token)
            _dependency_collector.reset(collector_token)

        dependencies = tuple(dict.fromkeys(collector))
        self._rebind_dependencies(dependencies)
        return value

    def _rebind_dependencies(self, dependencies: tuple[_Dependency, ...]) -> None:
        with self._lock:
            previous = set(self._dependencies)
            current = set(dependencies)
            removed = previous - current
            added = current - previous
            removed_unsubscribers = [
                self._dependency_unsubscribers.pop(dependency) for dependency in removed
            ]
            self._dependencies = dependencies

        for unsubscribe in removed_unsubscribers:
            unsubscribe()

        added_unsubscribers: dict[_Dependency, Callable[[], None]] = {}
        for dependency in added:
            added_unsubscribers[dependency] = dependency.subscribe(self._dependency_changed)

        if added_unsubscribers:
            with self._lock:
                if self._disposed:
                    pending = tuple(added_unsubscribers.values())
                else:
                    self._dependency_unsubscribers.update(added_unsubscribers)
                    pending = ()
            for unsubscribe in pending:
                unsubscribe()

    def __repr__(self) -> str:
        return f"ComputedState({self.value!r})"


def computed(compute: Callable[[], T]) -> ComputedState[T]:
    """Create a read-only state that tracks dependencies read by ``compute``."""

    return ComputedState(compute)
