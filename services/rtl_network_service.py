"""Current network context for the registered client RTLs (LATEST-NETWORK-CONTEXT-01).

Answers "where is each registered RTL in the client's network right now?" from
the read-only client RTL SQL Server, and nothing else. The rule (ADR-031):

* **Population** - exactly ``dbo.device_list`` (the registered directory).
  Telemetry-only and historical-only UIDs never appear. No count is hard-coded.
* **Current transformer** - ``dbo.trfr_list``, the existing verified current
  mapping candidate (it agrees with ``device_status.trfr``). An RTL with no
  row has *no current transformer mapping*; an older code found elsewhere is
  history and is never promoted to current.
* **Hierarchy** - ``dbo.vw_transformer_org_hierarchy`` (TUG-derived, read-only
  reference enrichment) where its row names the same transformer code as the
  current mapping. Equality is the database's own: whitespace-trimmed and
  case-insensitive, as SQL Server compares these columns. Never fuzzy. No
  match, a blank row, or conflicting rows -> "Hierarchy unavailable".
* **Corroboration** - the latest code in ``settings_upload_log``,
  ``startup_msg_log`` and ``master_temperature`` is compared with the current
  mapping. They never override it (``trfr_list`` outranks them because the
  prior audit established it as the current candidate); a disagreement, or a
  tie between different codes at a source's latest timestamp, is *surfaced*
  on the row as a ``SourceDisagreement`` and never resolved by picking one.
  A source with nothing for the RTL is silent, not a disagreement.
* Several ``trfr_list`` codes for one UID are ambiguous: no single current
  transformer is chosen and no hierarchy is resolved.

Deliberately absent: Online/Offline/active/health, lifecycle, transformer
movement history, TUG-derived asset status, the seven electrical metrics,
PostgreSQL and any fallback when the source is unavailable.

Authorization: same as the real fleet (``may_view_real_fleet``).
"""
from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum

from config.settings import RTLDatabaseConfigurationError
from repositories.rtl_temperature_repository import (
    RTLReportedTransformerCode,
    RTLTemperatureRepository,
    RTLTemperatureRepositoryError,
    RTLTransformerHierarchy,
)
from services.rtl_fleet_service import HierarchyContext, HierarchyState, may_view_real_fleet

__all__ = [
    "CurrentNetworkRow", "CurrentNetwork", "EvidenceSource", "MappingStatus",
    "NetworkFilter", "NetworkStatus", "NetworkSummary", "SourceDisagreement",
    "build_rows", "get_current_network", "get_network_row", "may_view_real_fleet",
]

logger = logging.getLogger(__name__)

#: Cascade levels, highest first. The order is the whole cascade contract.
LEVELS = ("zone", "sector", "cnc", "feeder", "transformer")

SCOPE_ALL = "all"
SCOPE_MAPPED = "mapped"
SCOPE_UNMAPPED = "unmapped"
SCOPE_HIERARCHY_UNAVAILABLE = "hierarchy_unavailable"
SCOPE_NEEDS_REVIEW = "needs_review"
SCOPES = (SCOPE_ALL, SCOPE_MAPPED, SCOPE_UNMAPPED, SCOPE_HIERARCHY_UNAVAILABLE, SCOPE_NEEDS_REVIEW)


class NetworkStatus(str, Enum):
    DATA = "data"
    UNAVAILABLE = "unavailable"  # source unreachable; nothing synthesised


class MappingStatus(str, Enum):
    MAPPED = "mapped"  # exactly one current trfr_list code
    NOT_MAPPED = "not_mapped"  # no trfr_list row
    AMBIGUOUS = "ambiguous"  # several trfr_list codes; none chosen


class EvidenceSource(str, Enum):
    SETTINGS = "settings"  # latest settings_upload_log record
    STARTUP = "startup"  # latest startup_msg_log (check-in) record
    TELEMETRY = "telemetry"  # latest master_temperature record


@dataclass(frozen=True)
class SourceDisagreement:
    """A corroborating source whose latest code differs from the mapping."""

    source: EvidenceSource
    codes: tuple[str, ...]  # what that source's latest record says (distinct)


@dataclass(frozen=True)
class CurrentNetworkRow:
    device_uid: int
    mapping_status: MappingStatus
    transformer_code: str | None  # the single current code; None unless MAPPED
    mapping_codes: tuple[str, ...]  # raw trfr_list codes (>1 only when AMBIGUOUS)
    hierarchy_state: HierarchyState
    hierarchy: HierarchyContext | None
    disagreements: tuple[SourceDisagreement, ...] = ()
    hierarchy_conflict: bool = False  # several differing hierarchy rows for the code

    @property
    def has_current_mapping(self) -> bool:
        return self.mapping_status is MappingStatus.MAPPED

    @property
    def needs_review(self) -> bool:
        return (
            bool(self.disagreements)
            or self.mapping_status is MappingStatus.AMBIGUOUS
            or self.hierarchy_conflict
        )


@dataclass(frozen=True)
class NetworkSummary:
    registered: int
    mapped: int
    unmapped: int
    hierarchy_resolved: int
    hierarchy_unavailable: int  # mapped, no usable hierarchy path
    needs_review: int


@dataclass(frozen=True)
class CurrentNetwork:
    status: NetworkStatus
    rows: tuple[CurrentNetworkRow, ...] = ()


def _key(code: str) -> str:
    return code.strip().casefold()


def summarise(rows: Iterable[CurrentNetworkRow]) -> NetworkSummary:
    rows = tuple(rows)
    resolved = sum(r.hierarchy_state is HierarchyState.AVAILABLE for r in rows)
    unavailable = sum(r.hierarchy_state is HierarchyState.UNAVAILABLE for r in rows)
    unmapped = sum(r.mapping_status is MappingStatus.NOT_MAPPED for r in rows)
    return NetworkSummary(
        registered=len(rows),
        mapped=len(rows) - unmapped,
        unmapped=unmapped,
        hierarchy_resolved=resolved,
        hierarchy_unavailable=unavailable,
        needs_review=sum(r.needs_review for r in rows),
    )


def build_rows(
    registered: Iterable[int],
    mappings: dict[int, tuple[str, ...]],
    hierarchy_rows: Iterable[RTLTransformerHierarchy],
    evidence: dict[EvidenceSource, Iterable[RTLReportedTransformerCode]],
) -> tuple[CurrentNetworkRow, ...]:
    """Pure assembly: one row per registered UID, ascending UID order.

    Only ``registered`` is iterated, so no other UID can appear. The current
    transformer comes from ``mappings`` alone; ``evidence`` can only add a
    disagreement flag, never change the code or the hierarchy.
    """
    view: dict[int, list[RTLTransformerHierarchy]] = defaultdict(list)
    for h in hierarchy_rows:
        view[h.device_uid].append(h)
    reported: dict[EvidenceSource, dict[int, set[str]]] = {}
    for source, items in evidence.items():
        by_uid: dict[int, set[str]] = defaultdict(set)
        for item in items:
            by_uid[item.device_uid].add(item.transformer_code)
        reported[source] = by_uid

    rows = []
    for uid in sorted(set(registered)):
        codes = tuple(sorted(set(mappings.get(uid, ()))))
        if not codes:
            rows.append(CurrentNetworkRow(uid, MappingStatus.NOT_MAPPED, None, (),
                                          HierarchyState.NOT_MAPPED, None))
            continue
        if len(codes) > 1:
            rows.append(CurrentNetworkRow(uid, MappingStatus.AMBIGUOUS, None, codes,
                                          HierarchyState.UNAVAILABLE, None))
            continue
        code = codes[0]

        contexts = {
            HierarchyContext(h.operating_unit, h.zone, h.sector, h.cnc, h.feeder)
            for h in view.get(uid, ())
            if _key(h.transformer_code) == _key(code)
        }
        contexts = {c for c in contexts if not c.is_empty}
        conflict = len(contexts) > 1
        if len(contexts) == 1:
            state, context = HierarchyState.AVAILABLE, next(iter(contexts))
        else:
            state, context = HierarchyState.UNAVAILABLE, None

        disagreements = []
        for source in EvidenceSource:
            said = reported.get(source, {}).get(uid)
            if said and any(_key(c) != _key(code) for c in said):
                disagreements.append(SourceDisagreement(source, tuple(sorted(said))))
        rows.append(CurrentNetworkRow(uid, MappingStatus.MAPPED, code, codes, state, context,
                                      tuple(disagreements), conflict))
    return tuple(rows)


def get_current_network(repository: RTLTemperatureRepository | None = None) -> CurrentNetwork:
    """The current network context, from a fixed six set-based reads.

    Registered directory, current mappings, hierarchy view, and the latest
    settings / startup / telemetry code per registered UID. No read depends on
    the number of RTLs. Any source failure yields UNAVAILABLE with no rows.
    """
    repo = repository if repository is not None else RTLTemperatureRepository()
    try:
        registered = repo.get_registered_device_uids()
        mapping_rows = repo.get_transformer_mappings()
        hierarchy_rows = repo.get_transformer_hierarchy()
        evidence = {
            EvidenceSource.SETTINGS: repo.get_latest_settings_transformer_codes(),
            EvidenceSource.STARTUP: repo.get_latest_startup_transformer_codes(),
            EvidenceSource.TELEMETRY: repo.get_latest_telemetry_transformer_codes(),
        }
    except (RTLTemperatureRepositoryError, RTLDatabaseConfigurationError) as exc:
        # Operation and exception class only: never SQL, credentials or rows.
        logger.warning("Current network unavailable (%s)", type(exc).__name__)
        return CurrentNetwork(NetworkStatus.UNAVAILABLE)
    mappings: dict[int, list[str]] = defaultdict(list)
    for m in mapping_rows:
        mappings[m.device_uid].append(m.transformer_code)
    rows = build_rows(registered, {u: tuple(c) for u, c in mappings.items()},
                      hierarchy_rows, evidence)
    return CurrentNetwork(NetworkStatus.DATA, rows)


def get_network_row(
    device_uid: int, repository: RTLTemperatureRepository | None = None
) -> tuple[NetworkStatus, CurrentNetworkRow | None]:
    """The current-network row for one UID, by the SAME rule as the whole view.

    RTL-NETWORK-USE-01. Consumers that show one RTL (the detail page) call this
    instead of re-deriving mapping, hierarchy or disagreement, so the two pages
    cannot disagree. It builds the full snapshot (six fixed reads) and selects
    the row; ``None`` means the UID is not registered.
    """
    network = get_current_network(repository)
    if network.status is not NetworkStatus.DATA:
        return network.status, None
    return network.status, next((r for r in network.rows if r.device_uid == device_uid), None)


# --------------------------------------------------------------------------
# Filtering (pure). Operates only over the rows given, i.e. the registered
# population: a filter can never offer a value no registered RTL carries.
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class NetworkFilter:
    scope: str = SCOPE_ALL
    zone: str | None = None
    sector: str | None = None
    cnc: str | None = None
    feeder: str | None = None
    transformer: str | None = None

    def value(self, level: str) -> str | None:
        return getattr(self, level)


def _level_value(row: CurrentNetworkRow, level: str) -> str | None:
    if level == "transformer":
        return row.transformer_code if row.hierarchy_state is HierarchyState.AVAILABLE else None
    return getattr(row.hierarchy, level, None) if row.hierarchy else None


_SCOPE_TESTS = {
    SCOPE_ALL: lambda r: True,
    SCOPE_MAPPED: lambda r: r.has_current_mapping,
    SCOPE_UNMAPPED: lambda r: r.mapping_status is MappingStatus.NOT_MAPPED,
    SCOPE_HIERARCHY_UNAVAILABLE: lambda r: r.hierarchy_state is HierarchyState.UNAVAILABLE,
    SCOPE_NEEDS_REVIEW: lambda r: r.needs_review,
}


def scope_rows(rows: Iterable[CurrentNetworkRow], scope: str) -> tuple[CurrentNetworkRow, ...]:
    """An unknown scope shows every registered RTL."""
    test = _SCOPE_TESTS.get(scope, _SCOPE_TESTS[SCOPE_ALL])
    return tuple(r for r in rows if test(r))


def scope_counts(rows: Iterable[CurrentNetworkRow]) -> dict[str, int]:
    rows = tuple(rows)
    return {s: sum(1 for r in rows if _SCOPE_TESTS[s](r)) for s in SCOPES}


def level_options(rows: Iterable[CurrentNetworkRow], level: str) -> tuple[str, ...]:
    """Distinct values of one level over these rows, sorted, blanks excluded."""
    return tuple(sorted({v for r in rows if (v := _level_value(r, level))}, key=str.casefold))


def normalise_filter(rows: Iterable[CurrentNetworkRow], selection: NetworkFilter) -> NetworkFilter:
    """Enforce the cascade: a selected value is kept only while the levels above
    it (those that are selected) still offer it. Levels may be skipped - a
    feeder can be chosen without a sector - but a value that a changed parent
    no longer offers is cleared."""
    scope = selection.scope if selection.scope in SCOPES else SCOPE_ALL
    current = scope_rows(rows, scope)
    chosen: dict[str, str | None] = {}
    for level in LEVELS:
        value = selection.value(level)
        if value is not None and value in level_options(current, level):
            chosen[level] = value
            current = tuple(r for r in current if _level_value(r, level) == value)
        else:
            chosen[level] = None
    return NetworkFilter(scope=scope, **chosen)


def filter_rows(rows: Iterable[CurrentNetworkRow], selection: NetworkFilter) -> tuple[CurrentNetworkRow, ...]:
    """Rows matching the scope and every selected level (selection normalised)."""
    rows = tuple(rows)
    selection = normalise_filter(rows, selection)
    current = scope_rows(rows, selection.scope)
    for level in LEVELS:
        value = selection.value(level)
        if value is not None:
            current = tuple(r for r in current if _level_value(r, level) == value)
    return current


def cascade_options(rows: Iterable[CurrentNetworkRow], selection: NetworkFilter) -> dict[str, tuple[str, ...]]:
    """Options per level, each constrained by the levels above it."""
    rows = tuple(rows)
    selection = normalise_filter(rows, selection)
    current = scope_rows(rows, selection.scope)
    options: dict[str, tuple[str, ...]] = {}
    for level in LEVELS:
        options[level] = level_options(current, level)
        value = selection.value(level)
        if value is not None:
            current = tuple(r for r in current if _level_value(r, level) == value)
    return options


def next_level(selection: NetworkFilter) -> str | None:
    """The first level with no selection, or None when all are chosen."""
    for level in LEVELS:
        if selection.value(level) is None:
            return level
    return None


def level_breakdown(rows: Iterable[CurrentNetworkRow], level: str) -> tuple[tuple[str, int], ...]:
    """(value, RTL count) for one level over rows that carry it, sorted."""
    counts: dict[str, int] = defaultdict(int)
    for r in rows:
        if (v := _level_value(r, level)):
            counts[v] += 1
    return tuple(sorted(counts.items(), key=lambda kv: kv[0].casefold()))


# --------------------------------------------------------------------------
# JSON-safe payload, so the page reads the source once per load and every
# filter change is a pure re-render of the same snapshot.
# --------------------------------------------------------------------------

def to_payload(rows: Iterable[CurrentNetworkRow]) -> list[dict]:
    return [
        {
            "uid": r.device_uid,
            "mapping": r.mapping_status.value,
            "code": r.transformer_code,
            "codes": list(r.mapping_codes),
            "h_state": r.hierarchy_state.value,
            "h": (
                [r.hierarchy.operating_unit, r.hierarchy.zone, r.hierarchy.sector,
                 r.hierarchy.cnc, r.hierarchy.feeder]
                if r.hierarchy else None
            ),
            "conflict": r.hierarchy_conflict,
            "dis": [[d.source.value, list(d.codes)] for d in r.disagreements],
        }
        for r in rows
    ]


def from_payload(payload: object) -> tuple[CurrentNetworkRow, ...]:
    """Rebuild rows from a page store. Malformed entries are dropped, not guessed."""
    rows = []
    for item in payload if isinstance(payload, list) else ():
        try:
            h = item["h"]
            rows.append(CurrentNetworkRow(
                device_uid=int(item["uid"]),
                mapping_status=MappingStatus(item["mapping"]),
                transformer_code=item["code"],
                mapping_codes=tuple(item["codes"]),
                hierarchy_state=HierarchyState(item["h_state"]),
                hierarchy=HierarchyContext(*h) if h else None,
                disagreements=tuple(
                    SourceDisagreement(EvidenceSource(s), tuple(c)) for s, c in item["dis"]
                ),
                hierarchy_conflict=bool(item["conflict"]),
            ))
        except (KeyError, TypeError, ValueError):
            continue
    return tuple(sorted(rows, key=lambda r: r.device_uid))
