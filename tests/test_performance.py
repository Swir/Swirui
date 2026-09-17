from __future__ import annotations

import json
from pathlib import Path

import pytest

from swirui.performance import (
    BenchmarkStats,
    PerformanceBudget,
    evaluate_budget,
    load_budgets,
    run_benchmark,
    write_report,
)


class SequenceClock:
    def __init__(self, values: list[int]) -> None:
        self._values = iter(values)

    def __call__(self) -> int:
        return next(self._values)


def test_run_benchmark_records_median_p95_and_throughput() -> None:
    calls = 0

    def workload() -> None:
        nonlocal calls
        calls += 1

    stats = run_benchmark(
        "scene_walk",
        workload,
        warmup=1,
        iterations=4,
        clock=SequenceClock(
            [
                0,
                1_000,
                2_000,
                5_000,
                6_000,
                11_000,
                12_000,
                19_000,
            ]
        ),
    )

    assert calls == 5
    assert stats.iterations == 4
    assert stats.median_us == pytest.approx(4.0)
    assert stats.p95_us == pytest.approx(7.0)
    assert stats.worst_us == pytest.approx(7.0)
    assert stats.total_ms == pytest.approx(0.016)
    assert stats.operations_per_second == pytest.approx(250_000.0)


def test_budget_reports_each_exceeded_guardrail() -> None:
    stats = BenchmarkStats(
        name="retained_scene",
        iterations=10,
        median_us=105.0,
        p95_us=220.0,
        worst_us=450.0,
        total_ms=2.0,
        operations_per_second=5_000.0,
    )
    result = evaluate_budget(
        stats,
        PerformanceBudget(max_median_us=100.0, max_p95_us=200.0, max_worst_us=400.0),
    )

    assert result.passed is False
    assert len(result.failures) == 3
    assert "median" in result.failures[0]
    assert "p95" in result.failures[1]
    assert "worst" in result.failures[2]


def test_load_budgets_and_write_report(tmp_path: Path) -> None:
    budget_path = tmp_path / "budgets.json"
    budget_path.write_text(
        json.dumps(
            {
                "scene_walk": {
                    "max_median_us": 1000,
                    "max_p95_us": 2000,
                    "max_worst_us": 5000,
                }
            }
        ),
        encoding="utf-8",
    )

    budget = load_budgets(budget_path)["scene_walk"]
    stats = BenchmarkStats(
        name="scene_walk",
        iterations=10,
        median_us=100.0,
        p95_us=150.0,
        worst_us=200.0,
        total_ms=1.0,
        operations_per_second=10_000.0,
    )
    result = evaluate_budget(stats, budget)
    report_path = tmp_path / "report.json"
    write_report(report_path, [result])
    report = json.loads(report_path.read_text(encoding="utf-8"))

    assert result.passed is True
    assert report["schema_version"] == 1
    assert report["passed"] is True
    assert report["benchmarks"]["scene_walk"]["stats"]["p95_us"] == 150.0


def test_invalid_budget_limits_are_rejected() -> None:
    with pytest.raises(ValueError, match="max_median_us"):
        PerformanceBudget(max_median_us=0.0, max_p95_us=1.0)

    with pytest.raises(ValueError, match="max_worst_us"):
        PerformanceBudget(max_median_us=1.0, max_p95_us=2.0, max_worst_us=float("inf"))


def test_run_benchmark_rejects_a_non_monotonic_clock() -> None:
    with pytest.raises(ValueError, match="monotonic"):
        run_benchmark(
            "bad-clock",
            lambda: None,
            warmup=0,
            iterations=1,
            clock=SequenceClock([10, 5]),
        )
