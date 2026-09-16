"""Application lifecycle for SwirUI."""

from __future__ import annotations

from types import TracebackType

from .core import AppConfig, EventEmitter, configure_logging
from .window import Window


class App(EventEmitter):
    """Top-level SwirUI application object.

    The 0.1 foundation runtime intentionally has no native event loop yet.
    ``run()`` validates and starts the framework lifecycle so API contracts can
    be tested before the native/GPU backend is introduced.
    """

    def __init__(self, name: str = "SwirUI App", *, config: AppConfig | None = None) -> None:
        super().__init__()
        self.name = name
        self.config = config or AppConfig()
        self.logger = configure_logging(debug=self.config.debug)
        self.windows: list[Window] = []
        self.running = False
        self.exit_code = 0

    def add_window(self, window: Window) -> Window:
        if window not in self.windows:
            self.windows.append(window)
            self.emit("window_added", window=window)
        return window

    def remove_window(self, window: Window) -> None:
        try:
            self.windows.remove(window)
        except ValueError as exc:
            raise ValueError("Window does not belong to this application.") from exc
        self.emit("window_removed", window=window)

    def start(self) -> None:
        if self.running:
            return
        self.running = True
        self.logger.debug("Starting application %s", self.name)
        self.emit("started")
        for window in self.windows:
            if not window.closed:
                window.show()

    def stop(self, exit_code: int = 0) -> None:
        if not self.running:
            self.exit_code = exit_code
            return
        self.exit_code = exit_code
        for window in tuple(self.windows):
            if not window.closed:
                window.close()
        self.running = False
        self.emit("stopped", exit_code=exit_code)
        self.logger.debug("Stopped application %s with code %d", self.name, exit_code)

    def run(self) -> int:
        """Start the foundation lifecycle and return its exit code.

        A blocking native event loop is scheduled for the native-window
        milestone. Keeping this method now stabilizes the public API early.
        """
        self.start()
        return self.exit_code

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
