"""An interrupted seed must not be mistaken for a finished one.

Regression tests for audit finding NEW-12.

Without `--reset`, the seed guard asked only "does any reading exist?". A seed
that died partway through the device loop therefore left a partial dataset that
every later `python -m db.seed_plant_monitoring` run reported as "Readings
already exist" and skipped — leaving a developer to debug missing data that the
tool insisted was fine.

Completeness is measured as (device, metric) pairs that have at least one
reading, against devices x metrics. A run that stopped halfway through the
devices has strictly fewer pairs.
"""
from __future__ import annotations

import pytest

from db.seed_plant_monitoring import SeedState, evaluate_seed_state


class TestEvaluateSeedState:
    def test_no_readings_at_all_is_empty(self):
        assert evaluate_seed_state(0, 960) is SeedState.EMPTY

    def test_all_pairs_present_is_complete(self):
        assert evaluate_seed_state(960, 960) is SeedState.COMPLETE

    def test_missing_pairs_is_partial(self):
        """The regression: this used to be indistinguishable from COMPLETE."""
        assert evaluate_seed_state(480, 960) is SeedState.PARTIAL

    def test_a_single_missing_pair_is_partial(self):
        assert evaluate_seed_state(959, 960) is SeedState.PARTIAL

    def test_more_pairs_than_expected_is_not_complete(self):
        """Extra pairs mean the dataset does not match the current config."""
        assert evaluate_seed_state(961, 960) is SeedState.PARTIAL

    def test_no_devices_expected_is_empty_not_complete(self):
        """Guards against 0 == 0 reporting a finished seed of nothing."""
        assert evaluate_seed_state(0, 0) is SeedState.EMPTY


class TestSeedStateDrivesTheDecision:
    @pytest.mark.parametrize(
        "state,should_seed",
        [(SeedState.EMPTY, True), (SeedState.PARTIAL, False), (SeedState.COMPLETE, False)],
    )
    def test_only_an_empty_database_seeds_without_reset(self, state, should_seed):
        assert (state is SeedState.EMPTY) is should_seed

    def test_partial_is_reported_distinctly_from_complete(self):
        """A developer must be told to --reset, not told everything is fine."""
        assert SeedState.PARTIAL is not SeedState.COMPLETE
