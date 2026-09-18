"""Observable collection primitives for SwirUI reactive state."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Mapping
from threading import RLock
from typing import Generic, TypeVar, overload

from .state import State

T = TypeVar("T")
K = TypeVar("K")
V = TypeVar("V")


class ObservableList(Generic[T]):
    """Thread-safe list-like collection backed by immutable reactive snapshots."""

    __slots__ = ("_lock", "_state")

    def __init__(self, values: Iterable[T] = ()) -> None:
        self._lock = RLock()
        self._state = State(tuple(values))

    @property
    def values(self) -> tuple[T, ...]:
        """Return the current immutable snapshot and register reactive reads."""

        return self._state.value

    def snapshot(self) -> tuple[T, ...]:
        return self.values

    def subscribe(
        self,
        subscriber: Callable[[tuple[T, ...]], None],
        *,
        immediate: bool = False,
    ) -> Callable[[], None]:
        return self._state.subscribe(subscriber, immediate=immediate)

    def append(self, value: T) -> None:
        with self._lock:
            self._state.set((*self._state.value, value))

    def extend(self, values: Iterable[T]) -> None:
        additions = tuple(values)
        if not additions:
            return
        with self._lock:
            self._state.set((*self._state.value, *additions))

    def insert(self, index: int, value: T) -> None:
        with self._lock:
            current = list(self._state.value)
            current.insert(index, value)
            self._state.set(tuple(current))

    def set(self, index: int, value: T) -> None:
        with self._lock:
            current = list(self._state.value)
            current[index] = value
            self._state.set(tuple(current))

    def remove(self, value: T) -> None:
        with self._lock:
            current = list(self._state.value)
            current.remove(value)
            self._state.set(tuple(current))

    def pop(self, index: int = -1) -> T:
        with self._lock:
            current = list(self._state.value)
            value = current.pop(index)
            self._state.set(tuple(current))
            return value

    def clear(self) -> None:
        with self._lock:
            self._state.set(())

    def __len__(self) -> int:
        return len(self._state.value)

    def __iter__(self) -> Iterator[T]:
        return iter(self._state.value)

    @overload
    def __getitem__(self, index: int) -> T: ...

    @overload
    def __getitem__(self, index: slice) -> tuple[T, ...]: ...

    def __getitem__(self, index: int | slice) -> T | tuple[T, ...]:
        return self._state.value[index]

    def __repr__(self) -> str:
        return f"ObservableList({list(self._state.value)!r})"


class ObservableDict(Generic[K, V]):
    """Thread-safe mapping-like collection with reactive snapshot reads."""

    __slots__ = ("_lock", "_state")

    def __init__(self, values: Mapping[K, V] | None = None) -> None:
        self._lock = RLock()
        self._state: State[dict[K, V]] = State(dict(values or {}))

    def snapshot(self) -> dict[K, V]:
        """Return a defensive copy while registering this mapping as a dependency."""

        return dict(self._state.value)

    def subscribe(
        self,
        subscriber: Callable[[dict[K, V]], None],
        *,
        immediate: bool = False,
    ) -> Callable[[], None]:
        def publish(value: dict[K, V]) -> None:
            subscriber(dict(value))

        return self._state.subscribe(publish, immediate=immediate)

    def set(self, key: K, value: V) -> None:
        with self._lock:
            current = dict(self._state.value)
            current[key] = value
            self._state.set(current)

    def update(self, values: Mapping[K, V]) -> None:
        with self._lock:
            current = dict(self._state.value)
            current.update(values)
            self._state.set(current)

    def remove(self, key: K) -> None:
        with self._lock:
            current = dict(self._state.value)
            del current[key]
            self._state.set(current)

    def pop(self, key: K) -> V:
        with self._lock:
            current = dict(self._state.value)
            value = current.pop(key)
            self._state.set(current)
            return value

    def clear(self) -> None:
        with self._lock:
            self._state.set({})

    def __len__(self) -> int:
        return len(self._state.value)

    def __iter__(self) -> Iterator[K]:
        return iter(tuple(self._state.value))

    def __getitem__(self, key: K) -> V:
        return self._state.value[key]

    def __contains__(self, key: object) -> bool:
        return key in self._state.value

    def __repr__(self) -> str:
        return f"ObservableDict({self._state.value!r})"
