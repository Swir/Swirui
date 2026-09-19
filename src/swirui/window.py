"""Window model for SwirUI."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from .core import Component, Event, EventEmitter, EventPhase
from .platforms import (
    DisplayInfo,
    NativeWindowHandle,
    PlatformBackend,
    PlatformEvent,
    PlatformEventKind,
)

if TYPE_CHECKING:
    from .rendering.scene import Scene, SceneNode


_POINTER_EVENTS = {
    PlatformEventKind.POINTER_MOVE,
    PlatformEventKind.POINTER_DOWN,
    PlatformEventKind.POINTER_UP,
}
_KEYBOARD_EVENTS = {
    PlatformEventKind.KEY_DOWN,
    PlatformEventKind.KEY_UP,
    PlatformEventKind.TEXT_INPUT,
}
_VK_TAB = 0x09


class Window(EventEmitter):
    """Framework-level window model independent of a specific native backend.

    Public geometry is expressed in logical device-independent pixels (DIPs).
    Native backends may receive physical pixel coordinates; SwirUI converts them
    at the window boundary so prepared scenes and routed input use one stable
    coordinate space across mixed-DPI monitors.
    """

    def __init__(
        self,
        *,
        title: str = "SwirUI",
        width: int = 960,
        height: int = 640,
        min_width: int = 320,
        min_height: int = 240,
    ) -> None:
        super().__init__()
        if width <= 0 or height <= 0:
            raise ValueError("Window dimensions must be positive.")
        if min_width <= 0 or min_height <= 0:
            raise ValueError("Minimum window dimensions must be positive.")

        self.title = title
        self.width = width
        self.height = height
        self.min_width = min_width
        self.min_height = min_height
        self.scale = 1.0
        self.display: DisplayInfo | None = None
        self.root: Component | None = None
        self.scene: Scene | None = None
        self.hovered_scene_node: SceneNode | None = None
        self.focused_component: Component | None = None
        self.pointer_capture_component: Component | None = None
        self.visible = False
        self.closed = False
        self.focused = False
        self.native_handle: NativeWindowHandle | None = None
        self._platform_backend: PlatformBackend | None = None

    @property
    def pixel_width(self) -> int:
        """Current client width in physical pixels for renderer surfaces."""

        return max(1, round(self.width * self.scale))

    @property
    def pixel_height(self) -> int:
        """Current client height in physical pixels for renderer surfaces."""

        return max(1, round(self.height * self.scale))

    @property
    def pixel_size(self) -> tuple[int, int]:
        """Current physical-pixel size corresponding to the logical window size."""

        return (self.pixel_width, self.pixel_height)

    def logical_to_physical(self, value: float) -> float:
        """Convert one logical DIP coordinate or extent to physical pixels."""

        return value * self.scale

    def physical_to_logical(self, value: float) -> float:
        """Convert one physical-pixel coordinate or extent to logical DIPs."""

        return value / self.scale

    def set_root(self, component: Component | None) -> Window:
        old_root = self.root
        if self.focused_component is not None and not self._component_belongs_to(
            component, self.focused_component
        ):
            self.focus_component(None)
        if self.pointer_capture_component is not None and not self._component_belongs_to(
            component, self.pointer_capture_component
        ):
            self.release_pointer_capture()
        self.root = component
        self.emit("root_changed", old_root=old_root, root=component)
        return self

    def set_scene(self, scene: Scene | None) -> Window:
        """Attach a prepared render scene and invalidate the next frame."""

        old_scene = self.scene
        self.scene = scene
        self.hovered_scene_node = None
        self.emit("scene_changed", old_scene=old_scene, scene=scene)
        return self

    def focus_component(self, component: Component | None) -> None:
        """Move logical keyboard focus to a focusable component in this window.

        Focus is independent from the operating-system window activation state.
        Keyboard and text-input platform events are routed through the focused
        component's ancestry using capture → target → bubble phases.
        """

        if component is self.focused_component:
            return
        if component is not None:
            if not self._component_belongs_to(self.root, component):
                raise ValueError("Focused component must belong to the window root tree.")
            if not component.focusable:
                raise ValueError("Focused component must be focusable.")
            component_path = self._component_path_for_component(component)
            if not component_path or any(
                not item.enabled or not item.visible for item in component_path
            ):
                raise ValueError(
                    "Focused component and its ancestors must be enabled and visible."
                )

        old_component = self.focused_component
        self.focused_component = component
        if old_component is not None:
            old_component.emit("focus_lost", window=self, related_target=component)
        if component is not None:
            component.emit("focus_gained", window=self, related_target=old_component)
        self.emit(
            "component_focus_changed",
            old_component=old_component,
            component=component,
        )

    def capture_pointer(self, component: Component) -> None:
        """Capture subsequent pointer routing to one mounted component.

        Capture remains logically active until explicit release, pointer-up,
        focus loss, hiding, closing, or removal of the captured component from
        the current root tree. Native backends may additionally acquire their
        operating-system pointer grab so moves/up events continue outside the
        window while a retained drag is active.
        """

        component_path = self._component_path_for_component(component)
        if not component_path:
            raise ValueError("Pointer capture component must belong to the window root tree.")
        if any(not item.enabled or not item.visible for item in component_path):
            raise ValueError("Pointer capture component and ancestors must be enabled and visible.")
        if component is self.pointer_capture_component:
            return

        old_component = self.pointer_capture_component
        self.pointer_capture_component = component
        native_acquired = self._set_native_pointer_capture(True)
        if old_component is not None:
            old_component.emit(
                "pointer_capture_lost",
                window=self,
                related_target=component,
            )
        component.emit(
            "pointer_capture_gained",
            window=self,
            related_target=old_component,
            native=native_acquired,
        )
        self.emit(
            "pointer_capture_changed",
            old_component=old_component,
            component=component,
            native=native_acquired,
        )

    def release_pointer_capture(self, component: Component | None = None) -> None:
        """Release the current pointer capture if owned by ``component`` when supplied."""

        captured = self.pointer_capture_component
        if captured is None or (component is not None and captured is not component):
            return
        self.pointer_capture_component = None
        native_released = self._set_native_pointer_capture(False)
        captured.emit(
            "pointer_capture_lost",
            window=self,
            related_target=None,
            native=native_released,
        )
        self.emit(
            "pointer_capture_changed",
            old_component=captured,
            component=None,
            native=native_released,
        )

    def focus_next(self, *, reverse: bool = False) -> Component | None:
        """Move focus through eligible components in deterministic tree order."""

        if self.root is None:
            self.focus_component(None)
            return None
        candidates = [
            component
            for component in self.root.walk()
            if self._component_is_focus_candidate(component)
        ]
        if not candidates:
            self.focus_component(None)
            return None

        step = -1 if reverse else 1
        current = self.focused_component
        if current is None or current not in candidates:
            next_component = candidates[-1] if reverse else candidates[0]
        else:
            current_index = candidates.index(current)
            next_component = candidates[(current_index + step) % len(candidates)]
        self.focus_component(next_component)
        return next_component

    def set_title(self, title: str) -> None:
        if title == self.title:
            return
        old_title = self.title
        self.title = title
        if self._platform_backend is not None and self.native_handle is not None:
            self._platform_backend.set_window_title(self.native_handle, title)
        self.emit("title_changed", old_title=old_title, title=title)

    def resize(self, width: int, height: int) -> None:
        """Resize using logical DIPs while the backend receives physical pixels."""

        width = max(width, self.min_width)
        height = max(height, self.min_height)
        if (width, height) == (self.width, self.height):
            return
        old_size = (self.width, self.height)
        self.width = width
        self.height = height
        if self._platform_backend is not None and self.native_handle is not None:
            self._platform_backend.resize_window(
                self.native_handle,
                self.pixel_width,
                self.pixel_height,
            )
        self.emit("resized", old_size=old_size, size=(width, height))

    def show(self) -> None:
        if self.closed:
            raise RuntimeError("A closed window cannot be shown again.")
        if not self.visible:
            if self._platform_backend is not None and self.native_handle is not None:
                self._platform_backend.show_window(self.native_handle)
            self.visible = True
            self.emit("shown")

    def hide(self) -> None:
        if self.visible:
            self.release_pointer_capture()
            if self._platform_backend is not None and self.native_handle is not None:
                self._platform_backend.hide_window(self.native_handle)
            self.visible = False
            self.hovered_scene_node = None
            self.emit("hidden")

    def close(self) -> None:
        if self.closed:
            return
        self.release_pointer_capture()
        if self._platform_backend is not None and self.native_handle is not None:
            self._platform_backend.destroy_window(self.native_handle)
        self._mark_closed()
        self._unbind_native()

    def _bind_native(self, backend: PlatformBackend, handle: NativeWindowHandle) -> None:
        if self.native_handle is not None:
            raise RuntimeError("Window is already bound to a native handle.")
        self._platform_backend = backend
        self.native_handle = handle
        initial_scale = backend.window_scale(handle)
        if initial_scale > 0.0:
            self.scale = initial_scale
        self._refresh_display()
        self.emit("native_bound", handle=handle, scale=self.scale, display=self.display)

    def _unbind_native(self) -> None:
        if self.pointer_capture_component is not None:
            self.release_pointer_capture()
        if self.native_handle is None:
            self._platform_backend = None
            self.display = None
            return
        old_handle = self.native_handle
        self.native_handle = None
        self._platform_backend = None
        self.display = None
        self.emit("native_unbound", handle=old_handle)

    def _apply_platform_event(self, event: PlatformEvent) -> None:
        if event.kind is PlatformEventKind.CLOSE:
            self._mark_closed()
            self._unbind_native()
            return

        if event.kind is PlatformEventKind.RESIZE:
            if event.width is None or event.height is None:
                return
            width = max(round(self.physical_to_logical(event.width)), self.min_width)
            height = max(round(self.physical_to_logical(event.height)), self.min_height)
            if (width, height) != (self.width, self.height):
                old_size = (self.width, self.height)
                self.width = width
                self.height = height
                self.emit("resized", old_size=old_size, size=(width, height))
            return

        if event.kind is PlatformEventKind.DPI_CHANGED:
            if event.scale is not None and event.scale > 0.0:
                self._set_scale(event.scale)
            self._refresh_display()
            return

        if event.kind is PlatformEventKind.DISPLAY_CHANGED:
            self._refresh_display()
            return

        if event.kind is PlatformEventKind.FOCUS:
            focused = bool(event.focused)
            if not focused:
                self.release_pointer_capture()
            if focused != self.focused:
                self.focused = focused
                self.emit("focus_changed", focused=focused)
            return

        if event.kind in _POINTER_EVENTS:
            self._apply_pointer_event(self._logical_pointer_event(event))
            return

        if event.kind in _KEYBOARD_EVENTS:
            self._apply_keyboard_event(event)
            return

        self.emit(event.kind.value, event=event)

    def _set_scale(self, scale: float) -> None:
        if scale <= 0.0 or scale == self.scale:
            return
        old_scale = self.scale
        self.scale = scale
        self.emit(
            "scale_changed",
            old_scale=old_scale,
            scale=scale,
            pixel_size=self.pixel_size,
        )

    def _refresh_display(self) -> None:
        backend = self._platform_backend
        handle = self.native_handle
        if backend is None or handle is None:
            return
        resolver = getattr(backend, "window_display", None)
        display = resolver(handle) if callable(resolver) else None
        self._set_display(display)

    def _set_display(self, display: DisplayInfo | None) -> None:
        if display == self.display:
            return
        old_display = self.display
        self.display = display
        if display is not None:
            self._set_scale(display.scale)
        self.emit("display_changed", old_display=old_display, display=display)

    def _set_native_pointer_capture(self, capture: bool) -> bool:
        backend = self._platform_backend
        handle = self.native_handle
        if backend is None or handle is None:
            return False
        method = getattr(
            backend,
            "capture_pointer" if capture else "release_pointer",
            None,
        )
        if not callable(method):
            return False
        try:
            result = method(handle)
        except (OSError, RuntimeError, ValueError):
            return False
        return result is not False

    def _logical_pointer_event(self, event: PlatformEvent) -> PlatformEvent:
        """Translate native physical pointer coordinates into logical DIPs."""

        if event.x is None and event.y is None:
            return event
        return replace(
            event,
            x=self.physical_to_logical(event.x) if event.x is not None else None,
            y=self.physical_to_logical(event.y) if event.y is not None else None,
        )

    def _apply_pointer_event(self, event: PlatformEvent) -> None:
        scene_path: tuple[SceneNode, ...] = ()
        if self.scene is not None and event.x is not None and event.y is not None:
            scene_path = self.scene.hit_path_xy(event.x, event.y)
        scene_target = scene_path[-1] if scene_path else None
        hit_component_path = self._component_path_for_scene_target(scene_target)
        hit_component_target = hit_component_path[-1] if hit_component_path else None

        captured = self.pointer_capture_component
        component_path = hit_component_path
        if captured is not None:
            captured_path = self._component_path_for_component(captured)
            if captured_path and all(item.enabled and item.visible for item in captured_path):
                component_path = captured_path
            else:
                self.release_pointer_capture(captured)
        component_target = component_path[-1] if component_path else None

        if (
            event.kind is PlatformEventKind.POINTER_DOWN
            and hit_component_target is not None
            and self._component_is_focus_candidate(hit_component_target)
        ):
            self.focus_component(hit_component_target)

        pointer_target_changed = (
            event.kind is PlatformEventKind.POINTER_MOVE
            and scene_target is not self.hovered_scene_node
        )
        if pointer_target_changed:
            previous_scene_target = self.hovered_scene_node
            previous_component_path = self._component_path_for_scene_target(previous_scene_target)
            previous_component_target = (
                previous_component_path[-1] if previous_component_path else None
            )
            self.hovered_scene_node = scene_target

            if previous_scene_target is not None:
                routed_leave = self._dispatch_direct_component_pointer_event(
                    "pointer_leave",
                    event,
                    previous_scene_target,
                    previous_component_path,
                )
                self.emit(
                    "pointer_leave",
                    event=event,
                    target=previous_scene_target,
                    component_target=previous_component_target,
                    component_path=previous_component_path,
                    routed_event=routed_leave,
                )

            if scene_target is not None:
                routed_enter = self._dispatch_direct_component_pointer_event(
                    "pointer_enter",
                    event,
                    scene_target,
                    hit_component_path,
                )
                self.emit(
                    "pointer_enter",
                    event=event,
                    target=scene_target,
                    path=scene_path,
                    component_target=hit_component_target,
                    component_path=hit_component_path,
                    routed_event=routed_enter,
                )

        routed_event = self._route_component_pointer_event(
            event.kind.value,
            event,
            scene_target,
            scene_path,
            component_path,
        )
        self.emit(
            event.kind.value,
            event=event,
            target=scene_target,
            path=scene_path,
            component_target=component_target,
            component_path=component_path,
            hit_component_target=hit_component_target,
            hit_component_path=hit_component_path,
            pointer_captured=self.pointer_capture_component is not None,
            routed_event=routed_event,
        )

        if event.kind is PlatformEventKind.POINTER_UP:
            self.release_pointer_capture()

    def _apply_keyboard_event(self, event: PlatformEvent) -> None:
        focused = self.focused_component
        if focused is not None and not self._component_is_focus_candidate(focused):
            self.focus_component(None)

        component_path = self._component_path_for_component(self.focused_component)
        component_target = component_path[-1] if component_path else None
        routed_event = self._route_component_keyboard_event(
            event.kind.value,
            event,
            component_path,
        )
        window_event = self.emit(
            event.kind.value,
            event=event,
            component_target=component_target,
            component_path=component_path,
            routed_event=routed_event,
        )

        is_tab_traversal = (
            event.kind is PlatformEventKind.KEY_DOWN
            and event.key_code == _VK_TAB
            and not event.ctrl
            and not event.alt
            and not event.meta
        )
        if not is_tab_traversal:
            return
        if window_event.default_prevented or (
            routed_event is not None and routed_event.default_prevented
        ):
            return

        previous = self.focused_component
        component = self.focus_next(reverse=event.shift)
        self.emit(
            "keyboard_focus_traversed",
            previous=previous,
            component=component,
            reverse=event.shift,
            event=event,
        )

    def _component_path_for_scene_target(
        self,
        scene_target: SceneNode | None,
    ) -> tuple[Component, ...]:
        """Map a prepared SceneNode back to its component by stable key."""

        if self.root is None or scene_target is None:
            return ()
        target = self.root.find(scene_target.key)
        return self._component_path_for_component(target)

    def _component_path_for_component(
        self,
        target: Component | None,
    ) -> tuple[Component, ...]:
        if self.root is None or target is None:
            return ()

        path: list[Component] = []
        current: Component | None = target
        while current is not None:
            path.append(current)
            current = current.parent
        path.reverse()
        if not path or path[0] is not self.root:
            return ()
        return tuple(path)

    def _component_is_focus_candidate(self, component: Component) -> bool:
        if not component.focusable:
            return False
        component_path = self._component_path_for_component(component)
        return bool(component_path) and all(
            item.enabled and item.visible for item in component_path
        )

    @staticmethod
    def _component_belongs_to(root: Component | None, target: Component) -> bool:
        return root is not None and any(component is target for component in root.walk())

    def _route_component_pointer_event(
        self,
        event_type: str,
        platform_event: PlatformEvent,
        scene_target: SceneNode | None,
        scene_path: tuple[SceneNode, ...],
        component_path: tuple[Component, ...],
    ) -> Event | None:
        if not component_path:
            return None

        target = component_path[-1]
        routed = Event(
            type=event_type,
            source=target,
            data={
                "event": platform_event,
                "scene_target": scene_target,
                "scene_path": scene_path,
                "component_target": target,
                "component_path": component_path,
            },
        )

        for component in component_path[:-1]:
            routed.phase = EventPhase.CAPTURE
            component.dispatch(routed, capture=True)
            if routed.propagation_stopped:
                return routed

        routed.phase = EventPhase.TARGET
        target.dispatch(routed, capture=True)
        if routed.propagation_stopped:
            return routed
        target.dispatch(routed)
        if routed.propagation_stopped:
            return routed

        for component in reversed(component_path[:-1]):
            routed.phase = EventPhase.BUBBLE
            component.dispatch(routed)
            if routed.propagation_stopped:
                break
        return routed

    def _route_component_keyboard_event(
        self,
        event_type: str,
        platform_event: PlatformEvent,
        component_path: tuple[Component, ...],
    ) -> Event | None:
        if not component_path:
            return None

        target = component_path[-1]
        routed = Event(
            type=event_type,
            source=target,
            data={
                "event": platform_event,
                "component_target": target,
                "component_path": component_path,
            },
        )

        for component in component_path[:-1]:
            routed.phase = EventPhase.CAPTURE
            component.dispatch(routed, capture=True)
            if routed.propagation_stopped:
                return routed

        routed.phase = EventPhase.TARGET
        target.dispatch(routed, capture=True)
        if routed.propagation_stopped:
            return routed
        target.dispatch(routed)
        if routed.propagation_stopped:
            return routed

        for component in reversed(component_path[:-1]):
            routed.phase = EventPhase.BUBBLE
            component.dispatch(routed)
            if routed.propagation_stopped:
                break
        return routed

    def _dispatch_direct_component_pointer_event(
        self,
        event_type: str,
        platform_event: PlatformEvent,
        scene_target: SceneNode,
        component_path: tuple[Component, ...],
    ) -> Event | None:
        if not component_path:
            return None
        target = component_path[-1]
        routed = Event(
            type=event_type,
            source=target,
            data={
                "event": platform_event,
                "scene_target": scene_target,
                "component_target": target,
                "component_path": component_path,
            },
            phase=EventPhase.DIRECT,
        )
        target.dispatch(routed)
        return routed

    def _mark_closed(self) -> None:
        if self.closed:
            return
        self.release_pointer_capture()
        self.focus_component(None)
        self.visible = False
        self.focused = False
        self.hovered_scene_node = None
        self.closed = True
        self.emit("closed")

    def __repr__(self) -> str:
        display_name = self.display.name if self.display is not None else None
        return (
            f"Window(title={self.title!r}, width={self.width}, height={self.height}, "
            f"scale={self.scale}, pixel_size={self.pixel_size}, display={display_name!r}, "
            f"visible={self.visible}, closed={self.closed})"
        )