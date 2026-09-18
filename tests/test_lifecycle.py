from swirui import App, Window, mount
from swirui.core import Component
from swirui.platforms import NullPlatformBackend
from swirui.rendering import NullRenderer


class RecordingComponent(Component):
    def __init__(self, name: str, log: list[str]) -> None:
        super().__init__(name)
        self.log = log

    def on_mount(self, window: Window) -> None:
        self.log.append(f"mount:{self.name}:{window.title}")

    def on_update(self, *, reason: str, source: Component) -> None:
        self.log.append(f"update:{self.name}:{reason}:{source.name}")

    def on_unmount(self, window: Window) -> None:
        self.log.append(f"unmount:{self.name}:{window.title}")


def test_window_root_resize_and_close() -> None:
    window = Window(title="Demo", width=800, height=600, min_width=400, min_height=300)
    root = Component("root")

    window.set_root(root)
    window.resize(100, 100)
    window.show()

    assert window.root is root
    assert (window.width, window.height) == (400, 300)
    assert window.visible is True

    window.close()
    assert window.closed is True
    assert window.visible is False


def test_app_lifecycle() -> None:
    app = App("Test", platform_backend=NullPlatformBackend())
    window = app.add_window(Window())

    exit_code = app.run()

    assert exit_code == 0
    assert app.running is True
    assert window.visible is True
    assert window.native_handle is not None

    app.stop(7)
    assert app.running is False
    assert app.exit_code == 7
    assert window.closed is True
    assert window.native_handle is None


def test_headless_backends() -> None:
    renderer = NullRenderer()
    platform = NullPlatformBackend()
    window = Window()

    renderer.initialize()
    platform.initialize()
    renderer.render(window, None)

    assert renderer.frames_rendered == 1
    assert platform.displays() == ()

    renderer.shutdown()
    platform.shutdown()
    assert renderer.initialized is False
    assert platform.initialized is False


def test_component_lifecycle_mount_update_and_unmount_order() -> None:
    log: list[str] = []
    window = Window(title="Lifecycle")
    root = RecordingComponent("root", log)
    child = RecordingComponent("child", log)
    root.add(child)

    runtime = mount(window, root)

    assert root.mounted is True
    assert child.mounted is True
    assert root.mounted_window is window
    assert child.mounted_window is window
    assert log == ["mount:root:Lifecycle", "mount:child:Lifecycle"]

    log.clear()
    child.invalidate(reason="reactive_value")
    assert log == [
        "update:child:reactive_value:child",
        "update:root:reactive_value:child",
    ]

    log.clear()
    runtime.unmount()
    assert log == ["unmount:child:Lifecycle", "unmount:root:Lifecycle"]
    assert root.mounted is False
    assert child.mounted is False
    assert root.mounted_window is None
    assert child.mounted_window is None


def test_dynamic_children_inherit_mounted_lifecycle() -> None:
    log: list[str] = []
    window = Window(title="Dynamic")
    root = RecordingComponent("root", log)
    runtime = mount(window, root)
    log.clear()

    child = RecordingComponent("late", log)
    root.add(child)

    assert child.mounted_window is window
    assert log[0] == "mount:late:Dynamic"
    assert "update:root:child_added:late" in log

    log.clear()
    root.remove(child)
    assert child.mounted is False
    assert log[0] == "unmount:late:Dynamic"
    assert "update:root:child_removed:late" in log

    runtime.unmount()


def test_window_close_unmounts_runtime_component_tree() -> None:
    log: list[str] = []
    window = Window(title="Closing")
    root = RecordingComponent("root", log)
    child = RecordingComponent("child", log)
    root.add(child)
    runtime = mount(window, root)
    assert runtime.mounted is True
    log.clear()

    window.close()

    assert runtime.mounted is False
    assert root.mounted is False
    assert child.mounted is False
    assert log == ["unmount:child:Closing", "unmount:root:Closing"]


def test_component_tree_cannot_be_mounted_by_two_runtimes() -> None:
    root = Component("root")
    first = mount(Window(title="First"), root)

    try:
        try:
            mount(Window(title="Second"), root)
        except ValueError as exc:
            assert "already mounted" in str(exc)
        else:
            raise AssertionError("mounting one retained tree twice must fail")
    finally:
        first.unmount()
