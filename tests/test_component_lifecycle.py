from __future__ import annotations

from swirui import Component, WidgetRuntime, Window


class LifecycleComponent(Component):
    def __init__(self, name: str, calls: list[tuple[str, str]]) -> None:
        super().__init__(name)
        self.calls = calls

    def on_mount(self, runtime: object) -> None:
        assert self.mounted is True
        assert self.runtime is runtime
        self.calls.append(("mount", self.name))

    def on_unmount(self, runtime: object) -> None:
        assert self.mounted is True
        assert self.runtime is runtime
        self.calls.append(("unmount", self.name))


def test_lifecycle_mounts_parent_first_and_unmounts_child_first() -> None:
    calls: list[tuple[str, str]] = []
    root = LifecycleComponent("root", calls)
    child = LifecycleComponent("child", calls)
    grandchild = LifecycleComponent("grandchild", calls)
    root.add(child)
    child.add(grandchild)

    runtime = WidgetRuntime(Window()).mount(root)

    assert calls == [
        ("mount", "root"),
        ("mount", "child"),
        ("mount", "grandchild"),
    ]
    assert root.runtime is runtime
    assert child.runtime is runtime
    assert grandchild.runtime is runtime

    runtime.unmount()

    assert calls[-3:] == [
        ("unmount", "grandchild"),
        ("unmount", "child"),
        ("unmount", "root"),
    ]
    assert root.mounted is False
    assert child.mounted is False
    assert grandchild.mounted is False


def test_rebuild_does_not_repeat_lifecycle_hooks() -> None:
    calls: list[tuple[str, str]] = []
    root = LifecycleComponent("root", calls)
    runtime = WidgetRuntime(Window()).mount(root)

    runtime.rebuild()
    runtime.rebuild()

    assert calls == [("mount", "root")]


def test_tree_mutations_mount_and_unmount_only_changed_subtree() -> None:
    calls: list[tuple[str, str]] = []
    root = LifecycleComponent("root", calls)
    stable = LifecycleComponent("stable", calls)
    root.add(stable)
    runtime = WidgetRuntime(Window()).mount(root)
    calls.clear()

    dynamic = LifecycleComponent("dynamic", calls)
    leaf = LifecycleComponent("leaf", calls)
    dynamic.add(leaf)
    root.add(dynamic)

    assert calls == [("mount", "dynamic"), ("mount", "leaf")]
    assert stable.mounted is True
    calls.clear()

    root.remove(dynamic)

    assert calls == [("unmount", "leaf"), ("unmount", "dynamic")]
    assert dynamic.mounted is False
    assert leaf.mounted is False
    assert root.mounted is True
    assert stable.mounted is True
    runtime.unmount()


def test_external_window_root_replacement_detaches_lifecycle() -> None:
    calls: list[tuple[str, str]] = []
    window = Window()
    root = LifecycleComponent("root", calls)
    child = LifecycleComponent("child", calls)
    root.add(child)
    runtime = WidgetRuntime(window).mount(root)
    calls.clear()

    replacement = Component("replacement")
    window.set_root(replacement)

    assert calls == [("unmount", "child"), ("unmount", "root")]
    assert runtime.mounted is False
    assert window.scene is None
    assert replacement.mounted is False


def test_mount_and_unmount_events_are_observable() -> None:
    root = Component("root")
    events: list[tuple[str, object]] = []
    root.on("mounted", lambda event: events.append((event.kind, event.data["runtime"])))
    root.on("unmounted", lambda event: events.append((event.kind, event.data["runtime"])))
    runtime = WidgetRuntime(Window()).mount(root)

    runtime.unmount()

    assert events == [("mounted", runtime), ("unmounted", runtime)]
