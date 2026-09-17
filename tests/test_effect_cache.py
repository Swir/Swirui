from __future__ import annotations

from swirui.rendering import (
    AdaptiveLighting,
    Bloom,
    Color,
    CornerRadius,
    EffectCache,
    Glow,
    Rect,
)


def test_effect_cache_reuses_geometry_across_logical_scene_keys() -> None:
    cache = EffectCache(max_entries=4)
    effect = Glow(
        color=Color(0.0, 0.7, 1.0, 0.5),
        blur_radius=20.0,
        spread=2.0,
        steps=8,
    )
    bounds = Rect(20.0, 30.0, 180.0, 96.0)
    radius = CornerRadius.uniform(18.0)

    first = cache.render(effect, "first", bounds, corner_radius=radius, z_index=-1)
    second = cache.render(effect, "second", bounds, corner_radius=radius, z_index=-1)

    assert first is not second
    assert first.key == "first"
    assert second.key == "second"
    assert first.children[0].key.startswith("first:")
    assert second.children[0].key.startswith("second:")
    assert [child.bounds for child in first.children] == [child.bounds for child in second.children]
    assert cache.stats.entries == 1
    assert cache.stats.hits == 1
    assert cache.stats.misses == 1
    assert cache.stats.hit_rate == 0.5


def test_effect_cache_returns_mutation_isolated_scene_trees() -> None:
    cache = EffectCache()
    effect = Glow(steps=6)
    bounds = Rect(0.0, 0.0, 120.0, 64.0)

    first = cache.render(effect, "first", bounds)
    original_child_count = len(first.children)
    first.children.clear()

    second = cache.render(effect, "second", bounds)

    assert original_child_count > 0
    assert len(second.children) == original_child_count
    assert cache.stats.hits == 1


def test_effect_cache_identity_includes_effect_geometry_opacity_and_z_index() -> None:
    cache = EffectCache()
    bounds = Rect(10.0, 10.0, 100.0, 50.0)

    cache.render(Glow(blur_radius=10.0), "a", bounds)
    cache.render(Glow(blur_radius=12.0), "b", bounds)
    cache.render(Glow(blur_radius=10.0), "c", Rect(11.0, 10.0, 100.0, 50.0))
    cache.render(Glow(blur_radius=10.0), "d", bounds, opacity=0.75)
    cache.render(Glow(blur_radius=10.0), "e", bounds, z_index=2)

    assert cache.stats.entries == 5
    assert cache.stats.hits == 0
    assert cache.stats.misses == 5


def test_effect_cache_uses_lru_eviction() -> None:
    cache = EffectCache(max_entries=2)
    bounds = Rect(0.0, 0.0, 80.0, 40.0)
    first = Glow(blur_radius=8.0)
    second = Glow(blur_radius=12.0)
    third = Glow(blur_radius=16.0)

    cache.render(first, "first", bounds)
    cache.render(second, "second", bounds)
    cache.render(first, "first-again", bounds)
    cache.render(third, "third", bounds)
    cache.render(second, "second-again", bounds)

    stats = cache.stats
    assert stats.entries == 2
    assert stats.hits == 1
    assert stats.misses == 4
    assert stats.evictions == 2


def test_effect_cache_supports_composite_visual_engine_effects() -> None:
    cache = EffectCache()
    bounds = Rect(40.0, 60.0, 220.0, 120.0)
    radius = CornerRadius.uniform(24.0)
    bloom = Bloom(steps=10)
    lighting = AdaptiveLighting(steps=10)

    bloom_first = cache.render(bloom, "bloom:first", bounds, corner_radius=radius)
    bloom_second = cache.render(bloom, "bloom:second", bounds, corner_radius=radius)
    light_first = cache.render(lighting, "light:first", bounds, corner_radius=radius)
    light_second = cache.render(lighting, "light:second", bounds, corner_radius=radius)

    assert len(tuple(bloom_first.walk())) == len(tuple(bloom_second.walk()))
    assert len(tuple(light_first.walk())) == len(tuple(light_second.walk()))
    assert cache.stats.entries == 2
    assert cache.stats.hits == 2
    assert cache.stats.misses == 2


def test_effect_cache_clear_and_reset_stats_are_independent() -> None:
    cache = EffectCache()
    effect = Glow(steps=4)
    bounds = Rect(0.0, 0.0, 64.0, 64.0)

    cache.render(effect, "one", bounds)
    cache.render(effect, "two", bounds)
    cache.clear()

    assert len(cache) == 0
    assert cache.stats.hits == 1
    assert cache.stats.misses == 1

    cache.reset_stats()
    assert cache.stats.entries == 0
    assert cache.stats.requests == 0
    assert cache.stats.evictions == 0


def test_effect_cache_rejects_non_positive_capacity_and_empty_keys() -> None:
    try:
        EffectCache(max_entries=0)
    except ValueError as exc:
        assert "positive" in str(exc)
    else:  # pragma: no cover - defensive assertion path.
        raise AssertionError("Expected invalid cache capacity to fail.")

    cache = EffectCache()
    try:
        cache.render(Glow(), "", Rect(0.0, 0.0, 32.0, 32.0))
    except ValueError as exc:
        assert "keys" in str(exc)
    else:  # pragma: no cover - defensive assertion path.
        raise AssertionError("Expected an empty cached-effect key to fail.")
