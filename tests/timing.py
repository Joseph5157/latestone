"""Timing utilities for performance guardrails."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from time import perf_counter


@dataclass
class TimingResult:
    elapsed_ms: float = 0.0
    row_count: int = 0


@contextmanager
def measure_time() -> TimingResult:
    """Context manager that records elapsed time and row count."""
    start = perf_counter()
    result = TimingResult()
    try:
        yield result
    finally:
        result.elapsed_ms = (perf_counter() - start) * 1000


def assert_timing(result: TimingResult, max_ms: float, min_rows: int = 0) -> None:
    """Assert that a query completed within the time budget and returned enough rows."""
    assert result.elapsed_ms <= max_ms, f"Query took {result.elapsed_ms:.1f}ms, budget {max_ms}ms"
    assert result.row_count >= min_rows, f"Query returned {result.row_count} rows, expected >= {min_rows}"