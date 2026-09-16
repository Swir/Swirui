"""Window model for SwirUI."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .core import Component, Event, EventEmitter, EventPhase
from .platforms import NativeWindowHandle, PlatformBackend, PlatformEvent, PlatformEventKind

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


class Window(EventEmitter):
    """Framework-level window model independent of a specific native backend."""

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
        self.root: Component | None = None
        self.scene: Scene | None = None
        self.hovered_scene_node: SceneNode | None = None
        self.focused_component: Component | None = None
        self.visible = False
        self.closed = False
        self.focused = False
        self.native_handle: NativeWindowHandle | None = None
        self._platform_backend: PlatformBackend | None = None

    def set_root(self, component: Component | None) -> Window:
        old_root = self.root
        if self.focused_component is not None and not self._component_belongs_to(
            component, self.focused_component
        ):
            self.focus_component(None)
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
            if not component.enabled or not component.visible:
                raise ValueError("Focused component must be enabled and visible.")

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

    def focus_next(self, *, reverse: bool = False) -> Component | None:
        """Move focus through enabled, visible, focusable components in tree order."""

        if self.root is None:
            self.focus_component(None)
            return None
        candidates = [
            component
            for component in self.root.walk()
            if component.focusable and component.enabled and component.visible
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
        width = max(width, self.min_width)
        height = max(height, self.min_height)
        if (width, height) == (self.width, self.height):
            return
        old_size = (self.width, self.height)
        self.width = width
        self.height = height
        if self._platform_backend is not None and self.native_handle is not None:
            self._platform_backend.resize_window(self.native_handle, width, height)
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
            if self._platform_backend is not None and self.native_handle is not None:
                self._platform_backend.hide_window(self.native_handle)
            self.visible = False
            self.hovered_scene_node = None
            self.emit("hidden")

    def close(self) -> None:
        if self.closed:
            return
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
        self.emit("native_bound", handle=handle, scale=self.scale)

    def _unbind_native(self) -> None:
        if self.native_handle is None:
            self._platform_backend = None
            return
        old_handle = self.native_handle
        self.native_handle = None
        self._platform_backend = None
        self.emit("native_unbound", handle=old_handle)

    def _apply_platform_event(self, event: PlatformEvent) -> None:
        if event.kind is PlatformEventKind.CLOSE:
            self._mark_closed()
            self._unbind_native()
            return

        if event.kind is PlatformEventKind.RESIZE:
            if event.width is None or event.height is None:
                return
            width = max(event.width, self.min_width)
            height = max(event.height, self.min_height)
            if (width, height) != (self.width, self.height):
                old_size = (self.width, self.height)
                self.width = width
                self.height = height
                self.emit("resized", old_size=old_size, size=(width, height))
            return

        if event.kind is PlatformEventKind.DPI_CHANGED:
            if event.scale is not None and event.scale > 0.0:
                self._set_scale(event.scale)
            return

        if event.kind is PlatformEventKind.FOCUS:
            focused = bool(event.focused)
            if focused != self.focused:
                self.focused = focused
                self.emit("focus_changed", focused=focused)
            return

        if event.kind in _POINTER_EVENTS:
            self._apply_pointer_event(event)
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
        self.emit("scale_changed", old_scale=old_scale, scale=scale)

    def _apply_pointer_event(self, event: PlatformEvent) -> None:
        scene_path: tuple[SceneNode, ...] = ()
        if self.scene is not None and event.x is not None and event.y is not None:
            scene_path = self.scene.hit_path_xy(event.x, event.y)
        scene_target = scene_path[-1] if scene_path else None
        component_path = self._component_path_for_scene_target(scene_target)
        component_target = component_path[-1] if component_path else None

        if (
            event.kind is PlatformEventKind.POINTER_DOWN
            and component_target is not None
            and component_target.focusable
            and component_target.enabled
            and component_target.visible
        ):
            self.focus_component(component_target)

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
                    component_path,
                )
                self.emit(
                    "pointer_enter",
                    event=event,
                    target=scene_target,
                    path=scene_path,
                    component_target=component_target,
                    component_path=component_path,
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
            routed_event=routed_event,
        )

    def _apply_keyboard_event(self, event: PlatformEvent) -> None:
        component_path = self._component_path_for_component(self.focused_component)
        if self.focused_component is not None and not component_path:
            self.focus_component(None)
        component_target = component_path[-1] if component_path else None
        routed_event = self._route_component_keyboard_event(
            event.kind.value,
            event,
            component_path,
        )
        self.emit(
            event.kind.value,
            event=event,
            component_target=component_target,
            component_path=component_path,
            routed_event=routed_event,
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
        self.focus_component(None)
        self.visible = False
        self.focused = False
        self.hovered_scene_node = None
        self.closed = True
        self.emit("closed")

    def __repr__(self) -> str:
        return (
            f"Window(title={self.title!r}, width={self.width}, height={self.height}, "
            f"scale={self.scale}, visible={self.visible}, closed={self.closed})"
        )
