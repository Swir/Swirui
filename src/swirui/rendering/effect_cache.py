"""Bounded retained-effect caching for immutable visual-effect inputs.

The cache sits above the renderer: it memoizes deterministic ``SceneNode``
subtrees produced by retained effects, then returns a structurally independent
clone for each logical scene key. Immutable geometry/color/path objects are
shared safely while mutable node/children containers are never exposed from the
cache itself.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from threading import RLock
from typing import Protocol

from .geometry import CornerRadius, Rect
from .scene import SceneNode

_TEMPLATE_KEY = "__swirui_effect_cache_template__"


class RetainedEffect(Protocol):
    """Structural contract implemented by standard retained surface effects."""

    def __hash__(self) -> int: ...

    def to_scene_node(
        self,
        key: str,
        bounds: Rect,
        *,
        corner_radius: CornerRadius | None = None,
        opacity: float = 1.0,
        z_index: int = 0,
    ) -> SceneNode: ...


@dataclass(frozen=True, slots=True)
class EffectCacheStats:
    """Immutable cache telemetry snapshot."""

    entries: int
    hits: int
    misses: int
    evictions: int

    @property
    def requests(self) -> int:
        return self.hits + self.misses

    @property
    def hit_rate(self) -> float:
        requests = self.requests
        return 0.0 if requests == 0 else self.hits / requests


_CacheKey = tuple[object, object, Rect, CornerRadius, float, int]


class EffectCache:
    """Thread-safe bounded LRU cache for deterministic retained effects.

    Standard frozen SwirUI effects such as ``DropShadow``, ``Glow``, ``Bloom``,
    ``DynamicShadow`` and ``AdaptiveLighting`` satisfy :class:`RetainedEffect`.
    Cache identity intentionally excludes the logical scene ``key`` so identical
    effect geometry can be reused while callers still receive independently keyed
    node trees.
    """

    def __init__(self, max_entries: int = 128) -> None:
        if max_entries <= 0:
            raise ValueError("EffectCache max_entries must be positive.")
        self._max_entries = max_entries
        self._entries: OrderedDict[_CacheKey, SceneNode] = OrderedDict()
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        self._lock = RLock()

    @property
    def max_entries(self) -> int:
        return self._max_entries

    @property
    def stats(self) -> EffectCacheStats:
        with self._lock:
            return EffectCacheStats(
                entries=len(self._entries),
                hits=self._hits,
                misses=self._misses,
                evictions=self._evictions,
            )

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)

    def clear(self) -> None:
        """Drop cached templates while preserving lifetime telemetry counters."""

        with self._lock:
            self._entries.clear()

    def invalidate(self, effect: RetainedEffect) -> int:
        """Drop every cached variant for ``effect`` and return the removed count.

        Bounds, radius, opacity and z-index are deliberately ignored so callers
        can release all retained variants of one immutable effect in a single
        operation without disturbing unrelated cache entries.
        """

        try:
            hash(effect)
        except TypeError as exc:
            raise TypeError("Cached retained effects must be hashable and immutable.") from exc

        with self._lock:
            matching = [
                cache_key
                for cache_key in self._entries
                if cache_key[0] is type(effect) and cache_key[1] == effect
            ]
            for cache_key in matching:
                del self._entries[cache_key]
            return len(matching)

    def reset_stats(self) -> None:
        """Reset hit/miss/eviction counters without invalidating cached templates."""

        with self._lock:
            self._hits = 0
            self._misses = 0
            self._evictions = 0

    def render(
        self,
        effect: RetainedEffect,
        key: str,
        bounds: Rect,
        *,
        corner_radius: CornerRadius | None = None,
        opacity: float = 1.0,
        z_index: int = 0,
    ) -> SceneNode:
        """Return a cached retained-effect subtree with caller-owned node identity.

        A cache hit skips the effect's tessellation/build work. Returned nodes are
        always fresh mutable containers, so adding/removing children on one scene
        cannot corrupt the cached template or another window's scene graph.
        """

        if not key:
            raise ValueError("Cached effect scene keys cannot be empty.")
        radius = CornerRadius() if corner_radius is None else corner_radius
        cache_key: _CacheKey = (
            type(effect),
            effect,
            bounds,
            radius,
            float(opacity),
            int(z_index),
        )
        try:
            hash(cache_key)
        except TypeError as exc:
            raise TypeError("Cached retained effects must be hashable and immutable.") from exc

        with self._lock:
            template = self._entries.pop(cache_key, None)
            if template is not None:
                self._entries[cache_key] = template
                self._hits += 1
                return _clone_tree(template, _TEMPLATE_KEY, key)

            self._misses += 1
            template = effect.to_scene_node(
                _TEMPLATE_KEY,
                bounds,
                corner_radius=radius,
                opacity=opacity,
                z_index=z_index,
            )
            self._entries[cache_key] = template
            if len(self._entries) > self._max_entries:
                self._entries.popitem(last=False)
                self._evictions += 1
            return _clone_tree(template, _TEMPLATE_KEY, key)


def _clone_tree(node: SceneNode, source_root: str, target_root: str) -> SceneNode:
    clone = SceneNode(
        key=_remap_key(node.key, source_root, target_root),
        kind=node.kind,
        bounds=node.bounds,
        opacity=node.opacity,
        z_index=node.z_index,
        fill=node.fill,
        corner_radius=node.corner_radius,
        path=node.path,
        text=node.text,
        font_size=node.font_size,
        font_family=node.font_family,
        resource_id=node.resource_id,
        clip_to_bounds=node.clip_to_bounds,
        hit_testable=node.hit_testable,
        blur_radius=node.blur_radius,
    )
    clone.add(*(_clone_tree(child, source_root, target_root) for child in node.children))
    return clone


def _remap_key(key: str, source_root: str, target_root: str) -> str:
    if key == source_root:
        return target_root
    prefix = f"{source_root}:"
    if key.startswith(prefix):
        return f"{target_root}{key[len(source_root):]}"
    return key
