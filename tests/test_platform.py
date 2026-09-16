from swirui import App, Window
from swirui.platforms import (
    NativeWindowSpec,
    NullPlatformBackend,
    PlatformEvent,
    PlatformEventKind,
    PointerButton,
)


def test_headless_native_window_contract() -> None:
    backend = NullPlatformBackend()
    backend.initialize()

    handle = backend.create_window(NativeWindowSpec("Demo", 800, 600))
    backend.show_window(handle)
    backend.set_window_title(handle, "Updated")
    backend.resize_window(handle, 1024, 768)
    backend.hide_window(handle)

    backend.post_event(
        PlatformEvent(
            PlatformEventKind.POINTER_DOWN,
            handle,
            x=12.0,
            y=24.0,
            button=PointerButton.LEFT,
        )
    )
    events = backend.poll_events()

    assert len(events) == 1
    assert events[0].window == handle
    assert events[0].button is PointerButton.LEFT

    backend.destroy_window(handle)
    backend.shutdown()
    assert backend.initialized is False


def test_app_dispatches_platform_events_to_window() -> None:
    backend = NullPlatformBackend()
    app = App("Events", platform_backend=backend)
    window = app.add_window(Window(width=640, height=480))
    pointer_events: list[object] = []

    window.on("pointer_move", lambda event: pointer_events.append(event.data["event"]))
    app.start()
    assert window.native_handle is not None
    handle = window.native_handle

    backend.post_event(
        PlatformEvent(PlatformEventKind.RESIZE, handle, width=900, height=700)
    )
    backend.post_event(
        PlatformEvent(PlatformEventKind.POINTER_MOVE, handle, x=33.0, y=44.0)
    )

    processed = app.process_events()

    assert processed == 2
    assert (window.width, window.height) == (900, 700)
    assert len(pointer_events) == 1

    backend.post_event(PlatformEvent(PlatformEventKind.CLOSE, handle))
    app.process_events()
    assert window.closed is True
    assert window.native_handle is None

    app.stop()
