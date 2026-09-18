"""Component-to-SceneGraph bridge for retained SwirUI widgets."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, runtime_checkable

from swirui.core import Component, Event
from swirui.rendering.geometry import Rect
from swirui.rendering.scene import Scene, SceneNode, SceneNodeKind
from swirui.window import Window

from .base import Widget


@runtime_checkable
class SceneRenderable(Protocol):
    """Structural contract implemented by visual retained components."""

    def build_scene_node(self) -> SceneNode: ...


@runtime_checkable
class SceneLayoutPreparer(Protocol):
    """Optional pre-compilation hook for retained layout containers."""

    def prepare_layout(self, viewport: Rect) -> None: ...


@runtime_checkable
class SceneChildPreparer(Protocol):
    """Optional hook for containers that transform compiled child scene nodes."""

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
    """Compile a visible component tree into a renderer-ready SceneGraph.

    Logical container components become transparent scene groups only when they
    contain visual descendants. Layout preparation runs before descendant
    compilation, allowing retained containers to arrange child Widget bounds
    without rebuilding the tree a second time. Disabled ancestors make their
    full visual subtree non-hit-testable without hiding it.

    Widget layout preparers are revision/viewport cached. A paint-only retained
    invalidation still recompiles the scene, but unchanged layout containers do
    not repeat measurement and arrangement until geometry-relevant state or the
    logical viewport actually changes.
    """

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
        prepare_layout = True
        if isinstance(component, Widget):
            prepare_layout = component._layout_preparation_needed(viewport)
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


def _child_viewport(child: Component, fallback: Rect) -> Rect:
    """Prefer an already-arranged child bounds rectangle for nested layouts."""

    bounds = getattr(child, "bounds", None)
    return bounds if isinstance(bounds, Rect) else fallback


class WidgetRuntime:
    """Mount a retained widget tree into one framework Window.

    The runtime listens once to root-level invalidation. Widget mutations rebuild
    the backend-neutral SceneGraph synchronously, and ``Window.set_scene`` then
    uses the application's existing scene invalidation/scheduler path. Native GPU
    contexts, text shaping, HiDPI conversion and presentation therefore remain in
    the established renderer rather than being reimplemented by widgets.
    """

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
        self._detach()
        self.root = root
        self.window.set_root(root)
        self._unsubscribers = [
            root.on("invalidated", self._on_root_invalidated),
            self.window.on("resized", self._on_window_resized),
            self.window.on("root_changed", self._on_window_root_changed),
            self.window.on("closed", self._on_window_closed),
        ]
        self.rebuild()
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
        for unsubscribe in self._unsubscribers:
            unsubscribe()
        self._unsubscribers.clear()
        self.root = None

    def _on_root_invalidated(self, _event: Event) -> None:
        self.rebuild()

    def _on_window_resized(self, _event: Event) -> None:
        self.rebuild()

    def _on_window_root_changed(self, event: Event) -> None:
        if event.data.get("root") is not self.root:
            self._detach()
            self.window.set_scene(None)

    def _on_window_closed(self, _event: Event) -> None:
        self._detach()


def mount(window: Window, root: Component) -> WidgetRuntime:
    """Convenience helper that mounts ``root`` and returns its retained runtime."""

    return WidgetRuntime(window).mount(root)
