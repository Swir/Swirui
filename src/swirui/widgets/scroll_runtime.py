"""Retained runtime extension that routes native scroll input through components."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from swirui.core import Component, Event
from swirui.platforms import PlatformEvent, PlatformEventKind

from .runtime import WidgetRuntime as _WidgetRuntime
from .scroll_events import scroll_residual

if TYPE_CHECKING:
    from swirui.window import Window


class WidgetRuntime(_WidgetRuntime):
    """Widget runtime with hit-tested capture/target/bubble scroll routing."""

    def __init__(self, window: Window) -> None:
        super().__init__(window)
        self._scroll_router_bound = False

    def mount(self, root: Component) -> WidgetRuntime:
        super().mount(root)
        if self.root is root and not self._scroll_router_bound:
            self._unsubscribers.append(
                self.window.on(PlatformEventKind.POINTER_SCROLL.value, self._on_pointer_scroll)
            )
            self._scroll_router_bound = True
        return self

    def _detach(self) -> None:
        super()._detach()
        self._scroll_router_bound = False

    def _on_pointer_scroll(self, event: Event) -> None:
        platform_event = event.data.get("event")
        if (
            not isinstance(platform_event, PlatformEvent)
            or platform_event.kind is not PlatformEventKind.POINTER_SCROLL
            or platform_event.x is None
            or platform_event.y is None
        ):
            return

        scene = self.window.scene
        if scene is None:
            return
        logical_event = self.window._logical_pointer_event(platform_event)
        assert logical_event.x is not None
        assert logical_event.y is not None
        scene_path = scene.hit_path_xy(logical_event.x, logical_event.y)
        scene_target = scene_path[-1] if scene_path else None
        component_path = self.window._component_path_for_scene_target(scene_target)
        if not component_path:
            return

        routed = self.window._route_component_pointer_event(
            PlatformEventKind.POINTER_SCROLL.value,
            logical_event,
            scene_target,
            scene_path,
            component_path,
        )
        if routed is None:
            return

        event.data["target"] = scene_target
        event.data["path"] = scene_path
        event.data["component_target"] = component_path[-1]
        event.data["component_path"] = component_path
        event.data["routed_event"] = routed

        if routed.default_prevented:
            event.prevent_default()
            residual = scroll_residual(routed)
            if residual is not None:
                event.data.setdefault("original_event", platform_event)
                event.data["event"] = replace(
                    platform_event,
                    delta_x=residual[0],
                    delta_y=residual[1],
                )
        if routed.propagation_stopped:
            event.stop_propagation()


def mount(window: Window, root: Component) -> WidgetRuntime:
    """Mount ``root`` with retained pointer-scroll routing enabled."""

    return WidgetRuntime(window).mount(root)
