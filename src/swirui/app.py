"""Application lifecycle and native event loop for SwirUI."""

from __future__ import annotations

import time
from types import TracebackType

from .core import AppConfig, EventEmitter, configure_logging
from .platforms import (
    NativeWindowSpec,
    NullPlatformBackend,
    PlatformBackend,
    PlatformEvent,
    PlatformEventKind,
    create_platform_backend,
)
from .window import Window


class App(EventEmitter):
    """Top-level SwirUI application object."""

    def __init__(
        self,
        name: str = "SwirUI App",
        *,
        config: AppConfig | None = None,
        platform_backend: PlatformBackend | None = None,
    ) -> None:
        super().__init__()
        self.name = name
        self.config = config or AppConfig()
        self.logger = configure_logging(debug=self.config.debug)
        self.platform_backend = platform_backend or create_platform_backend()
        self.windows: list[Window] = []
        self.running = False
        self.exit_code = 0

    def add_window(self, window: Window) -> Window:
        if window not in self.windows:
            self.windows.append(window)
            if self.running and not window.closed:
                self._attach_window(window)
                window.show()
            self.emit("window_added", window=window)
        return window

    def remove_window(self, window: Window) -> None:
        try:
            self.windows.remove(window)
        except ValueError as exc:
            raise ValueError("Window does not belong to this application.") from exc
        if not window.closed:
            window.close()
        self.emit("window_removed", window=window)

    def start(self) -> None:
        if self.running:
            return
        self.platform_backend.initialize()
        self.running = True
        self.logger.debug(
            "Starting application %s with platform backend %s",
            self.name,
            self.platform_backend.name,
        )
        self.emit("started")
        for window in self.windows:
            if not window.closed:
                self._attach_window(window)
                window.show()

    def process_events(self) -> int:
        """Process one batch of normalized native platform events."""

        if not self.running:
            return 0

        events = self.platform_backend.poll_events()
        for event in events:
            self._dispatch_platform_event(event)

        if self.platform_backend.name != NullPlatformBackend.name:
            if self.windows and all(window.closed for window in self.windows):
                self.stop(self.exit_code)
        return len(events)

    def stop(self, exit_code: int = 0) -> None:
        if not self.running:
            self.exit_code = exit_code
            return
        self.exit_code = exit_code
        for window in tuple(self.windows):
            if not window.closed:
                window.close()
        self.platform_backend.shutdown()
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
