"""SATURDAY-REAL-FLEET-01: real registered-RTL fleet (read-only, factual)."""
from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock

import pytest

from components import rtl_fleet as ui
from repositories.rtl_temperature_repository import (
    RTLLatestTemperature,
    RTLRegisteredDevice,
    RTLTemperatureRepository,
    RTLTemperatureRepositoryError,
    RTLTransformerHierarchy,
    RTLTransformerMapping,
)
from services import rtl_fleet_service as svc
from services.device_scope import EMPTY, UNRESTRICTED, DeviceScope
from tests.dash_tree import text_of

ROOT = Path(__file__).resolve().parent.parent
T = datetime(2026, 9, 17, 3, 39)  # naive source clock


def _latest(uid, temp, when=T, tied=None):
    tied = tied if tied is not None else (Decimal(temp),)
    value = tied[0] if len(tied) == 1 else None
    return RTLLatestTemperature(uid, when, value, len(tied), tuple(tied))


class FakeRepo:
    """Only the read methods the fleet uses; records calls (set-based check)."""

    def __init__(self, registered, latest=None, mappings=(), hierarchy=()):
        self.registered, self.latest = registered, latest or {}
        self.mappings, self.hierarchy = list(mappings), list(hierarchy)
        self.calls = []

    def _guard(self, name):
        self.calls.append(name)

    def get_registered_device_uids(self):
        self._guard("registered")
        return list(self.registered)

    def get_latest_temperatures(self, uids):
        self._guard("latest")
        return {u: v for u, v in self.latest.items() if u in set(uids)}

    def get_transformer_mappings(self):
        self._guard("mappings")
        return self.mappings

    def get_transformer_hierarchy(self):
        self._guard("hierarchy")
        return self.hierarchy


def _h(uid, code, zone="Z", sector="S", cnc="C", feeder="F", ou="OU"):
    return RTLTransformerHierarchy(uid, code, ou, zone, sector, cnc, feeder)


def _four_case_fleet():
    # 1 mapped+temp, 2 unmapped+temp, 3 mapped no temp, 4 unmapped no temp
    repo = FakeRepo(
        [4, 3, 2, 1],
        latest={1: _latest(1, "21.5"), 2: _latest(2, "30.0")},
        mappings=[RTLTransformerMapping(1, "T1"), RTLTransformerMapping(3, "T3")],
        hierarchy=[_h(1, "T1")],  # T3 has no hierarchy row
    )
    return svc.get_real_fleet(repo), repo


# ---------------------------------------------------------------- population
def test_all_339_registered_rtls_are_rows_in_uid_order_and_counts_are_derived():
    uids = list(range(29000, 29339))
    repo = FakeRepo(uids, latest={u: _latest(u, "20") for u in uids[:300]},
                    mappings=[RTLTransformerMapping(u, f"T{u}") for u in uids[:100]],
                    hierarchy=[_h(u, f"T{u}") for u in uids[:90]])
    fleet = svc.get_real_fleet(repo)
    assert fleet.status is svc.FleetStatus.DATA
    assert [r.device_uid for r in fleet.rows] == sorted(uids)
    s = fleet.summary
    assert (s.registered, s.mapped, s.with_temperature, s.no_temperature) == (339, 100, 300, 39)
    assert s.hierarchy_unavailable == 10


def test_only_registered_uids_appear_not_telemetry_or_mapping_only_uids():
    repo = FakeRepo([1], latest={1: _latest(1, "1"), 999: _latest(999, "5")},
                    mappings=[RTLTransformerMapping(888, "TX")], hierarchy=[_h(888, "TX")])
    assert [r.device_uid for r in svc.get_real_fleet(repo).rows] == [1]


def test_four_mapping_and_telemetry_combinations():
    fleet, _ = _four_case_fleet()
    r = {row.device_uid: row for row in fleet.rows}
    assert r[1].temperature_state is svc.TemperatureState.VALUE and r[1].has_transformer_mapping
    assert r[2].temperature_state is svc.TemperatureState.VALUE and not r[2].has_transformer_mapping
    assert r[3].temperature_state is svc.TemperatureState.NO_DATA and r[3].has_transformer_mapping
    assert r[4].temperature_state is svc.TemperatureState.NO_DATA and not r[4].has_transformer_mapping
    assert r[3].temperature is None and r[3].last_reported is None  # nothing synthesised
    assert r[1].last_reported == T and r[1].temperature == Decimal("21.5")


def test_hierarchy_available_unavailable_and_not_mapped():
    fleet, _ = _four_case_fleet()
    r = {row.device_uid: row for row in fleet.rows}
    assert r[1].hierarchy_state is svc.HierarchyState.AVAILABLE and r[1].hierarchy.zone == "Z"
    assert r[3].hierarchy_state is svc.HierarchyState.UNAVAILABLE and r[3].hierarchy is None
    assert r[2].hierarchy_state is svc.HierarchyState.NOT_MAPPED
    assert fleet.summary.hierarchy_unavailable == 1


def test_hierarchy_requires_an_exact_transformer_code_match():
    repo = FakeRepo([1], mappings=[RTLTransformerMapping(1, "T1")], hierarchy=[_h(1, "T1 ")])
    assert svc.get_real_fleet(repo).rows[0].hierarchy_state is svc.HierarchyState.UNAVAILABLE


def test_an_all_blank_hierarchy_row_is_unavailable():
    blank = RTLTransformerHierarchy(1, "T1", None, None, None, None, None)
    repo = FakeRepo([1], mappings=[RTLTransformerMapping(1, "T1")], hierarchy=[blank])
    assert svc.get_real_fleet(repo).rows[0].hierarchy_state is svc.HierarchyState.UNAVAILABLE


# ---------------------------------------------------------------- temperature
def test_conflicting_latest_values_propagate_as_ambiguous_and_are_preserved():
    amb = _latest(1, None, tied=(Decimal("20"), Decimal("25")))
    fleet = svc.get_real_fleet(FakeRepo([1], latest={1: amb}))
    row = fleet.rows[0]
    assert row.temperature_state is svc.TemperatureState.AMBIGUOUS
    assert row.temperature is None
    assert row.ambiguous_values == (Decimal("20"), Decimal("25"))
    assert fleet.summary.ambiguous == 1 and fleet.summary.with_temperature == 1
    text = text_of(ui.fleet_table(fleet.rows))
    assert "Ambiguous" in text and "20.0" in text and "25.0" in text


def test_identical_ties_show_the_common_value():
    tied = RTLLatestTemperature(1, T, Decimal("20"), 3, (Decimal("20"),))
    row = svc.get_real_fleet(FakeRepo([1], latest={1: tied})).rows[0]
    assert row.temperature_state is svc.TemperatureState.VALUE and row.temperature == Decimal("20")


def test_last_reported_is_the_telemetry_timestamp_shown_as_sast_unconverted():
    row = svc.get_real_fleet(FakeRepo([1], latest={1: _latest(1, "20")})).rows[0]
    assert row.last_reported == T
    assert "17 Sep 2026 03:39 SAST" in text_of(ui.fleet_table((row,)))


def test_the_row_model_carries_no_status_or_legacy_timestamp_fields():
    fields = set(svc.RTLFleetRow.__dataclass_fields__)
    assert not any(k in fields for k in ("status", "last_status", "last_status_timestamp", "online", "comms"))


# ---------------------------------------------------------------- failure
@pytest.mark.parametrize("fail_on", ["registered", "latest", "mappings", "hierarchy"])
def test_any_source_failure_is_unavailable_with_no_rows(fail_on):
    class Repo(FakeRepo):
        def _guard(self, name):
            self.calls.append(name)
            if name == fail_on:
                raise RTLTemperatureRepositoryError("down")

    fleet = svc.get_real_fleet(Repo([1, 2], latest={1: _latest(1, "1")}))
    assert fleet.status is svc.FleetStatus.UNAVAILABLE and fleet.rows == () and fleet.summary is None


def test_missing_rtl_configuration_is_unavailable_not_an_exception():
    from config.settings import RTLDatabaseConfigurationError

    def factory():
        raise RTLDatabaseConfigurationError("Missing RTL read-only database configuration")

    fleet = svc.get_real_fleet(RTLTemperatureRepository(factory))
    assert fleet.status is svc.FleetStatus.UNAVAILABLE


# ---------------------------------------------------------------- set-based
def test_source_reads_are_a_fixed_number_regardless_of_fleet_size():
    for n in (3, 339, 1200):
        uids = list(range(1, n + 1))
        repo = FakeRepo(uids, latest={u: _latest(u, "1") for u in uids})
        svc.get_real_fleet(repo)
        assert repo.calls == ["registered", "latest", "mappings", "hierarchy"]


def test_real_repository_issues_only_select_statements_in_bounded_batches():
    uids = list(range(1, 1201))
    cursor = Mock()
    cursor.fetchall.side_effect = lambda: []
    connection = Mock()
    connection.cursor.return_value = cursor
    repo = RTLTemperatureRepository(Mock(return_value=connection))
    repo.get_latest_temperatures(uids)
    statements = [c.args[0].lstrip().upper() for c in cursor.execute.call_args_list]
    assert len(statements) == 3  # 1200 UIDs -> 3 batches, never one per UID
    assert all(s.startswith(("SELECT", "WITH")) for s in statements)
    assert not any(re.search(r"\b(INSERT|UPDATE|DELETE|ALTER|CREATE|DROP)\b", s) for s in statements)


def test_hierarchy_read_is_select_only_and_trims_blank_text():
    cursor = Mock()
    cursor.fetchall.return_value = [(1, "T1", " OU ", "Z", "  ", None, "F")]
    connection = Mock()
    connection.cursor.return_value = cursor
    rows = RTLTemperatureRepository(Mock(return_value=connection)).get_transformer_hierarchy()
    sql = cursor.execute.call_args.args[0].upper()
    assert sql.lstrip().startswith("SELECT") and "VW_TRANSFORMER_ORG_HIERARCHY" in sql
    assert rows == [RTLTransformerHierarchy(1, "T1", "OU", "Z", None, None, "F")]


# ---------------------------------------------------------------- isolation
def test_fleet_service_has_no_postgresql_or_legacy_view_dependency():
    src = (ROOT / "services" / "rtl_fleet_service.py").read_text(encoding="utf-8")
    code = "\n".join(
        line for line in src.splitlines() if line.startswith(("import ", "from "))
    )
    for banned in ("plant_monitoring_repository", "db.engine", "sqlalchemy",
                   "fleet_overview_service", "hierarchy_service", "monitoring_service"):
        assert banned not in code, banned
    for legacy in ("vw_installed_rtls", "device_status", "comms_alarm", "last_comms_ok"):
        assert f'"{legacy}' not in src and f"FROM dbo.{legacy}" not in src


# ---------------------------------------------------------------- rendering
def test_rendering_uses_explicit_words_not_nulls_and_no_unsupported_metrics():
    fleet, _ = _four_case_fleet()
    html_text = text_of(ui.summary_cards(fleet.summary)) + text_of(ui.fleet_table(fleet.rows))
    assert "No temperature data" in html_text
    assert "No current transformer mapping" in html_text
    assert "Hierarchy unavailable" in html_text
    assert "None" not in html_text and "null" not in html_text.lower()
    lowered = html_text.lower()
    for banned in ("voltage", "active power", "reactive", "power factor",
                   "frequency", "energy", "online", "offline", "plant", "active rtl",
                   "retired", "inactive"):
        assert banned not in lowered, banned


def test_summary_wording_is_factual():
    fleet, _ = _four_case_fleet()
    text = text_of(ui.summary_cards(fleet.summary))
    for label in ("Registered RTLs", "Current transformer mappings",
                  "With temperature data", "No temperature data"):
        assert label in text
    assert "Active" not in text and "Online" not in text
    assert "not a count of active or online RTLs" in ui.SCOPE_NOTE


def test_filters_partition_correctly_and_counts_sum():
    fleet, _ = _four_case_fleet()
    counts = ui.filter_counts(fleet.rows)
    assert counts == {"all": 4, "with_temperature": 2, "no_temperature": 2, "no_mapping": 2}
    assert [r.device_uid for r in ui.filter_rows(fleet, "no_mapping")] == [2, 4]
    assert len(ui.filter_rows(fleet, "bogus")) == 4


def test_no_sensitive_fields_in_the_read_models():
    for cls in (RTLRegisteredDevice, svc.RTLFleetRow, RTLTransformerHierarchy):
        fields = " ".join(cls.__dataclass_fields__).lower()
        for banned in ("cell", "phone", "email", "password", "api_key", "contact"):
            assert banned not in fields


# ---------------------------------------------------------------- authorization
def test_only_unrestricted_scope_may_view_the_real_fleet():
    assert svc.may_view_real_fleet(UNRESTRICTED)
    assert not svc.may_view_real_fleet(EMPTY)
    assert not svc.may_view_real_fleet(DeviceScope(frozenset({"d1"})))
    assert not svc.may_view_real_fleet(None)
