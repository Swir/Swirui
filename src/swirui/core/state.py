"""Reactive state primitives for SwirUI."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress
from threading import RLock
from typing import Generic, TypeVar

T = TypeVar("T")
Subscriber = Callable[[T], None]


class State(Generic[T]):
    """Thread-safe observable value used by the reactive runtime."""

    __slots__ = ("_value", "_subscribers", "_lock")

    def __init__(self, value: T) -> None:
        self._value = value
        self._subscribers: list[Subscriber[T]] = []
        self._lock = RLock()

    @property
    def value(self) -> T:
        with self._lock:
            return self._value

    def get(self) -> T:
        return self.value

    def set(self, value: T) -> bool:
        with self._lock:
            if value == self._value:
                return False
            self._value = value
            subscribers = tuple(self._subscribers)

        for subscriber in subscribers:
            subscriber(value)
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

    def __repr__(self) -> str:
        return f"State({self.value!r})"
