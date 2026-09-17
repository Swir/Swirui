import pytest

from swirui import App, Window
from swirui.platforms import (
    DisplayInfo,
    NativeWindowSpec,
    NullPlatformBackend,
    PlatformEvent,
    PlatformEventKind,
    PointerButton,
)


def test_display_info_exposes_virtual_work_area_and_refresh_metadata() -> None:
    display = DisplayInfo(
        "Secondary",
        2560,
        1440,
        scale=1.5,
        refresh_rate_hz=144.0,
        x=-2560,
        y=120,
        work_x=-2560,
        work_y=120,
        work_width=2560,
        work_height=1380,
    )

    assert display.x == -2560
    assert display.y == 120
    assert display.refresh_rate_hz == 144.0
    assert display.effective_work_width == 2560
    assert display.effective_work_height == 1380

    fallback_work_area = DisplayInfo("Primary", 1920, 1080)
    assert fallback_work_area.refresh_rate_hz == 60.0
    assert fallback_work_area.effective_work_width == 1920
    assert fallback_work_area.effective_work_height == 1080

    with pytest.raises(ValueError, match="Display dimensions"):
        DisplayInfo("Invalid", 0, 1080)
    with pytest.raises(ValueError, match="Display scale"):
        DisplayInfo("Invalid", 1920, 1080, scale=0.0)
    with pytest.raises(ValueError, match="Display refresh rate"):
        DisplayInfo("Invalid", 1920, 1080, refresh_rate_hz=0.0)


def test_headless_native_window_contract() -> None:
    backend = NullPlatformBackend()
    backend.initialize()

    handle = backend.create_window(NativeWindowSpec("Demo", 800, 600))
    assert backend.window_scale(handle) == 1.0
    assert backend.window_display(handle) is None
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


def test_platform_event_preserves_keyboard_modifier_state() -> None:
    backend = NullPlatformBackend()
    backend.initialize()
    handle = backend.create_window(NativeWindowSpec("Modifiers", 320, 240))
    backend.post_event(
        PlatformEvent(
            PlatformEventKind.KEY_DOWN,
            handle,
            key_code=9,
            shift=True,
            ctrl=True,
            alt=False,
            meta=True,
        )
    )

    event = backend.poll_events()[0]

    assert event.key_code == 9
    assert event.shift is True
    assert event.ctrl is True
    assert event.alt is False
    assert event.meta is True
    backend.destroy_window(handle)
    backend.shutdown()


def test_app_dispatches_platform_events_to_window() -> None:
    backend = NullPlatformBackend()
    app = App("Events", platform_backend=backend)
    window = app.add_window(Window(width=640, height=480))
    pointer_events: list[object] = []
    scale_changes: list[tuple[float, float]] = []

    window.on("pointer_move", lambda event: pointer_events.append(event.data["event"]))
    window.on(
        "scale_changed",
        lambda event: scale_changes.append((event.data["old_scale"], event.data["scale"])),
    )
    app.start()
    assert window.native_handle is not None
    assert window.scale == 1.0
    assert window.display is None
    handle = window.native_handle

    # Platform coordinates are physical pixels. At 150% scale, the 1350x1050
    # physical resize and 49.5x66 pointer position map to 900x700 and 33x44 DIPs.
    backend.post_event(
        PlatformEvent(PlatformEventKind.RESIZE, handle, width=1350, height=1050)
    )
    backend.post_event(PlatformEvent(PlatformEventKind.DPI_CHANGED, handle, scale=1.5))
    backend.post_event(PlatformEvent(PlatformEventKind.DISPLAY_CHANGED, handle))
    backend.post_event(
        PlatformEvent(PlatformEventKind.POINTER_MOVE, handle, x=49.5, y=66.0)
    )

    processed = app.process_events()

    assert processed == 4
    assert (window.width, window.height) == (900, 700)
    assert window.pixel_size == (1350, 1050)
    assert window.scale == 1.5
    assert scale_changes == [(1.0, 1.5)]
    assert len(pointer_events) == 1
    pointer_event = pointer_events[0]
    assert pointer_event.x == pytest.approx(33.0)
    assert pointer_event.y == pytest.approx(44.0)

    backend.post_event(PlatformEvent(PlatformEventKind.CLOSE, handle))
    app.process_events()
    assert window.closed is True
    assert window.native_handle is None

    app.stop()
