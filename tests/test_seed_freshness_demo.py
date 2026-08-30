"""The freshness demo seed (CC-1 Phase 10).

Two things are under test and only two: that the fixture actually covers the
freshness states the Command Center panels need to be seen working, and that
a seed which DELETES cannot do so by accident. Whether the chosen RTLs are
the nicest ones to demo is a judgement, not an assertion.

No database here — this asserts over the declared plan and the module's
source, the same shape as tests/test_seed_events_demo.py.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

from config.metrics import METRIC_KEYS
from db import seed_freshness_demo as seed

SOURCE = pathlib.Path(seed.__file__).read_text(encoding="utf-8")


class TestCoverage:
    """The fixture must exercise every branch the panels can render."""

    def test_it_covers_fresh_stale_and_no_data(self):
        outcomes = " ".join(t.outcome for t in seed.TARGETS)
        assert "FRESH" in outcomes
        assert "STALE" in outcomes
        assert "NO_DATA" in outcomes

    def test_there_is_an_untouched_control(self):
        """If everything is shaped, a global breakage looks like the seed."""
        controls = [
            t for t in seed.TARGETS
            if not t.metrics and t.keep_older_than is None
        ]
        assert len(controls) == 1
        assert "FRESH" in controls[0].outcome

    def test_it_includes_a_mixed_metric_no_data_rtl(self):
        """ADR-002: ONE silent metric makes the RTL No Data, with seven
        healthy feeds beside it. A whole-device blackout would not test that."""
        mixed = [
            t for t in seed.TARGETS
            if "NO_DATA" in t.outcome and t.metrics and t.keep_older_than is None
        ]
        assert len(mixed) == 1
        assert len(mixed[0].metrics) == 1

    def test_it_includes_a_mixed_metric_stale_rtl(self):
        """ADR-009 D3 — the target a simpler fixture would have missed.

        Seven metrics stay fresh, so `device_last_updated` reads minutes old
        on an RTL that is genuinely Stale. Without this row the honest
        oldest-metric path is never seen outside the test suite.
        """
        mixed = [
            t for t in seed.TARGETS
            if "STALE" in t.outcome and t.metrics and t.keep_older_than
        ]
        assert len(mixed) == 1
        assert len(mixed[0].metrics) == 1

    def test_the_two_stale_rtls_have_different_ages(self):
        """So the ranking has something to order, and the screen shows it."""
        ages = {
            t.keep_older_than for t in seed.TARGETS
            if "STALE" in t.outcome and t.keep_older_than
        }
        assert len(ages) == 2

    def test_every_named_metric_is_a_real_metric(self):
        """A typo would delete nothing and still report success."""
        for target in seed.TARGETS:
            for metric in target.metrics:
                assert metric in METRIC_KEYS

    def test_targets_are_distinct_rtls(self):
        ids = [t.device_id for t in seed.TARGETS]
        assert len(ids) == len(set(ids))

    def test_the_reserved_identifier_is_left_alone(self):
        """plant-01-t1-d1 (aa12/29017) is the worked example throughout the
        docs and tests (AGENTS.md scope). Breaking its data would make every
        reference to it misleading."""
        assert all(t.device_id != "plant-01-t1-d1" for t in seed.TARGETS)


class TestStaleTargetsClearTheThreshold:
    def test_the_plain_stale_margin_is_past_the_threshold(self):
        from config.settings import monitoring

        threshold_minutes = monitoring.stale_after_minutes
        assert seed.STALE_MARGIN.total_seconds() / 60 > threshold_minutes

    def test_the_lagging_metric_is_older_still(self):
        """Ordered on purpose: two stale RTLs that rank identically would
        show nothing about the ranking."""
        assert seed.LAGGING_AGE > seed.STALE_MARGIN


class TestItCannotDeleteByAccident:
    """It removes rows, so the guards are the feature."""

    def test_apply_is_opt_in(self):
        parser_defaults = [
            node
            for node in ast.walk(ast.parse(SOURCE))
            if isinstance(node, ast.Constant) and node.value == "--apply"
        ]
        assert parser_defaults, "--apply flag not found"
        assert "action=\"store_true\"" in SOURCE

    def test_the_dry_run_path_never_deletes(self):
        """The DELETE must be unreachable without --apply."""
        tree = ast.parse(SOURCE)
        main = next(
            n for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) and n.name == "main"
        )
        calls = [
            n.func.id
            for n in ast.walk(main)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        ]
        assert "_apply" in calls
        # _apply is called only after the not-args.apply early return above it.
        source_lines = SOURCE.splitlines()
        dry_run_return = next(
            i for i, line in enumerate(source_lines) if "Dry run." in line
        )
        apply_call = next(
            i for i, line in enumerate(source_lines) if "removed = _apply(" in line
        )
        assert dry_run_return < apply_call

    def test_it_only_ever_touches_readings(self):
        """Never a plant, transformer, device or event — those are not
        recoverable by re-running the monitoring seed."""
        deletes = [
            line for line in SOURCE.splitlines() if "DELETE FROM" in line
        ]
        assert deletes
        assert all(".readings" in line for line in deletes)

    def test_it_is_honest_that_there_is_no_one_command_undo(self):
        """`_reset_data` deletes `devices`, which device_events,
        user_device_assignments, rtl_active_state and rtl_programming_requests
        all reference — so "just re-run the seed" is not true, and this
        module must not say it is."""
        assert "NO ONE-COMMAND UNDO" in SOURCE
        assert "one-way local change" in SOURCE

    def test_it_refuses_when_the_hierarchy_is_missing(self):
        assert "Refused:" in SOURCE
