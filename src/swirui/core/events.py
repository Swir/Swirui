"""Event primitives used across SwirUI."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class Event:
    """A lightweight event object with propagation control."""

    type: str
    source: object
    data: dict[str, Any] = field(default_factory=dict)
    propagation_stopped: bool = False

    def stop_propagation(self) -> None:
        self.propagation_stopped = True


EventHandler = Callable[[Event], None]


class EventEmitter:
    """Small event dispatcher shared by framework objects."""

    def __init__(self) -> None:
        self._listeners: dict[str, list[EventHandler]] = defaultdict(list)

    def on(self, event_type: str, handler: EventHandler) -> Callable[[], None]:
        if handler not in self._listeners[event_type]:
            self._listeners[event_type].append(handler)

        def unsubscribe() -> None:
            self.off(event_type, handler)

        return unsubscribe

    def off(self, event_type: str, handler: EventHandler) -> None:
        handlers = self._listeners.get(event_type)
        if not handlers:
            return
        try:
            handlers.remove(handler)
        except ValueError:
            return
        if not handlers:
            self._listeners.pop(event_type, None)

    def emit(self, event_type: str, **data: Any) -> Event:
        event = Event(type=event_type, source=self, data=data)
        for handler in tuple(self._listeners.get(event_type, ())):
            handler(event)
            if event.propagation_stopped:
                break
        return event
