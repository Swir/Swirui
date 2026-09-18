"""Async and persistent reactive state demo for SwirUI."""

from __future__ import annotations

import asyncio
from pathlib import Path

from swirui import AsyncState, AsyncStatus, PersistentState


async def main() -> None:
    preferences = PersistentState(Path(".swirui-demo-settings.json"), {"refreshes": 0})
    remote_value = AsyncState[str]("cached")

    remote_value.subscribe(
        lambda snapshot: print(
            "async:",
            snapshot.status.value,
            snapshot.value,
            type(snapshot.error).__name__ if snapshot.error else "ok",
        ),
        immediate=True,
    )

    async def load_message() -> str:
        await asyncio.sleep(0.05)
        return "SwirUI reactive runtime is ready"

    await remote_value.run(load_message)
    assert remote_value.status is AsyncStatus.READY

    current = preferences.value
    preferences.set({"refreshes": int(current["refreshes"]) + 1})
    print("persistent:", preferences.path, preferences.value)


if __name__ == "__main__":
    asyncio.run(main())
