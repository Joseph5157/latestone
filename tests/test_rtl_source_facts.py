"""RTL-INTEGRATION-04: real-data adapter foundation (SELECT-only, factual)."""
from __future__ import annotations

import dataclasses
import logging
import re
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock

import pymssql
import pytest

from repositories.rtl_temperature_repository import (
    LATEST_BATCH_SIZE,
    RTLTemperatureRepository,
    RTLTemperatureRepositoryError,
)
from services import rtl_source_facts_service as facts

ROOT = Path(__file__).resolve().parent.parent
T1 = datetime(2026, 9, 17, 8, 29)  # naive on purpose: source clock, no timezone


def _repo(*, fetchall=None, side_effect=None, execute_error=None):
    """Repository over a mock connection; fetchall returns successive results."""
    cursor = Mock()
    if side_effect is not None:
        cursor.fetchall.side_effect = side_effect
    else:
        cursor.fetchall.return_value = fetchall or []
    if execute_error is not None:
        cursor.execute.side_effect = execute_error
    connection = Mock()
    connection.cursor.return_value = cursor
    factory = Mock(return_value=connection)
    return RTLTemperatureRepository(factory), cursor, connection, factory


# ---------------------------------------------------------------- latest set
def test_latest_for_one_uid_is_parameterized_and_raw():
    repo, cursor, connection, _ = _repo(fetchall=[(29017, T1, Decimal("37.50"))])

    result = repo.get_latest_temperatures([29017])

    assert set(result) == {29017}
    latest = result[29017]
    assert latest.reading_time is T1 and latest.reading_time.tzinfo is None
    assert latest.temperature == Decimal("37.50")
    assert latest.tied_latest_row_count == 1 and not latest.has_latest_ambiguity
    sql, params = cursor.execute.call_args.args
    assert params == (29017,) and "29017" not in sql and "%s" in sql
    assert "SELECT *" not in sql.upper()
    cursor.close.assert_called_once()
    connection.close.assert_called_once()


def test_latest_for_multiple_uids_single_query_deterministic_order():
    rows = [(1, T1, Decimal("10")), (2, T1, Decimal("20")), (3, T1, Decimal("30"))]
    repo, cursor, _, factory = _repo(fetchall=rows)

    result = repo.get_latest_temperatures([3, 1, 2, 2])  # unordered + duplicate

    assert list(result) == [1, 2, 3]
    assert cursor.execute.call_count == 1  # no N+1
    assert factory.call_count == 1
    assert cursor.execute.call_args.args[1] == (1, 2, 3)  # sorted, deduplicated input


def test_latest_empty_request_opens_no_connection():
    repo, cursor, _, factory = _repo()

    assert repo.get_latest_temperatures([]) == {}
    assert repo.get_telemetry_device_uids([]) == []
    factory.assert_not_called()
    cursor.execute.assert_not_called()


def test_latest_unknown_and_mixed_uids_are_absent_not_synthesised():
    repo, _, _, _ = _repo(fetchall=[(29017, T1, Decimal("37.50"))])

    assert repo.get_latest_temperatures([29017, 999999]).keys() == {29017}
    repo_none, _, _, _ = _repo(fetchall=[])
    assert repo_none.get_latest_temperatures([999999]) == {}


def test_latest_batches_large_requests_without_per_uid_queries():
    uids = list(range(1, LATEST_BATCH_SIZE * 2 + 2))  # 3 batches
    repo, cursor, _, factory = _repo(fetchall=[])

    repo.get_latest_temperatures(uids)

    assert cursor.execute.call_count == 3
    assert factory.call_count == 1  # one connection for all batches
    assert [len(c.args[1]) for c in cursor.execute.call_args_list] == [
        LATEST_BATCH_SIZE, LATEST_BATCH_SIZE, 1,
    ]


def test_latest_400_uids_is_one_query():
    repo, cursor, _, _ = _repo(fetchall=[])
    repo.get_latest_temperatures(range(1, 401))
    assert cursor.execute.call_count == 1


def test_case_a_one_latest_row_is_unambiguous():
    repo, _, _, _ = _repo(fetchall=[(7, T1, Decimal("45.2"))])

    latest = repo.get_latest_temperatures([7])[7]

    assert (latest.reading_time, latest.temperature) == (T1, Decimal("45.2"))
    assert latest.tied_latest_row_count == 1 and latest.tied_distinct_temperature_count == 1
    assert not latest.has_latest_ambiguity


def test_case_b_identical_latest_rows_expose_common_value_and_count():
    repo, _, _, _ = _repo(fetchall=[(7, T1, Decimal("45.2")), (7, T1, Decimal("45.2"))])

    latest = repo.get_latest_temperatures([7])[7]

    assert (latest.reading_time, latest.temperature) == (T1, Decimal("45.2"))
    assert latest.tied_latest_row_count == 2
    assert latest.tied_distinct_temperature_count == 1
    assert latest.tied_source_temperatures == (Decimal("45.2"),)
    assert not latest.has_latest_ambiguity


def test_case_c_conflicting_latest_rows_stay_ambiguous_with_no_chosen_value():
    rows = [(7, T1, Decimal("71.8")), (7, T1, Decimal("45.2")), (7, T1, Decimal("71.8"))]
    repo, _, _, _ = _repo(fetchall=rows)

    latest = repo.get_latest_temperatures([7])[7]

    assert latest.reading_time == T1  # timestamp preserved
    assert latest.temperature is None  # no highest/lowest/first/average
    assert latest.has_latest_ambiguity
    assert latest.tied_latest_row_count == 3
    assert latest.tied_distinct_temperature_count == 2
    assert latest.tied_source_temperatures == (Decimal("45.2"), Decimal("71.8"))


def test_conflicting_latest_is_independent_of_source_row_order():
    a = [(7, T1, Decimal("1")), (7, T1, Decimal("2"))]
    first = _repo(fetchall=a)[0].get_latest_temperatures([7])[7]
    second = _repo(fetchall=list(reversed(a)))[0].get_latest_temperatures([7])[7]
    assert first == second and first.temperature is None


def test_extreme_values_are_not_filtered():
    rows = [(1, T1, Decimal("-999.00")), (2, T1, Decimal("99999.00"))]
    repo, _, _, _ = _repo(fetchall=rows)

    result = repo.get_latest_temperatures([1, 2])
    assert result[1].temperature == Decimal("-999.00")
    assert result[2].temperature == Decimal("99999.00")


def test_latest_sql_is_select_only_explicit_columns_no_mutation_keywords():
    repo, cursor, _, _ = _repo(fetchall=[])
    repo.get_latest_temperatures([1, 2])
    repo.get_telemetry_device_uids([1, 2])
    repo.get_telemetry_device_uids()
    for call in cursor.execute.call_args_list:
        sql = call.args[0].upper()
        assert "SELECT *" not in sql
        assert not re.search(r"\b(INSERT|UPDATE|DELETE|MERGE|ALTER|CREATE|DROP|TRUNCATE|INTO)\b", sql)
        assert not re.search(r"\b(EXEC|EXECUTE|SP_EXECUTESQL|XP_\w+|OPENROWSET|OPENQUERY)\b", sql)


def test_every_executable_rtl_sql_constant_is_read_only_and_exec_free():
    """Checks module-level SQL constants only, so comments/docs cannot trip it."""
    from repositories import rtl_temperature_repository as module
    constants = {n: v for n, v in vars(module).items() if n.endswith("_SQL") and isinstance(v, str)}
    assert len(constants) >= 7
    for name, sql in constants.items():
        text = sql.upper()
        assert text.lstrip().startswith(("SELECT", "WITH")), name
        assert "SELECT *" not in text, name
        assert not re.search(
            r"\b(INSERT|UPDATE|DELETE|MERGE|ALTER|CREATE|DROP|TRUNCATE|INTO"
            r"|EXEC|EXECUTE|SP_EXECUTESQL|XP_\w+|OPENROWSET|OPENQUERY)\b",
            text,
        ), name


@pytest.mark.parametrize("bad", ["29017", 1.5, None, True, 2**31])
def test_invalid_uids_rejected_before_any_connection(bad):
    repo, _, _, factory = _repo()
    with pytest.raises(ValueError):
        repo.get_latest_temperatures([bad])
    factory.assert_not_called()


def test_latest_driver_failure_is_safe_error_and_closes():
    repo, cursor, connection, _ = _repo(execute_error=pymssql.Error("secret host detail"))
    with pytest.raises(RTLTemperatureRepositoryError) as info:
        repo.get_latest_temperatures([1])
    assert "secret" not in str(info.value)
    cursor.close.assert_called_once()
    connection.close.assert_called_once()


# -------------------------------------------------------------- populations
def test_source_populations_are_separate_and_no_fleet_api_exists():
    repo, _, _, _ = _repo(side_effect=[[(1,), (2,)], [(2,), (3,)], [(2, "AA12")]])

    result = facts.get_source_populations(repo)

    pops = result.populations
    assert result.status is facts.FactsStatus.DATA
    assert pops.registered == {1, 2} and pops.telemetry == {2, 3} and pops.mapped == {2}
    assert pops.provenance is facts.FactSource.CLIENT_RTL_SQLSERVER
    banned = re.compile(r"canonical|active_fleet|monitored_fleet|get_fleet")
    for module_names in (dir(facts), dir(RTLTemperatureRepository)):
        assert not [n for n in module_names if banned.search(n)]


# ------------------------------------------------------------ device facts
def _facts_repo():
    repo = Mock(spec=RTLTemperatureRepository)
    repo.get_registered_device_uids.return_value = [1, 2]
    repo.get_telemetry_device_uids.return_value = [2, 3]
    from repositories.rtl_temperature_repository import RTLLatestTemperature, RTLTransformerMapping
    repo.get_transformer_mappings.return_value = [RTLTransformerMapping(2, "AA12")]
    repo.get_latest_temperatures.return_value = {2: RTLLatestTemperature(2, T1, Decimal("16.00"))}
    return repo


def test_device_facts_report_source_facts_without_business_meaning():
    result = facts.get_device_facts([3, 1, 2, 4], _facts_repo())

    by_uid = {f.device_uid: f for f in result.facts}
    assert [f.device_uid for f in result.facts] == [1, 2, 3, 4]
    assert (by_uid[1].registered_in_device_list, by_uid[1].has_temperature_telemetry, by_uid[1].has_transformer_mapping) == (True, False, False)
    two = by_uid[2]
    assert (two.registered_in_device_list, two.has_temperature_telemetry, two.has_transformer_mapping) == (True, True, True)
    assert two.transformer_mapping_values == ("AA12",)  # raw value
    assert two.latest_temperature.temperature == Decimal("16.00")
    assert (by_uid[3].registered_in_device_list, by_uid[3].has_temperature_telemetry) == (False, True)
    unknown = by_uid[4]
    assert not (unknown.registered_in_device_list or unknown.has_temperature_telemetry or unknown.has_transformer_mapping)
    assert unknown.latest_temperature is None
    assert result.status is facts.FactsStatus.PARTIAL  # 1 of 4 has a reading
    assert all(f.provenance is facts.FactSource.CLIENT_RTL_SQLSERVER for f in result.facts)


def test_device_facts_contain_no_status_words_or_sensitive_fields():
    names = {f.name for f in dataclasses.fields(facts.RTLDeviceFacts)}
    assert names == {
        "device_uid", "registered_in_device_list", "has_temperature_telemetry",
        "has_transformer_mapping", "transformer_mapping_values", "latest_temperature", "provenance",
    }
    for banned in ("online", "offline", "active", "healthy", "attention", "cell", "phone", "contact"):
        assert not [n for n in names if banned in n]


def test_device_facts_uses_four_set_based_operations_regardless_of_uid_count():
    """Pin no-N+1: registered, telemetry membership, mappings, latest = 4 SQL ops."""
    for size in (1, 50, LATEST_BATCH_SIZE):
        repo, cursor, _, factory = _repo(fetchall=[])

        result = facts.get_device_facts(range(1, size + 1), repo)

        assert result.status is facts.FactsStatus.NO_DATA
        assert cursor.execute.call_count == 4, size
        sqls = [c.args[0] for c in cursor.execute.call_args_list]
        assert "dbo.device_list" in sqls[0]
        assert "dbo.master_temperature" in sqls[1] and "DISTINCT" in sqls[1]
        assert "dbo.trfr_list" in sqls[2]
        assert "MAX(t.reading_timestamp)" in sqls[3]
        assert factory.call_count == 4  # one short connection per repository call, constant in size


def test_device_facts_conflicting_latest_is_not_resolved_by_service():
    from repositories.rtl_temperature_repository import RTLLatestTemperature
    repo = _facts_repo()
    repo.get_latest_temperatures.return_value = {
        2: RTLLatestTemperature(2, T1, None, 2, (Decimal("45.2"), Decimal("71.8")))
    }
    fact = facts.get_device_facts([2], repo).facts[0]
    assert fact.latest_temperature.temperature is None and fact.latest_temperature.has_latest_ambiguity


def test_registered_query_selects_only_uid():
    repo, cursor, _, _ = _repo(fetchall=[(1,)])
    repo.get_registered_device_uids()
    sql = cursor.execute.call_args.args[0]
    assert sql.split("FROM")[0].split() == ["SELECT", "device_uid"]


# ----------------------------------------------------------------- outcomes
def test_latest_outcomes_data_partial_no_data_empty():
    repo = Mock(spec=RTLTemperatureRepository)
    from repositories.rtl_temperature_repository import RTLLatestTemperature
    one = RTLLatestTemperature(1, T1, Decimal("1"))
    repo.get_latest_temperatures.return_value = {1: one}
    assert facts.get_latest_temperatures([1], repo).status is facts.FactsStatus.DATA
    partial = facts.get_latest_temperatures([1, 2], repo)
    assert partial.status is facts.FactsStatus.PARTIAL and partial.uids_without_reading == (2,)
    repo.get_latest_temperatures.return_value = {}
    assert facts.get_latest_temperatures([9], repo).status is facts.FactsStatus.NO_DATA
    assert facts.get_latest_temperatures([], repo).status is facts.FactsStatus.NO_DATA


def test_rtl_failure_is_unavailable_with_no_synthetic_fallback(caplog):
    repo = Mock(spec=RTLTemperatureRepository)
    repo.get_latest_temperatures.side_effect = RTLTemperatureRepositoryError("x")
    repo.get_registered_device_uids.side_effect = RTLTemperatureRepositoryError("x")
    with caplog.at_level(logging.WARNING):
        latest = facts.get_latest_temperatures([1], repo)
        device = facts.get_device_facts([1], repo)
        pops = facts.get_source_populations(repo)
    assert latest.status is device.status is pops.status is facts.FactsStatus.UNAVAILABLE
    assert latest.latest_by_uid == {} and device.facts == () and pops.populations is None
    assert "RTL source facts unavailable" in caplog.text  # diagnosable
    assert "password" not in caplog.text.lower() and "SELECT" not in caplog.text


# --------------------------------------------------------------- boundaries
def test_provenance_distinguishes_client_rtl_from_application_postgresql():
    assert [m.value for m in facts.FactSource] == ["client_rtl_sqlserver"]
    assert facts.get_latest_temperatures([], None).provenance is facts.FactSource.CLIENT_RTL_SQLSERVER


def test_adapter_is_not_wired_into_user_facing_layers():
    """Authorization boundary: no callback/route/component may reach raw RTL facts."""
    user_facing = [ROOT / "routes.py", ROOT / "app.py"]
    for folder in ("callbacks", "components", "pages"):
        user_facing += list((ROOT / folder).rglob("*.py")) if (ROOT / folder).exists() else []
    offenders = [
        str(p.relative_to(ROOT)) for p in user_facing
        if p.exists() and "rtl_source_facts_service" in p.read_text(encoding="utf-8")
    ]
    assert offenders == []


def test_adapter_modules_do_not_import_postgresql_or_write_paths():
    import ast
    banned = ("db", "sqlalchemy", "alembic", "psycopg", "repositories.plant_monitoring_repository")
    for rel in ("services/rtl_source_facts_service.py", "repositories/rtl_temperature_repository.py"):
        tree = ast.parse((ROOT / rel).read_text(encoding="utf-8"))
        imported = [
            n.module or "" if isinstance(n, ast.ImportFrom) else a.name
            for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))
            for a in (n.names if isinstance(n, ast.Import) else [n])
        ]
        assert not [m for m in imported if m.split(".")[0] in banned or m in banned], (rel, imported)


def test_no_timezone_conversion_in_adapter_sources():
    for rel in ("services/rtl_source_facts_service.py", "repositories/rtl_temperature_repository.py"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert not re.search(r"tzinfo\s*=|astimezone|timezone\.utc|ZoneInfo|pytz|localize", text)


# -------------------------------------------------------------- integration
@pytest.mark.rtl_db
def test_local_rtl_set_latest_matches_single_uid_latest_and_populations():
    repo = RTLTemperatureRepository()
    telemetry = repo.get_telemetry_device_uids()
    assert len(telemetry) == 400
    sample = telemetry[:10]
    batch = repo.get_latest_temperatures(sample + [999999])
    assert 999999 not in batch
    for uid in sample:
        single = repo.get_latest_temperature(uid)
        if single is None:
            assert uid not in batch
        else:
            assert (batch[uid].reading_time, batch[uid].temperature) == (single.reading_time, single.temperature)
            assert batch[uid].reading_time.tzinfo is None
    known = repo.get_latest_temperatures([29743])[29743]
    assert (str(known.reading_time), known.temperature) == ("2026-09-17 03:39:00", Decimal("16.00"))
    assert not known.has_latest_ambiguity and known.tied_latest_row_count == 1
    everything = repo.get_latest_temperatures(telemetry)
    assert len(everything) == 400  # local data: every telemetry UID has a timestamped reading
    assert not [u for u, v in everything.items() if v.has_latest_ambiguity]
    assert len(repo.get_registered_device_uids()) == 339
    assert len(repo.get_mapped_device_uids()) == 185
    assert repo.get_telemetry_device_uids([29743, 999999]) == [29743]

    result = facts.get_device_facts([29743, 999999], repo)
    assert result.facts[0].has_temperature_telemetry and result.facts[0].registered_in_device_list
    assert not result.facts[1].has_temperature_telemetry
