"""Per-window appearance policy with native system preference synchronization."""

from __future__ import annotations

from enum import StrEnum

from .animation import AnimationController, AnimationStatus
from .core import Component, Event, EventEmitter, state_transaction
from .platforms import ColorScheme
from .theme import FUTURE_DARK, FUTURE_LIGHT, Theme
from .theme_transition import ThemeTransition
from .window import Window


class ThemeMode(StrEnum):
    SYSTEM = "system"
    LIGHT = "light"
    DARK = "dark"


class ThemeController(EventEmitter):
    """Own a window root's theme while preserving child scopes and overrides.

    One controller may be attached to a window. The controller listens for
    native appearance notifications, initial binding and root replacement;
    it does not poll or start a thread. Native Windows detection is supported.
    Unsupported/unbound backends use the explicit fallback, dark by default.

    ``close()`` detaches listeners and retains the last applied theme. Closing
    the window closes its controller automatically. Use from the UI thread.
    """

    def __init__(
        self, window: Window, *, mode: ThemeMode | str = ThemeMode.SYSTEM,
        light: Theme = FUTURE_LIGHT, dark: Theme = FUTURE_DARK,
        fallback: ColorScheme | str = ColorScheme.DARK,
        animations: AnimationController | None = None,
    ) -> None:
        super().__init__()
        self._mode = ThemeMode(mode)
        self._fallback = ColorScheme(fallback)
        self._validate_themes(light, dark)
        if animations is not None and animations.window is not window:
            raise ValueError("The animation controller must belong to this window.")
        if window.closed:
            raise ValueError("Cannot attach a theme controller to a closed window.")
        if window._theme_controller is not None:
            raise ValueError("This window already has a theme controller.")
        self._window = window
        self._animations = animations
        self._transition: ThemeTransition | None = None
        self._transition_root: Component | None = None
        self._transition_target: Theme | None = None
        self._light, self._dark = light, dark
        self._system_scheme: ColorScheme | None = None
        self._closed = False
        self._refreshing = False
        self._refresh_again = False
        self._last_state: tuple[ThemeMode, ColorScheme | None, ColorScheme, Theme] | None = None
        window._theme_controller = self
        self._subscriptions = [
            window.on(name, self._on_refresh)
            for name in ("native_bound", "native_unbound", "root_changed",
                         "system_appearance_changed")
        ]
        self._subscriptions.append(window.on("closed", self._on_closed))
        self._subscriptions.append(window.on("hidden", self._on_hidden))
        try:
            self.refresh()
        except Exception:
            self.close()
            raise

    @staticmethod
    def _validate_themes(light: Theme, dark: Theme) -> None:
        if not isinstance(light, Theme) or not isinstance(dark, Theme):
            raise TypeError("light and dark must be Theme instances.")

    @property
    def mode(self) -> ThemeMode:
        return self._mode

    @mode.setter
    def mode(self, value: ThemeMode | str) -> None:
        self._require_open()
        mode = ThemeMode(value)
        if mode != self._mode:
            self._mode = mode
            self.refresh()

    @property
    def fallback(self) -> ColorScheme:
        return self._fallback

    @fallback.setter
    def fallback(self, value: ColorScheme | str) -> None:
        self._require_open()
        fallback = ColorScheme(value)
        if fallback != self._fallback:
            self._fallback = fallback
            self.refresh()

    @property
    def system_scheme(self) -> ColorScheme | None:
        """Last native preference; None means unavailable, not dark."""
        return self._system_scheme

    @property
    def effective_scheme(self) -> ColorScheme:
        if self._mode is ThemeMode.SYSTEM:
            return self._system_scheme or self._fallback
        return ColorScheme(self._mode.value)

    @property
    def effective_theme(self) -> Theme:
        return self._light if self.effective_scheme is ColorScheme.LIGHT else self._dark

    @property
    def closed(self) -> bool:
        return self._closed

    @property
    def transitioning(self) -> bool:
        return self._transition is not None and self._transition.status is AnimationStatus.RUNNING

    def set_themes(self, *, light: Theme, dark: Theme) -> None:
        """Replace the pair (including package variants) and apply current policy."""
        self._require_open()
        self._validate_themes(light, dark)
        self._light, self._dark = light, dark
        self.refresh()

    def refresh(self) -> None:
        """Read current native preference and apply policy to the current root."""
        self._require_open()
        if self._refreshing:
            self._refresh_again = True
            return
        self._refreshing = True
        try:
            with state_transaction():
                while not self.closed:
                    self._refresh_again = False
                    self._system_scheme = self._window.get_system_color_scheme()
                    theme = self.effective_theme
                    root = self._window.root
                    self._apply_theme(root, theme)
                    if self.closed:
                        break
                    # A root observer may choose another mode or variant pair.
                    # Resolve that policy before announcing a stale appearance.
                    if self._refresh_again:
                        continue
                    state = (self.mode, self.system_scheme, self.effective_scheme, theme)
                    if state != self._last_state:
                        previous = self._last_state
                        self._last_state = state
                        self.emit("changed", mode=self.mode, system_scheme=self.system_scheme,
                                  effective_scheme=self.effective_scheme, theme=theme,
                                  previous=previous)
                    if not self._refresh_again:
                        break
        finally:
            self._refreshing = False

    def close(self) -> None:
        """Detach idempotently, retaining the current appearance."""
        if self._closed:
            return
        self._closed = True
        self._cancel_transition()
        self._transition_root = None
        self._transition_target = None
        for unsubscribe in self._subscriptions:
            unsubscribe()
        self._subscriptions.clear()
        if self._window._theme_controller is self:
            self._window._theme_controller = None

    def _on_refresh(self, event: Event) -> None:
        if not self.closed:
            self.refresh()

    def _on_closed(self, event: Event) -> None:
        self.close()

    def _on_hidden(self, event: Event) -> None:
        self._cancel_transition()
        if self._window.root is not None:
            self._window.root.theme = self.effective_theme

    def _cancel_transition(self) -> None:
        if self._transition is not None:
            if self._animations is not None:
                self._animations.cancel(self._transition)
            self._transition.cancel()
            self._transition = None

    def _apply_theme(self, root: Component | None, theme: Theme) -> None:
        if (root is self._transition_root and theme == self._transition_target
                and self.transitioning and self._window.visible
                and self._window.native_handle is not None):
            return
        self._cancel_transition()
        self._transition_root, self._transition_target = root, theme
        if root is None:
            return
        source = root.theme
        driver = self._animations
        if (driver is None or driver.disposed or source is None or source == theme
                or self._last_state is None or not self._window.visible
                or self._window.native_handle is None):
            root.theme = theme
            return

        def update(value: Theme) -> None:
            if (not self.closed and self._window.root is root
                    and self._transition is transition):
                root.theme = value

        transition = ThemeTransition(source, theme, theme.motion_duration, update)
        self._transition = transition
        driver.play(transition)

    def _require_open(self) -> None:
        if self.closed:
            raise RuntimeError("The theme controller is closed.")
