"""Durable reactive state primitives for SwirUI."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path
from threading import RLock
from typing import Generic, TypeVar, cast
from uuid import uuid4

from .state import State

T = TypeVar("T")

_SCHEMA_VERSION = 1


def _identity(value: object) -> object:
    return value


class PersistentState(State[T], Generic[T]):
    """A :class:`State` whose committed values are stored atomically as JSON.

    Missing files start from ``default`` without creating storage eagerly. A successful
    ``set()`` writes the new value first and only then publishes the reactive change, so
    serialization or filesystem failures never leave in-memory state ahead of disk.
    Custom ``encode``/``decode`` callables can adapt domain objects while keeping the
    on-disk envelope versioned and deterministic.
    """

    __slots__ = (
        "_decode",
        "_default",
        "_encode",
        "_indent",
        "_path",
        "_persistence_lock",
    )

    def __init__(
        self,
        path: str | Path,
        default: T,
        *,
        encode: Callable[[T], object] | None = None,
        decode: Callable[[object], T] | None = None,
        indent: int | None = 2,
    ) -> None:
        self._path = Path(path)
        self._default = default
        self._encode = encode or cast(Callable[[T], object], _identity)
        self._decode = decode or cast(Callable[[object], T], _identity)
        self._indent = indent
        self._persistence_lock = RLock()
        super().__init__(self._read_value(default))

    @property
    def path(self) -> Path:
        return self._path

    def set(self, value: T) -> bool:
        """Persist and publish ``value`` as one serialized state transition."""

        with self._persistence_lock:
            if value == self.value:
                return False
            self._write_value(value)
            return super().set(value)

    def reload(self) -> bool:
        """Reload the persisted value, or ``default`` when storage was removed."""

        with self._persistence_lock:
            value = self._read_value(self._default)
            return super().set(value)

    def persist(self) -> None:
        """Rewrite the current value using the canonical on-disk envelope."""

        with self._persistence_lock:
            self._write_value(self.value)

    def reset(self) -> bool:
        """Restore and persist the constructor's default value."""

        return self.set(self._default)

    def _read_value(self, missing: T) -> T:
        if not self._path.exists():
            return missing
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Could not read persistent state from {self._path}.") from exc

        if not isinstance(raw, dict):
            raise ValueError(f"Persistent state at {self._path} is not a JSON object.")
        if raw.get("schema") != _SCHEMA_VERSION or "value" not in raw:
            raise ValueError(
                f"Persistent state at {self._path} has an unsupported or invalid schema."
            )
        return self._decode(raw["value"])

    def _write_value(self, value: T) -> None:
        payload = {
            "schema": _SCHEMA_VERSION,
            "value": self._encode(value),
        }
        serialized = json.dumps(
            payload,
            ensure_ascii=False,
            indent=self._indent,
            sort_keys=True,
        )
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._path.with_name(f".{self._path.name}.{uuid4().hex}.tmp")
        try:
            with temporary.open("x", encoding="utf-8", newline="\n") as handle:
                handle.write(serialized)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self._path)
        finally:
            with suppress(FileNotFoundError):
                temporary.unlink()

    def __repr__(self) -> str:
        return f"PersistentState(path={str(self._path)!r}, value={self.value!r})"
