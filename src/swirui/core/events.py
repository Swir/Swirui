"""Event primitives used across SwirUI."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class EventPhase(StrEnum):
    """Routing phase for an event moving through a component tree."""

    DIRECT = "direct"
    CAPTURE = "capture"
    TARGET = "target"
    BUBBLE = "bubble"


@dataclass(slots=True)
class Event:
    """A lightweight event object with routing and default-action control."""

    type: str
    source: object
    data: dict[str, Any] = field(default_factory=dict)
    current_target: object | None = None
    phase: EventPhase = EventPhase.DIRECT
    propagation_stopped: bool = False
    default_prevented: bool = False

    def stop_propagation(self) -> None:
        """Stop routing the event to later components in the current path."""

        self.propagation_stopped = True

    def prevent_default(self) -> None:
        """Cancel the framework default action without stopping event routing."""

        self.default_prevented = True


EventHandler = Callable[[Event], None]


class EventEmitter:
    """Small event dispatcher shared by framework objects."""

    def __init__(self) -> None:
        self._listeners: dict[str, list[EventHandler]] = defaultdict(list)
        self._capture_listeners: dict[str, list[EventHandler]] = defaultdict(list)

    def on(
        self,
        event_type: str,
        handler: EventHandler,
        *,
        capture: bool = False,
    ) -> Callable[[], None]:
        listeners = self._capture_listeners if capture else self._listeners
        if handler not in listeners[event_type]:
            listeners[event_type].append(handler)

        def unsubscribe() -> None:
            self.off(event_type, handler, capture=capture)

        return unsubscribe

    def off(self, event_type: str, handler: EventHandler, *, capture: bool = False) -> None:
        listeners = self._capture_listeners if capture else self._listeners
        handlers = listeners.get(event_type)
        if not handlers:
            return
        try:
            handlers.remove(handler)
        except ValueError:
            return
        if not handlers:
            listeners.pop(event_type, None)

    def dispatch(self, event: Event, *, capture: bool = False) -> Event:
        """Dispatch an existing event while preserving its original source."""

        event.current_target = self
        listeners = self._capture_listeners if capture else self._listeners
        for handler in tuple(listeners.get(event.type, ())):
            handler(event)
            if event.propagation_stopped:
                break
        return event

    def emit(self, event_type: str, **data: Any) -> Event:
        event = Event(
            type=event_type,
            source=self,
            data=data,
            current_target=self,
            phase=EventPhase.DIRECT,
        )
        return self.dispatch(event)
