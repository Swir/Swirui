"""Retained component lifecycle hooks in SwirUI."""

from __future__ import annotations

from swirui import Component, Window, mount


class TrackedComponent(Component):
    def on_mount(self, window: Window) -> None:
        print(f"mounted {self.name!r} in {window.title!r}")

    def on_update(self, *, reason: str, source: Component) -> None:
        print(f"updated {self.name!r}: reason={reason!r}, source={source.name!r}")

    def on_unmount(self, window: Window) -> None:
        print(f"unmounted {self.name!r} from {window.title!r}")


window = Window(title="Lifecycle demo", width=720, height=420)
root = TrackedComponent("root")
child = TrackedComponent("child")
root.add(child)

runtime = mount(window, root)
child.invalidate(reason="demo_state_changed")
runtime.unmount()
