"""Retained-runtime performance guardrails for CI.

This suite intentionally benchmarks CPU-side retained-scene work only. GPU driver
performance is validated by native smoke tests but is not compared across shared
CI hardware. The budgets here are broad guardrails against accidental algorithmic
regressions, not public performance claims.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from pathlib import Path

from swirui import Window
from swirui.performance import (
    BenchmarkResult,
    evaluate_budget,
    load_budgets,
    run_benchmark,
    write_report,
)
from swirui.rendering import (
    BackdropBlur,
    Color,
    CornerRadius,
    EffectCache,
    Glow,
    Point,
    Rect,
    Reflection,
    Scene,
    SceneNode,
    SceneNodeKind,
    WgpuRenderer,
)

BenchmarkWorkload = Callable[[], object]


def _build_grid_scene(columns: int = 32, rows: int = 32) -> Scene:
    cell = 24.0
    root = SceneNode(
        key="root",
        kind=SceneNodeKind.GROUP,
        bounds=Rect(0.0, 0.0, columns * cell, rows * cell),
        clip_to_bounds=True,
    )
    fill = Color.from_hex("#3388CC")
    nodes = [
        SceneNode(
            key=f"cell-{row}-{column}",
            kind=SceneNodeKind.RECTANGLE,
            bounds=Rect(column * cell, row * cell, cell - 1.0, cell - 1.0),
            fill=fill,
            z_index=(row + column) % 4,
        )
        for row in range(rows)
        for column in range(columns)
    ]
    root.add(*nodes)
    return Scene(width=columns * cell, height=rows * cell, root=root)


def _scene_walk_workload(scene: Scene) -> BenchmarkWorkload:
    expected_nodes = 1025

    def workload() -> object:
        nodes = tuple(scene.walk_composited())
        if len(nodes) != expected_nodes:
            raise RuntimeError("Retained scene walk returned an unexpected node count.")
        return nodes

    return workload


def _hit_test_workload(scene: Scene) -> BenchmarkWorkload:
    points = tuple(
        Point(column * 24.0 + 12.0, row * 24.0 + 12.0)
        for row in range(0, 32, 4)
        for column in range(0, 32, 4)
    )

    def workload() -> object:
        keys = tuple(
            node.key if (node := scene.hit_test(point)) is not None else None for point in points
        )
        if any(key is None for key in keys):
            raise RuntimeError("Retained scene hit testing missed a populated grid cell.")
        return keys

    return workload


def _reflection_build_workload() -> BenchmarkWorkload:
    reflection = Reflection(
        color=Color(0.72, 0.9, 1.0, 0.28),
        angle_degrees=24.0,
        position=0.42,
        width=0.18,
        steps=96,
    )
    bounds = Rect(120.0, 80.0, 640.0, 360.0)

    def workload() -> object:
        node = reflection.to_scene_node("benchmark-reflection", bounds)
        if not node.children:
            raise RuntimeError("Reflection tessellation produced no retained path bands.")
        return node

    return workload


def _cached_effect_build_workload() -> BenchmarkWorkload:
    """Exercise the hot path used by unchanged high-quality retained effects."""

    cache = EffectCache(max_entries=4)
    glow = Glow(
        color=Color(0.0, 0.7, 1.0, 0.55),
        blur_radius=42.0,
        spread=3.0,
        steps=64,
    )
    bounds = Rect(120.0, 80.0, 640.0, 360.0)
    radius = CornerRadius.uniform(32.0)
    cache.render(glow, "warm", bounds, corner_radius=radius)
    sequence = 0

    def workload() -> object:
        nonlocal sequence
        sequence += 1
        node = cache.render(
            glow,
            f"benchmark-cached-glow-{sequence}",
            bounds,
            corner_radius=radius,
        )
        if len(node.children) != 64:
            raise RuntimeError("Cached retained effect returned an unexpected layer count.")
        return node

    return workload


def _cached_backdrop_payload_workload() -> BenchmarkWorkload:
    """Guard the unchanged-scene hot path for backdrop/material preparation."""

    width = 1024.0
    height = 640.0
    root = SceneNode("root", SceneNodeKind.GROUP, Rect(0.0, 0.0, width, height))
    fill = Color.from_hex("#163A66")
    cells = [
        SceneNode(
            key=f"backdrop-cell-{index}",
            kind=SceneNodeKind.RECTANGLE,
            bounds=Rect(
                float((index % 16) * 64),
                float((index // 16) * 36),
                60.0,
                32.0,
            ),
            fill=fill,
        )
        for index in range(256)
    ]
    glass = BackdropBlur(radius=24.0).to_scene_node(
        "benchmark-glass",
        Rect(192.0, 128.0, 640.0, 360.0),
        corner_radius=CornerRadius.uniform(28.0),
        z_index=2,
    )
    glass.add(
        SceneNode(
            "benchmark-glass-tint",
            SceneNodeKind.RECTANGLE,
            Rect(192.0, 128.0, 640.0, 360.0),
            fill=Color(0.15, 0.55, 1.0, 0.16),
        )
    )
    root.add(*cells, glass)
    window = Window(width=int(width), height=int(height))
    window.set_scene(Scene(width, height, root))
    renderer = WgpuRenderer(native_module=object())
    expected = renderer._backdrop_payload(window)
    if expected is None:
        raise RuntimeError("Backdrop benchmark scene produced no segmented payload.")

    def workload() -> object:
        payload = renderer._backdrop_payload(window)
        if payload is not expected:
            raise RuntimeError("Unchanged backdrop scene missed the prepared-payload cache.")
        return payload

    return workload


def _run_suite(budget_path: Path) -> list[BenchmarkResult]:
    scene = _build_grid_scene()
    budgets = load_budgets(budget_path)
    scenarios: tuple[tuple[str, BenchmarkWorkload, int, int], ...] = (
        ("retained_scene_walk_1024", _scene_walk_workload(scene), 60, 10),
        ("scene_hit_testing_1024", _hit_test_workload(scene), 40, 8),
        ("reflection_tessellation_96", _reflection_build_workload(), 40, 8),
        ("cached_effect_clone_64", _cached_effect_build_workload(), 80, 12),
        ("cached_backdrop_payload_256", _cached_backdrop_payload_workload(), 100, 16),
    )

    results: list[BenchmarkResult] = []
    for name, workload, iterations, warmup in scenarios:
        try:
            budget = budgets[name]
        except KeyError as exc:
            raise ValueError(f"Missing performance budget for {name!r}.") from exc
        stats = run_benchmark(name, workload, iterations=iterations, warmup=warmup)
        results.append(evaluate_budget(stats, budget))
    return results


def _print_results(results: list[BenchmarkResult]) -> None:
    print("SwirUI retained-runtime performance guardrails")
    print("scenario                     median us    p95 us    worst us    result")
    for result in results:
        stats = result.stats
        status = "PASS" if result.passed else "FAIL"
        print(
            f"{stats.name:<28} {stats.median_us:>10.1f} {stats.p95_us:>10.1f} "
            f"{stats.worst_us:>11.1f}    {status}"
        )
        for failure in result.failures:
            print(f"  - {failure}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--budgets",
        type=Path,
        default=Path(__file__).with_name("performance_budgets.json"),
        help="JSON file containing named latency budgets.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("performance-report.json"),
        help="Destination for the machine-readable benchmark report.",
    )
    args = parser.parse_args()

    results = _run_suite(args.budgets)
    _print_results(results)
    write_report(args.report, results)
    return 0 if all(result.passed for result in results) else 1


if __name__ == "__main__":
    sys.exit(main())
