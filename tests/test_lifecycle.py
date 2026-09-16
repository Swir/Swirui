from swirui import App, Window
from swirui.core import Component
from swirui.platforms import NullPlatformBackend
from swirui.rendering import NullRenderer


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
    app = App("Test")
    window = app.add_window(Window())

    exit_code = app.run()

    assert exit_code == 0
    assert app.running is True
    assert window.visible is True

    app.stop(7)
    assert app.running is False
    assert app.exit_code == 7
    assert window.closed is True


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
