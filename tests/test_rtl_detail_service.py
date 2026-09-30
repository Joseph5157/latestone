"""RTL-UID-DETAIL-01 — the factual detail model for one registered client RTL.

Every fact comes from the read-only client SQL Server and nothing is
synthesised: no PostgreSQL fallback, no Online/Offline verdict, none of the
seven unsupported metrics, no fuzzy hierarchy match, and no chosen value when
the source conflicts about the latest reading.

The fake repository below returns exactly what the audited source shape
returns, so these tests pin behaviour rather than a mock's convenience.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from repositories.rtl_temperature_repository import (
    RTLTemperatureReading,
    RTLTemperatureRepositoryError,
    RTLTransformerHierarchy,
    RTLTransformerMapping,
)
from services import rtl_detail_service as detail
from services.rtl_fleet_service import HierarchyState, TemperatureState

REGISTERED_MAPPED = 29042  # registered, mapped, hierarchy, telemetry
REGISTERED_UNMAPPED = 29006  # registered, no trfr_list row, telemetry
REGISTERED_NO_TELEMETRY = 29999  # registered, no master_temperature row
REGISTERED_MAPPED_NO_HIERARCHY = 29500  # registered + mapped, hierarchy blank
REGISTERED_AMBIGUOUS = 29777  # conflicting values at the latest timestamp
TELEMETRY_ONLY = 41000  # has telemetry, NOT in device_list
UNKNOWN_UID = 12345  # in no source table at all

LAST = datetime(2022, 4, 13, 5, 54)


class FakeRepo:
    """Records every call so "was the source read at all?" is assertable."""

    def __init__(self, *, unavailable: bool = False):
        self.unavailable = unavailable
        self.calls: list[str] = []

    def _guard(self, name: str):
        self.calls.append(name)
        if self.unavailable:
            raise RTLTemperatureRepositoryError("RTL temperature source is unavailable")

    def get_registered_device_uids(self):
        self._guard("registered")
        return [
            REGISTERED_UNMAPPED,
            REGISTERED_MAPPED,
            REGISTERED_MAPPED_NO_HIERARCHY,
            REGISTERED_AMBIGUOUS,
            REGISTERED_NO_TELEMETRY,
        ]

    def get_transformer_mappings(self):
        self._guard("mappings")
        return [
            RTLTransformerMapping(REGISTERED_MAPPED, "AA12"),
            RTLTransformerMapping(REGISTERED_MAPPED_NO_HIERARCHY, "ZZ99"),
            RTLTransformerMapping(REGISTERED_AMBIGUOUS, "BB34"),
        ]

    def get_transformer_hierarchy(self):
        self._guard("hierarchy")
        return [
            RTLTransformerHierarchy(
                REGISTERED_MAPPED, "AA12", "Distribution", "North", "Sector 4", "CNC 2", "Feeder 7"
            ),
            # Mapped to ZZ99 in trfr_list but the view row names a DIFFERENT
            # transformer: an exact-match miss, never a fuzzy fallback.
            RTLTransformerHierarchy(
                REGISTERED_MAPPED_NO_HIERARCHY, "ZZ98", "Distribution", "South", None, None, None
            ),
            # Mapped and the code matches, but every level is blank.
            RTLTransformerHierarchy(REGISTERED_AMBIGUOUS, "BB34", None, None, None, None, None),
        ]

    def get_latest_temperatures(self, device_uids):
        self._guard("latest")
        from repositories.rtl_temperature_repository import RTLLatestTemperature

        table = {
            REGISTERED_UNMAPPED: RTLLatestTemperature(
                REGISTERED_UNMAPPED, LAST, Decimal("18.0"), 1, (Decimal("18.0"),)
            ),
            REGISTERED_MAPPED: RTLLatestTemperature(
                REGISTERED_MAPPED, LAST, Decimal("35.5"), 1, (Decimal("35.5"),)
            ),
            REGISTERED_MAPPED_NO_HIERARCHY: RTLLatestTemperature(
                REGISTERED_MAPPED_NO_HIERARCHY, LAST, Decimal("22.0"), 1, (Decimal("22.0"),)
            ),
            REGISTERED_AMBIGUOUS: RTLLatestTemperature(
                REGISTERED_AMBIGUOUS, LAST, None, 2, (Decimal("21.0"), Decimal("48.0"))
            ),
            TELEMETRY_ONLY: RTLLatestTemperature(
                TELEMETRY_ONLY, LAST, Decimal("30.0"), 1, (Decimal("30.0"),)
            ),
        }
        return {uid: table[uid] for uid in device_uids if uid in table}

    def get_temperature_range(self, device_uid, start_time, end_time):
        self._guard("range")
        if start_time > end_time:
            raise ValueError("start_time must be less than or equal to end_time")
        if device_uid != REGISTERED_MAPPED:
            return []
        every = [
            RTLTemperatureReading(device_uid, LAST - timedelta(hours=h), Decimal(20 + h))
            for h in range(0, 40)
        ]
        return sorted(
            [r for r in every if start_time <= r.reading_time <= end_time],
            key=lambda r: r.reading_time,
        )


def get(uid, repo=None):
    return detail.get_rtl_detail(uid, repo if repo is not None else FakeRepo())


# ---------------------------------------------------------------------------
# Registered-UID validation (gate section 13)
# ---------------------------------------------------------------------------


class TestRegistrationIsTheGate:
    def test_a_registered_uid_with_telemetry_loads(self):
        result = get(REGISTERED_MAPPED)
        assert result.status is detail.DetailStatus.DATA
        assert result.rtl.device_uid == REGISTERED_MAPPED

    def test_a_registered_uid_without_telemetry_loads(self):
        """Registration, not telemetry, decides whether the page exists."""
        result = get(REGISTERED_NO_TELEMETRY)
        assert result.status is detail.DetailStatus.DATA
        assert result.rtl.temperature_state is TemperatureState.NO_DATA

    def test_a_telemetry_only_uid_is_not_registered(self):
        """81 telemetry UIDs are absent from `device_list`. Absence is not
        retirement, but it is also not registration — the route must not
        auto-register them."""
        assert get(TELEMETRY_ONLY).status is detail.DetailStatus.NOT_REGISTERED

    def test_a_telemetry_only_uid_leaks_no_source_facts(self):
        result = get(TELEMETRY_ONLY)
        assert result.rtl is None

    def test_a_completely_unknown_uid_is_not_registered(self):
        assert get(UNKNOWN_UID).status is detail.DetailStatus.NOT_REGISTERED

    def test_an_unregistered_uid_never_reads_telemetry(self):
        """Registration is checked first, so a probe for an unregistered UID
        performs no temperature read at all."""
        repo = FakeRepo()
        get(TELEMETRY_ONLY, repo)
        assert "latest" not in repo.calls
        assert "range" not in repo.calls

    @pytest.mark.parametrize("bad", ["29042", None, 0, -5, True, 1.5, 2**31])
    def test_a_non_uid_is_refused_without_touching_the_source(self, bad):
        repo = FakeRepo()
        assert get(bad, repo).status is detail.DetailStatus.NOT_REGISTERED
        assert repo.calls == []

    def test_an_unavailable_source_is_not_reported_as_unregistered(self):
        """"The database is down" and "this RTL does not exist" are different
        facts; folding them together would tell an operator an RTL was
        deregistered because a network link failed."""
        result = get(REGISTERED_MAPPED, FakeRepo(unavailable=True))
        assert result.status is detail.DetailStatus.UNAVAILABLE
        assert result.rtl is None


# ---------------------------------------------------------------------------
# Latest temperature (gate section 8)
# ---------------------------------------------------------------------------


class TestLatestTemperature:
    def test_a_single_value_is_used_as_received(self):
        rtl = get(REGISTERED_MAPPED).rtl
        assert rtl.temperature_state is TemperatureState.VALUE
        assert rtl.temperature == Decimal("35.5")
        assert rtl.last_reported == LAST

    def test_conflicting_values_stay_ambiguous(self):
        rtl = get(REGISTERED_AMBIGUOUS).rtl
        assert rtl.temperature_state is TemperatureState.AMBIGUOUS
        assert rtl.temperature is None
        assert rtl.ambiguous_values == (Decimal("21.0"), Decimal("48.0"))

    def test_no_value_is_chosen_from_a_conflict(self):
        """Not highest, not lowest, not the average, not an arbitrary row."""
        rtl = get(REGISTERED_AMBIGUOUS).rtl
        for forbidden in (Decimal("48.0"), Decimal("21.0"), Decimal("34.5")):
            assert rtl.temperature != forbidden

    def test_an_rtl_with_no_reading_reports_no_data(self):
        rtl = get(REGISTERED_NO_TELEMETRY).rtl
        assert rtl.temperature_state is TemperatureState.NO_DATA
        assert rtl.temperature is None
        assert rtl.last_reported is None

    def test_the_timestamp_is_the_naive_source_clock_value(self):
        """SAST source values are shown unconverted (ADR-029). A tzinfo here
        would mean something converted them."""
        assert get(REGISTERED_MAPPED).rtl.last_reported.tzinfo is None

    def test_ambiguity_semantics_match_the_fleet_page(self):
        """One rule, reused — not a second implementation that can drift."""
        from services import rtl_fleet_service

        repo = FakeRepo()
        fleet = rtl_fleet_service.get_real_fleet(repo)
        row = next(r for r in fleet.rows if r.device_uid == REGISTERED_AMBIGUOUS)
        rtl = get(REGISTERED_AMBIGUOUS).rtl
        assert rtl.temperature_state is row.temperature_state
        assert rtl.ambiguous_values == row.ambiguous_values
        assert rtl.last_reported == row.last_reported


# ---------------------------------------------------------------------------
# Mapping and hierarchy (gate section 9)
# ---------------------------------------------------------------------------


class TestMappingAndHierarchy:
    def test_a_mapped_rtl_with_hierarchy_carries_the_full_context(self):
        rtl = get(REGISTERED_MAPPED).rtl
        assert rtl.transformer_codes == ("AA12",)
        assert rtl.hierarchy_state is HierarchyState.AVAILABLE
        assert (rtl.hierarchy.zone, rtl.hierarchy.sector) == ("North", "Sector 4")
        assert (rtl.hierarchy.cnc, rtl.hierarchy.feeder) == ("CNC 2", "Feeder 7")

    def test_hierarchy_requires_an_exact_transformer_code_match(self):
        """`trfr_list` says ZZ99, the view row says ZZ98. A near match is a
        miss — the hierarchy is unavailable, never fuzzily attached."""
        rtl = get(REGISTERED_MAPPED_NO_HIERARCHY).rtl
        assert rtl.transformer_codes == ("ZZ99",)
        assert rtl.hierarchy_state is HierarchyState.UNAVAILABLE
        assert rtl.hierarchy is None

    def test_a_mapped_rtl_whose_hierarchy_row_is_blank_is_unavailable(self):
        rtl = get(REGISTERED_AMBIGUOUS).rtl
        assert rtl.transformer_codes == ("BB34",)
        assert rtl.hierarchy_state is HierarchyState.UNAVAILABLE

    def test_an_unmapped_rtl_reports_not_mapped(self):
        rtl = get(REGISTERED_UNMAPPED).rtl
        assert rtl.transformer_codes == ()
        assert rtl.has_transformer_mapping is False
        assert rtl.hierarchy_state is HierarchyState.NOT_MAPPED
        assert rtl.hierarchy is None

    def test_hierarchy_states_match_the_fleet_page_for_every_uid(self):
        from services import rtl_fleet_service

        fleet = rtl_fleet_service.get_real_fleet(FakeRepo())
        for row in fleet.rows:
            rtl = get(row.device_uid).rtl
            assert rtl.hierarchy_state is row.hierarchy_state, row.device_uid
            assert rtl.transformer_codes == row.transformer_codes, row.device_uid


# ---------------------------------------------------------------------------
# Temperature history (gate section 7)
# ---------------------------------------------------------------------------


class TestTemperatureHistory:
    def test_the_windows_are_the_established_three(self):
        assert [w.key for w in detail.HISTORY_WINDOWS] == ["24h", "7d", "30d"]

    def test_a_window_is_anchored_to_the_rtls_own_last_reading(self):
        """ADR-030. Client telemetry ends well before wall-clock now and many
        RTLs last reported years ago, so a window measured from "now" is
        empty for the whole fleet and says nothing about the RTL. The range
        is stated on screen, and both ends are source-clock values, so no
        timezone conversion is involved."""
        result = detail.get_temperature_history(REGISTERED_MAPPED, "24h", FakeRepo())
        assert result.status is detail.HistoryStatus.DATA
        assert result.window_end == LAST
        assert result.window_start == LAST - timedelta(hours=24)

    @pytest.mark.parametrize("key,delta", [("24h", timedelta(hours=24)),
                                           ("7d", timedelta(days=7)),
                                           ("30d", timedelta(days=30))])
    def test_each_window_spans_its_own_length(self, key, delta):
        result = detail.get_temperature_history(REGISTERED_MAPPED, key, FakeRepo())
        assert result.window_end - result.window_start == delta

    def test_readings_come_back_in_ascending_source_time(self):
        result = detail.get_temperature_history(REGISTERED_MAPPED, "7d", FakeRepo())
        times = [r.reading_time for r in result.readings]
        assert times == sorted(times)
        assert len(times) == 40  # every fake row falls inside 7 days

    def test_a_shorter_window_returns_fewer_readings(self):
        day = detail.get_temperature_history(REGISTERED_MAPPED, "24h", FakeRepo())
        week = detail.get_temperature_history(REGISTERED_MAPPED, "7d", FakeRepo())
        assert len(day.readings) < len(week.readings)
        assert all(r.reading_time >= day.window_start for r in day.readings)

    def test_a_period_with_no_readings_is_an_explicit_no_data_state(self):
        """Never a silent fall back to synthetic readings."""
        result = detail.get_temperature_history(REGISTERED_UNMAPPED, "24h", FakeRepo())
        assert result.status is detail.HistoryStatus.NO_DATA
        assert result.readings == ()

    def test_an_rtl_with_no_latest_reading_has_no_window_to_anchor(self):
        result = detail.get_temperature_history(REGISTERED_NO_TELEMETRY, "24h", FakeRepo())
        assert result.status is detail.HistoryStatus.NO_DATA
        assert result.window_start is None and result.window_end is None

    def test_history_is_refused_for_an_unregistered_uid(self):
        """The same registration gate as the page itself: a callback must not
        become a second, unguarded way to read the source."""
        repo = FakeRepo()
        result = detail.get_temperature_history(TELEMETRY_ONLY, "24h", repo)
        assert result.status is detail.HistoryStatus.NOT_REGISTERED
        assert result.readings == ()
        assert "range" not in repo.calls

    def test_an_unknown_window_key_is_refused_rather_than_guessed(self):
        result = detail.get_temperature_history(REGISTERED_MAPPED, "all-time", FakeRepo())
        assert result.status is detail.HistoryStatus.NO_DATA
        assert result.readings == ()

    def test_an_unavailable_source_is_reported_not_emptied(self):
        result = detail.get_temperature_history(
            REGISTERED_MAPPED, "24h", FakeRepo(unavailable=True)
        )
        assert result.status is detail.HistoryStatus.UNAVAILABLE
        assert result.readings == ()


# ---------------------------------------------------------------------------
# What the model must never carry (gate sections 10 and 11)
# ---------------------------------------------------------------------------


class TestTheModelCarriesNoUnsupportedClaims:
    UNSUPPORTED = (
        "voltage", "current", "active_power", "reactive_power",
        "power_factor", "frequency", "energy",
    )
    STATE_WORDS = ("online", "offline", "active", "inactive", "healthy", "unhealthy", "status")

    @pytest.mark.parametrize("metric", UNSUPPORTED)
    def test_no_unsupported_metric_field_exists(self, metric):
        assert not hasattr(get(REGISTERED_MAPPED).rtl, metric)

    @pytest.mark.parametrize("word", STATE_WORDS)
    def test_no_communication_or_lifecycle_state_field_exists(self, word):
        rtl = get(REGISTERED_MAPPED).rtl
        assert not any(word in name for name in vars(rtl))

    def test_provenance_records_the_client_source(self):
        from services.rtl_source_facts_service import FactSource

        assert get(REGISTERED_MAPPED).rtl.provenance is FactSource.CLIENT_RTL_SQLSERVER

    @staticmethod
    def _executable_names() -> set[str]:
        """Every identifier the module's CODE mentions — docstrings and
        comments excluded.

        Scanning the raw source would match the module docstring, which names
        these sources precisely in order to say it does not use them. What
        matters is whether the code reaches for them.
        """
        import ast
        import inspect

        tree = ast.parse(inspect.getsource(detail))
        names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                names.add(node.id)
            elif isinstance(node, ast.Attribute):
                names.add(node.attr)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                names.add(getattr(node, "module", "") or "")
                names.update(a.name for a in node.names)
        return names

    @pytest.mark.parametrize(
        "banned",
        # NOT "readings": `RTLHistory.readings` is this module's own field for
        # client temperature rows. The PostgreSQL reach would be the accessor
        # or the module, which is what these names cover.
        ["plant_monitoring_repository", "monitoring_service", "hierarchy_service",
         "sqlalchemy", "db.engine", "get_readings", "get_readings_for_device"],
    )
    def test_the_service_reaches_for_no_postgresql_path(self, banned):
        """A real fallback would have to come through one of these."""
        assert banned not in self._executable_names()

    @pytest.mark.parametrize(
        "banned",
        ["device_status", "comms_alarm", "vw_installed_rtls", "last_comms_ok",
         "last_status", "get_installed_rtls"],
    )
    def test_no_status_or_comms_source_is_consulted(self, banned):
        assert banned not in self._executable_names()

    def test_it_reads_only_the_four_approved_source_methods(self):
        """The whole source surface of this page, enumerated. A new read here
        is a deliberate decision, not something that arrives unnoticed."""
        called = self._executable_names()
        repository_reads = {
            n for n in called
            if n.startswith("get_") and n not in {"get_rtl_detail", "get_temperature_history"}
        }
        assert repository_reads == {
            "get_registered_device_uids",   # dbo.device_list — the gate
            "get_transformer_mappings",     # dbo.trfr_list
            "get_transformer_hierarchy",    # dbo.vw_transformer_org_hierarchy
            "get_latest_temperatures",      # dbo.master_temperature (latest)
            "get_temperature_range",        # dbo.master_temperature (window)
        }
