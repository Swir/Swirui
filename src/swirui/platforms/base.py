"""Platform backend contracts for native operating-system integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class DisplayInfo:
    name: str
    width: int
    height: int
    scale: float = 1.0
    primary: bool = False


@runtime_checkable
class PlatformBackend(Protocol):
    """Contract implemented by Windows, Linux and macOS backends."""

    @property
    def name(self) -> str: ...

    def initialize(self) -> None: ...

    def displays(self) -> tuple[DisplayInfo, ...]: ...

    def shutdown(self) -> None: ...


class NullPlatformBackend:
    """Headless platform backend used by tests and early foundation work."""

    name = "headless"

    def __init__(self) -> None:
        self.initialized = False

    def initialize(self) -> None:
        self.initialized = True

    def displays(self) -> tuple[DisplayInfo, ...]:
        return ()

    def shutdown(self) -> None:
        self.initialized = False
