"""Bounded retained-effect caching for immutable visual-effect inputs.

The cache memoizes deterministic ``SceneNode`` subtrees and returns a structurally
independent clone for each logical scene key. Entry-count and retained-node limits
bound both cache cardinality and the cost of high-quality retained effects.
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
    retained_nodes: int
    hits: int
    misses: int
    evictions: int
    evicted_nodes: int
    oversize_bypasses: int

    @property
    def requests(self) -> int:
        return self.hits + self.misses

    @property
    def hit_rate(self) -> float:
        requests = self.requests
        return 0.0 if requests == 0 else self.hits / requests


@dataclass(slots=True)
class _CacheEntry:
    template: SceneNode
    node_count: int


_CacheKey = tuple[object, object, Rect, CornerRadius, float, int]


class EffectCache:
    """Thread-safe LRU cache for deterministic retained effects.

    Cache identity excludes the logical scene ``key`` so identical effect geometry
    can be reused while callers receive independently keyed node trees. A single
    effect larger than ``max_nodes`` bypasses storage instead of evicting useful
    entries.
    """

    def __init__(self, max_entries: int = 128, *, max_nodes: int = 4096) -> None:
        if max_entries <= 0:
            raise ValueError("EffectCache max_entries must be positive.")
        if max_nodes <= 0:
            raise ValueError("EffectCache max_nodes must be positive.")
        self._max_entries = max_entries
        self._max_nodes = max_nodes
        self._entries: OrderedDict[_CacheKey, _CacheEntry] = OrderedDict()
        self._retained_nodes = 0
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        self._evicted_nodes = 0
        self._oversize_bypasses = 0
        self._lock = RLock()

    @property
    def max_entries(self) -> int:
        return self._max_entries

    @property
    def max_nodes(self) -> int:
        return self._max_nodes

    @property
    def stats(self) -> EffectCacheStats:
        with self._lock:
            return EffectCacheStats(
                entries=len(self._entries),
                retained_nodes=self._retained_nodes,
                hits=self._hits,
                misses=self._misses,
                evictions=self._evictions,
                evicted_nodes=self._evicted_nodes,
                oversize_bypasses=self._oversize_bypasses,
            )

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)

    def clear(self) -> None:
        """Drop cached templates while preserving lifetime telemetry counters."""

        with self._lock:
            self._entries.clear()
            self._retained_nodes = 0

    def invalidate(self, effect: RetainedEffect) -> int:
        """Drop every cached variant for ``effect`` and return the removed count."""

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
                entry = self._entries.pop(cache_key)
                self._retained_nodes -= entry.node_count
            return len(matching)

    def reset_stats(self) -> None:
        """Reset counters without invalidating cached templates."""

        with self._lock:
            self._hits = 0
            self._misses = 0
            self._evictions = 0
            self._evicted_nodes = 0
            self._oversize_bypasses = 0

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
        """Return a cached retained-effect subtree with caller-owned node identity."""

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
            entry = self._entries.pop(cache_key, None)
            if entry is not None:
                self._entries[cache_key] = entry
                self._hits += 1
                return _clone_tree(entry.template, _TEMPLATE_KEY, key)

            self._misses += 1
            template = effect.to_scene_node(
                _TEMPLATE_KEY,
                bounds,
                corner_radius=radius,
                opacity=opacity,
                z_index=z_index,
            )
            node_count = sum(1 for _ in template.walk())
            if node_count > self._max_nodes:
                self._oversize_bypasses += 1
                return _clone_tree(template, _TEMPLATE_KEY, key)

            self._entries[cache_key] = _CacheEntry(template, node_count)
            self._retained_nodes += node_count
            while len(self._entries) > self._max_entries or self._retained_nodes > self._max_nodes:
                _, evicted = self._entries.popitem(last=False)
                self._retained_nodes -= evicted.node_count
                self._evictions += 1
                self._evicted_nodes += evicted.node_count
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
