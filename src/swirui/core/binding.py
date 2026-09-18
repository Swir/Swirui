"""Reactive property descriptors and data-binding helpers for SwirUI."""

from __future__ import annotations

from collections.abc import Callable
from threading import RLock
from typing import Generic, Literal, TypeVar, overload
from weakref import WeakKeyDictionary

from .state import ComputedState, State

T = TypeVar("T")


class Binding:
    """Disposable subscription group created by SwirUI binding helpers."""

    __slots__ = ("_active", "_lock", "_unsubscribers")

    def __init__(self, *unsubscribers: Callable[[], None]) -> None:
        self._active = True
        self._lock = RLock()
        self._unsubscribers = unsubscribers

    @property
    def active(self) -> bool:
        with self._lock:
            return self._active

    def dispose(self) -> None:
        """Detach every subscription owned by this binding."""

        with self._lock:
            if not self._active:
                return
            self._active = False
            unsubscribers = self._unsubscribers
            self._unsubscribers = ()
        for unsubscribe in unsubscribers:
            unsubscribe()

    def __enter__(self) -> Binding:
        return self

    def __exit__(self, _exc_type: object, _exc: object, _traceback: object) -> None:
        self.dispose()


class ReactiveProperty(Generic[T]):
    """Descriptor backed by one independent :class:`State` per object instance."""

    __slots__ = ("_default", "_lock", "_name", "_states")

    def __init__(self, default: T) -> None:
        self._default = default
        self._lock = RLock()
        self._name = "<reactive property>"
        self._states: WeakKeyDictionary[object, State[T]] = WeakKeyDictionary()

    def __set_name__(self, _owner: type[object], name: str) -> None:
        self._name = name

    @overload
    def __get__(self, instance: None, owner: type[object] | None = None) -> ReactiveProperty[T]: ...

    @overload
    def __get__(self, instance: object, owner: type[object] | None = None) -> T: ...

    def __get__(
        self,
        instance: object | None,
        owner: type[object] | None = None,
    ) -> T | ReactiveProperty[T]:
        del owner
        if instance is None:
            return self
        return self.state(instance).value

    def __set__(self, instance: object, value: T) -> None:
        self.state(instance).set(value)

    def state(self, instance: object) -> State[T]:
        """Return the observable state backing this property on ``instance``."""

        with self._lock:
            state = self._states.get(instance)
            if state is None:
                try:
                    state = State(self._default)
                    self._states[instance] = state
                except TypeError as exc:
                    raise TypeError(
                        f"{self._name} requires an instance that supports weak references."
                    ) from exc
            return state

    def subscribe(
        self,
        instance: object,
        subscriber: Callable[[T], None],
        *,
        immediate: bool = False,
    ) -> Callable[[], None]:
        """Subscribe to this property's value for one object instance."""

        return self.state(instance).subscribe(subscriber, immediate=immediate)


ReadableState = State[T] | ComputedState[T]


def bind(
    source: ReadableState[T],
    target: State[T],
    *,
    immediate: bool = True,
) -> Binding:
    """Bind a readable state to a writable state in one direction."""

    def update(value: T) -> None:
        target.set(value)

    unsubscribe = source.subscribe(update, immediate=immediate)
    return Binding(unsubscribe)


def bind_bidirectional(
    left: State[T],
    right: State[T],
    *,
    initial: Literal["left", "right", "none"] = "left",
) -> Binding:
    """Keep two writable states synchronized until the returned binding is disposed."""

    if initial == "left":
        right.set(left.value)
    elif initial == "right":
        left.set(right.value)

    def update_right(value: T) -> None:
        right.set(value)

    def update_left(value: T) -> None:
        left.set(value)

    return Binding(
        left.subscribe(update_right),
        right.subscribe(update_left),
    )
