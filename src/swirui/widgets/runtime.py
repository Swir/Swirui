"""Component-to-SceneGraph bridge for retained SwirUI widgets."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, runtime_checkable

from swirui.core import Component, Event
from swirui.core.state import schedule_reactive_update
from swirui.rendering.geometry import CornerRadius, Path2D, Point, Rect
from swirui.rendering.scene import Scene, SceneNode, SceneNodeKind
from swirui.window import Window

from .base import Widget


@runtime_checkable
class SceneRenderable(Protocol):
    def build_scene_node(self) -> SceneNode: ...


@runtime_checkable
class SceneLayoutPreparer(Protocol):
    def prepare_layout(self, viewport: Rect) -> None: ...


@runtime_checkable
class SceneChildPreparer(Protocol):
    def prepare_scene_children(
        self,
        children: tuple[SceneNode, ...],
    ) -> tuple[SceneNode, ...]: ...


def compile_component_scene(
    root: Component | None,
    *,
    width: float,
    height: float,
    generation: int = 0,
) -> Scene | None:
    """Compile a visible component tree into a renderer-ready SceneGraph."""

    viewport = Rect(0.0, 0.0, float(width), float(height))
    if root is None or not root.visible:
        return None
    scene_root = _compile_component(root, viewport=viewport, ancestors_enabled=True)
    if scene_root is None:
        return None
    return Scene(float(width), float(height), scene_root, generation=generation)


def _compile_component(
    component: Component,
    *,
    viewport: Rect,
    ancestors_enabled: bool,
) -> SceneNode | None:
    if not component.visible:
        return None

    effective_enabled = ancestors_enabled and component.enabled
    if isinstance(component, SceneLayoutPreparer):
        prepare_layout = not isinstance(component, Widget) or component._layout_preparation_needed(
            viewport
        )
        if prepare_layout:
            component.prepare_layout(viewport)
            if isinstance(component, Widget):
                component._mark_layout_prepared(viewport)

    visual_node = component.build_scene_node() if isinstance(component, SceneRenderable) else None
    descendant_viewport = visual_node.bounds if visual_node is not None else viewport

    child_nodes = tuple(
        node
        for child in component.children
        if (
            node := _compile_component(
                child,
                viewport=_child_viewport(child, descendant_viewport),
                ancestors_enabled=effective_enabled,
            )
        )
        is not None
    )

    if visual_node is not None:
        if not effective_enabled:
            visual_node.hit_testable = False
        if isinstance(component, SceneChildPreparer):
            child_nodes = component.prepare_scene_children(child_nodes)
        visual_node.add(*child_nodes)
        if isinstance(component, Widget):
            if component.visual_clip is not None:
                visual_node.clip_rect = component.visual_clip
            scale = component.visual_scale
            if scale != 1.0:
                bounds = visual_node.bounds
                pivot = Point(bounds.x + bounds.width * 0.5, bounds.y + bounds.height * 0.5)
                _scale_scene_subtree(visual_node, scale, pivot)
            offset = component.visual_offset
            if offset.x != 0.0 or offset.y != 0.0:
                _translate_scene_subtree(visual_node, offset.x, offset.y)
        return visual_node

    if not child_nodes:
        return None
    node = SceneNode(
        key=component.key,
        kind=SceneNodeKind.GROUP,
        bounds=viewport,
        hit_testable=False,
    )
    node.add(*child_nodes)
    return node


def _scale_rect(bounds: Rect, scale: float, pivot: Point) -> Rect:
    return Rect(
        pivot.x + (bounds.x - pivot.x) * scale,
        pivot.y + (bounds.y - pivot.y) * scale,
        bounds.width * scale,
        bounds.height * scale,
    )


def _scale_scene_subtree(node: SceneNode, scale: float, pivot: Point) -> None:
    node.bounds = _scale_rect(node.bounds, scale, pivot)
    if node.clip_rect is not None:
        node.clip_rect = _scale_rect(node.clip_rect, scale, pivot)
    radius = node.corner_radius
    node.corner_radius = CornerRadius(
        radius.top_left * scale,
        radius.top_right * scale,
        radius.bottom_right * scale,
        radius.bottom_left * scale,
    )
    if node.kind is SceneNodeKind.TEXT:
        node.font_size *= scale
    if node.kind is SceneNodeKind.PATH and node.path is not None:
        node.path = Path2D(tuple(Point(point.x * scale, point.y * scale) for point in node.path.points))
    for child in node.children:
        _scale_scene_subtree(child, scale, pivot)


def _translate_scene_subtree(node: SceneNode, dx: float, dy: float) -> None:
    bounds = node.bounds
    node.bounds = Rect(bounds.x + dx, bounds.y + dy, bounds.width, bounds.height)
    if node.clip_rect is not None:
        clip = node.clip_rect
        node.clip_rect = Rect(clip.x + dx, clip.y + dy, clip.width, clip.height)
    for child in node.children:
        _translate_scene_subtree(child, dx, dy)


def _child_viewport(child: Component, fallback: Rect) -> Rect:
    bounds = getattr(child, "bounds", None)
    return bounds if isinstance(bounds, Rect) else fallback


class WidgetRuntime:
    """Mount a retained widget tree into one framework Window."""

    def __init__(self, window: Window) -> None:
        self.window = window
        self.root: Component | None = None
        self.generation = 0
        self._unsubscribers: list[Callable[[], None]] = []

    @property
    def mounted(self) -> bool:
        return self.root is not None

    def mount(self, root: Component) -> WidgetRuntime:
        if self.root is root and self.window.root is root:
            return self
        if root.mounted:
            raise ValueError("Component tree is already mounted by another runtime.")

        self._detach()
        self.root = root
        self.window.set_root(root)
        try:
            root._mount(self.window)
            self._unsubscribers = [
                root.on("invalidated", self._on_root_invalidated),
                self.window.on("resized", self._on_window_resized),
                self.window.on("root_changed", self._on_window_root_changed),
                self.window.on("closed", self._on_window_closed),
            ]
            self.rebuild()
        except BaseException:
            self._detach()
            if self.window.root is root:
                self.window.set_root(None)
            self.window.set_scene(None)
            raise
        return self

    def rebuild(self) -> Scene | None:
        root = self.root
        if root is None:
            return None
        self.generation += 1
        scene = compile_component_scene(
            root,
            width=float(self.window.width),
            height=float(self.window.height),
            generation=self.generation,
        )
        hovered_key = (
            self.window.hovered_scene_node.key
            if self.window.hovered_scene_node is not None
            else None
        )
        self.window.set_scene(scene)
        if scene is not None and hovered_key is not None:
            self.window.hovered_scene_node = next(
                (node for node in scene.walk() if node.key == hovered_key),
                None,
            )
        return scene

    def unmount(self) -> None:
        root = self.root
        self._detach()
        if root is not None and self.window.root is root:
            self.window.set_root(None)
        self.window.set_scene(None)

    def _detach(self) -> None:
        root = self.root
        for unsubscribe in self._unsubscribers:
            unsubscribe()
        self._unsubscribers.clear()
        self.root = None
        if root is not None and root.mounted_window is self.window:
            root._unmount()

    def _rebuild_scheduled(self) -> None:
        self.rebuild()

    def _on_root_invalidated(self, _event: Event) -> None:
        schedule_reactive_update(self, self._rebuild_scheduled)

    def _on_window_resized(self, _event: Event) -> None:
        self.rebuild()

    def _on_window_root_changed(self, event: Event) -> None:
        if event.data.get("root") is not self.root:
            self._detach()
            self.window.set_scene(None)

    def _on_window_closed(self, _event: Event) -> None:
        self._detach()


def mount(window: Window, root: Component) -> WidgetRuntime:
    return WidgetRuntime(window).mount(root)
