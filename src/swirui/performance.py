"""Small, dependency-free performance budget helpers used by SwirUI CI.

The module deliberately keeps benchmark policy separate from framework internals:
callers provide a workload, SwirUI records stable summary statistics, and an
explicit :class:`PerformanceBudget` decides whether the result is acceptable.
These guardrails are intended to catch large retained-runtime regressions in CI;
they are not a substitute for dedicated hardware benchmarking.
"""

from __future__ import annotations

import json
import math
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

Clock = Callable[[], int]
Workload = Callable[[], object]


@dataclass(frozen=True, slots=True)
class BenchmarkStats:
    """Measured timing statistics for one benchmark workload."""

    name: str
    iterations: int
    median_us: float
    p95_us: float
    worst_us: float
    total_ms: float
    operations_per_second: float


@dataclass(frozen=True, slots=True)
class PerformanceBudget:
    """Upper latency limits for a benchmark scenario."""

    max_median_us: float
    max_p95_us: float
    max_worst_us: float | None = None

    def __post_init__(self) -> None:
        for label, value in (
            ("max_median_us", self.max_median_us),
            ("max_p95_us", self.max_p95_us),
        ):
            if not math.isfinite(value) or value <= 0.0:
                raise ValueError(f"{label} must be a positive finite number.")
        if self.max_worst_us is not None and (
            not math.isfinite(self.max_worst_us) or self.max_worst_us <= 0.0
        ):
            raise ValueError("max_worst_us must be a positive finite number when provided.")


@dataclass(frozen=True, slots=True)
class BenchmarkResult:
    """Measured statistics together with budget evaluation details."""

    stats: BenchmarkStats
    budget: PerformanceBudget
    passed: bool
    failures: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""

        return {
            "stats": asdict(self.stats),
            "budget": asdict(self.budget),
            "passed": self.passed,
            "failures": list(self.failures),
        }


def _percentile_nearest_rank(samples: Sequence[int], percentile: float) -> int:
    if not samples:
        raise ValueError("At least one timing sample is required.")
    if not 0.0 < percentile <= 1.0:
        raise ValueError("percentile must be in the range (0, 1].")
    ordered = sorted(samples)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return ordered[index]


def run_benchmark(
    name: str,
    workload: Workload,
    *,
    iterations: int,
    warmup: int = 5,
    clock: Clock = time.perf_counter_ns,
) -> BenchmarkStats:
    """Measure one workload using per-iteration latency samples.

    Warm-up executions are excluded from the statistics. The function records
    each measured invocation independently so percentile latency remains visible
    instead of being hidden inside a single aggregate loop timing.
    """

    if not name.strip():
        raise ValueError("Benchmark name cannot be empty.")
    if iterations <= 0:
        raise ValueError("iterations must be greater than zero.")
    if warmup < 0:
        raise ValueError("warmup cannot be negative.")

    for _ in range(warmup):
        workload()

    samples_ns: list[int] = []
    for _ in range(iterations):
        started = clock()
        workload()
        elapsed = clock() - started
        if elapsed < 0:
            raise ValueError("Benchmark clock must be monotonic.")
        samples_ns.append(elapsed)

    ordered = sorted(samples_ns)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        median_ns = float(ordered[middle])
    else:
        median_ns = (ordered[middle - 1] + ordered[middle]) / 2.0
    p95_ns = float(_percentile_nearest_rank(ordered, 0.95))
    worst_ns = float(ordered[-1])
    total_ns = float(sum(ordered))
    operations_per_second = (
        iterations * 1_000_000_000.0 / total_ns if total_ns > 0.0 else math.inf
    )

    return BenchmarkStats(
        name=name,
        iterations=iterations,
        median_us=median_ns / 1_000.0,
        p95_us=p95_ns / 1_000.0,
        worst_us=worst_ns / 1_000.0,
        total_ms=total_ns / 1_000_000.0,
        operations_per_second=operations_per_second,
    )


def evaluate_budget(stats: BenchmarkStats, budget: PerformanceBudget) -> BenchmarkResult:
    """Compare measured statistics with explicit latency guardrails."""

    failures: list[str] = []
    if stats.median_us > budget.max_median_us:
        failures.append(
            f"median {stats.median_us:.1f} us exceeds budget {budget.max_median_us:.1f} us"
        )
    if stats.p95_us > budget.max_p95_us:
        failures.append(f"p95 {stats.p95_us:.1f} us exceeds budget {budget.max_p95_us:.1f} us")
    if budget.max_worst_us is not None and stats.worst_us > budget.max_worst_us:
        failures.append(
            f"worst {stats.worst_us:.1f} us exceeds budget {budget.max_worst_us:.1f} us"
        )
    return BenchmarkResult(
        stats=stats,
        budget=budget,
        passed=not failures,
        failures=tuple(failures),
    )


def load_budgets(path: str | Path) -> dict[str, PerformanceBudget]:
    """Load named performance budgets from a JSON object."""

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Performance budget file must contain a JSON object.")

    budgets: dict[str, PerformanceBudget] = {}
    for name, raw_budget in payload.items():
        if not isinstance(name, str) or not isinstance(raw_budget, Mapping):
            raise ValueError("Each performance budget entry must be a named JSON object.")
        median = raw_budget.get("max_median_us")
        p95 = raw_budget.get("max_p95_us")
        worst = raw_budget.get("max_worst_us")
        if not isinstance(median, (int, float)) or not isinstance(p95, (int, float)):
            raise ValueError(f"Budget {name!r} requires numeric median and p95 limits.")
        if worst is not None and not isinstance(worst, (int, float)):
            raise ValueError(f"Budget {name!r} max_worst_us must be numeric when provided.")
        budgets[name] = PerformanceBudget(
            max_median_us=float(median),
            max_p95_us=float(p95),
            max_worst_us=float(worst) if worst is not None else None,
        )
    return budgets


def write_report(path: str | Path, results: Sequence[BenchmarkResult]) -> None:
    """Write benchmark results as stable, human-readable JSON."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "passed": all(result.passed for result in results),
        "benchmarks": {result.stats.name: result.to_dict() for result in results},
    }
    destination.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
