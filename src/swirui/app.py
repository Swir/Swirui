"""Application lifecycle, native event loop and render scheduling for SwirUI."""

from __future__ import annotations

import time
from collections.abc import Callable
from types import TracebackType

from .core import AppConfig, Event, EventEmitter, configure_logging
from .platforms import (
    NativeWindowSpec,
    NullPlatformBackend,
    PlatformBackend,
    PlatformEvent,
    PlatformEventKind,
    create_platform_backend,
)
from .rendering import FrameScheduler, NullRenderer, Renderer
from .window import Window


class App(EventEmitter):
    """Top-level SwirUI application object."""

    def __init__(
        self,
        name: str = "SwirUI App",
        *,
        config: AppConfig | None = None,
        platform_backend: PlatformBackend | None = None,
        renderer: Renderer | None = None,
    ) -> None:
        super().__init__()
        self.name = name
        self.config = config or AppConfig()
        self.logger = configure_logging(debug=self.config.debug)
        self.platform_backend = platform_backend or create_platform_backend()
        self.renderer = renderer or NullRenderer()
        self.windows: list[Window] = []
        self.running = False
        self.exit_code = 0
        self._frame_schedulers: dict[Window, FrameScheduler] = {}
        self._window_unsubscribers: dict[Window, list[Callable[[], None]]] = {}

    def add_window(self, window: Window) -> Window:
        if window not in self.windows:
            self.windows.append(window)
            self._observe_window(window)
            if self.running and not window.closed:
                self._attach_window(window)
                window.show()
                self.invalidate(window)
            self.emit("window_added", window=window)
        return window

    def remove_window(self, window: Window) -> None:
        try:
            self.windows.remove(window)
        except ValueError as exc:
            raise ValueError("Window does not belong to this application.") from exc
        if not window.closed:
            window.close()
        self._unobserve_window(window)
        self._frame_schedulers.pop(window, None)
        self.emit("window_removed", window=window)

    def start(self) -> None:
        if self.running:
            return
        self.platform_backend.initialize()
        self.renderer.initialize()
        self.running = True
        self.logger.debug(
            "Starting application %s with platform=%s renderer=%s",
            self.name,
            self.platform_backend.name,
            self.renderer.name,
        )
        self.emit("started")
        for window in self.windows:
            if not window.closed:
                self._attach_window(window)
                window.show()
                self.invalidate(window)
        self.render_pending()

    def process_events(self) -> int:
        """Process one native event batch and render any due invalidated frames."""

        if not self.running:
            return 0

        events = self.platform_backend.poll_events()
        for event in events:
            self._dispatch_platform_event(event)

        self.render_pending()
        if (
            self.platform_backend.name != NullPlatformBackend.name
            and self.windows
            and all(window.closed for window in self.windows)
        ):
            self.stop(self.exit_code)
        return len(events)

    def invalidate(self, window: Window | None = None) -> None:
        """Request a future frame for one window or every attached window."""

        if window is not None:
            scheduler = self._frame_schedulers.get(window)
            if scheduler is not None:
                scheduler.invalidate()
            return
        for scheduler in self._frame_schedulers.values():
            scheduler.invalidate()

    def render_pending(self, now: float | None = None) -> int:
        """Render invalidated windows whose frame interval has elapsed."""

        if not self.running:
            return 0
        frame_time = time.monotonic() if now is None else now
        frames = 0
        for window, scheduler in tuple(self._frame_schedulers.items()):
            if window.closed or not window.visible:
                continue
            if scheduler.consume(frame_time):
                self.renderer.render(window, window.root)
                frames += 1
                self.emit(
                    "frame_rendered",
                    window=window,
                    frame_number=scheduler.stats.frame_number,
                    frame_time=frame_time,
                )
        return frames

    def stop(self, exit_code: int = 0) -> None:
        if not self.running:
            self.exit_code = exit_code
            return
        self.exit_code = exit_code
        for window in tuple(self.windows):
            if not window.closed:
                window.close()
        self.renderer.shutdown()
        self.platform_backend.shutdown()
        self._frame_schedulers.clear()
        self.running = False
        self.emit("stopped", exit_code=exit_code)
        self.logger.debug("Stopped application %s with code %d", self.name, exit_code)

    def run(self) -> int:
        """Start the application and run the native event loop when available.

        The headless backend remains non-blocking for deterministic tests and CI.
        Native backends keep pumping events until all application windows close
        or :meth:`stop` is called.
        """

        self.start()
        if self.platform_backend.name == NullPlatformBackend.name:
            return self.exit_code

        while self.running:
            processed = self.process_events()
            if self.running and processed == 0:
                time.sleep(0.004)
        return self.exit_code

    def _attach_window(self, window: Window) -> None:
        if window.native_handle is not None:
            return
        handle = self.platform_backend.create_window(
            NativeWindowSpec(
                title=window.title,
                width=window.width,
                height=window.height,
                min_width=window.min_width,
                min_height=window.min_height,
            )
        )
        window._bind_native(self.platform_backend, handle)
        self.renderer.create_surface(window)
        self._frame_schedulers[window] = FrameScheduler(self.config.target_fps)

    def _dispatch_platform_event(self, event: PlatformEvent) -> None:
        window = next(
            (candidate for candidate in self.windows if candidate.native_handle == event.window),
            None,
        )
        if window is None:
            return

        if event.kind is PlatformEventKind.CLOSE:
            self.platform_backend.destroy_window(event.window)
        window._apply_platform_event(event)
        self.emit("platform_event", event=event, window=window)

    def _observe_window(self, window: Window) -> None:
        if window in self._window_unsubscribers:
            return

        def invalidate_window(_event: Event) -> None:
            self.invalidate(window)

        def resize_surface(_event: Event) -> None:
            if self.running and window.native_handle is not None:
                self.renderer.resize_surface(window, window.width, window.height)
            self.invalidate(window)

        def close_surface(_event: Event) -> None:
            if window.native_handle is not None:
                self.renderer.destroy_surface(window)
            self._frame_schedulers.pop(window, None)

        self._window_unsubscribers[window] = [
            window.on("root_changed", invalidate_window),
            window.on("shown", invalidate_window),
            window.on("resized", resize_surface),
            window.on("closed", close_surface),
        ]

    def _unobserve_window(self, window: Window) -> None:
        for unsubscribe in self._window_unsubscribers.pop(window, ()):
            unsubscribe()

    def __enter__(self) -> App:
        self.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, traceback
        self.stop(1 if exc is not None else 0)
