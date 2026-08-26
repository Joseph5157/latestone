"""Guards the layering rule: Pages compose, Components render, Callbacks
coordinate, Services decide, Repositories fetch.

`components/` must stay presentation-only — no database access, direct or
via the repository layer. `pages/` must not reach past callbacks/services
into the repository layer either. Written as an AST import scan rather than
a text search so a module doc-comment mentioning "repositories" cannot
trip a false positive, and rewritten import styles (`import repositories.x`,
`from repositories import x`) are all still caught.
"""
from __future__ import annotations

import ast
import pathlib

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
FORBIDDEN_ROOTS = {"repositories", "db"}


def _imported_top_level_modules(path: pathlib.Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            # `from . import x` / `from .x import y` (level > 0) is an
            # intra-package relative import, never a route to another
            # top-level package, so only absolute imports are checked.
            if node.module and node.level == 0:
                modules.add(node.module.split(".")[0])
    return modules


def _violations(directory: str, forbidden: set[str]) -> dict[str, set[str]]:
    found = {}
    for path in sorted((REPO_ROOT / directory).glob("*.py")):
        hit = _imported_top_level_modules(path) & forbidden
        if hit:
            found[path.name] = hit
    return found


def test_components_do_not_import_repositories_or_db():
    violations = _violations("components", FORBIDDEN_ROOTS)
    assert not violations, (
        f"components/ must stay presentation-only, but found: {violations}. "
        "Route data access through a service or callback instead."
    )


def test_pages_do_not_import_repositories():
    violations = _violations("pages", {"repositories"})
    assert not violations, (
        f"pages/ must compose components only, but found: {violations}. "
        "Fetch data in a callback and pass it in, not from a page module."
    )


#: Service functions that decide how raw data is transformed (binning,
#: aggregation, KPI-context derivation, ...). Components may still import
#: *types* from services.monitoring_service (Freshness, MetricView, Reading,
#: DeltaResult, ConsumptionBar, FleetHealth, ...) — that is a shared
#: vocabulary, not a decision, and nearly every component legitimately does
#: it. A blanket "components must not import services" rule would fail on
#: that legitimate use, so this guard names the actual violations instead: a
#: component computing derived data itself rather than rendering what the
#: service already prepared. `bin_consumption`/`choose_bin` are the names
#: Phase 3 moved the trend cells off of; `reading_age`/`series_context` are the
#: names Phase 4 moved kpi_card.py off of (onto MetricView properties that
#: call them internally — the properties themselves are not banned, only a
#: component importing the raw functions is).
#:
#: `evaluate_freshness`/`aggregate_freshness` are listed pre-emptively rather
#: than in response to a violation: the Phase 5 metric-health work introduces
#: the first components that render freshness rollups, and "the component must
#: not decide what is stale" is exactly the rule that is easy to break while
#: writing them. No component imports either today, so this costs nothing now
#: and refuses the mistake later.
#:
#: `metric_health_from_rows`/`hottest_temperature` are the two Phase 5 service
#: entry points that decide, respectively, which state a metric's rollup is in
#: and which device's reading is hottest. `components.metric_health` and
#: `components.temperature_attribution` render `MetricHealth`/
#: `TemperatureAttribution` — the finished view models these functions
#: return — never the rows or readings those functions take as input. Listing
#: the functions themselves (not just `evaluate_freshness`/`aggregate_freshness`
#: underneath them) closes the gap where a component could call the
#: higher-level function directly and still end up deciding freshness.
FORBIDDEN_SERVICE_SYMBOLS = {
    "bin_consumption",
    "choose_bin",
    "reading_age",
    "series_context",
    "evaluate_freshness",
    "aggregate_freshness",
    "metric_health_from_rows",
    "hottest_temperature",
}


def _imported_symbols_from_services(path: pathlib.Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    symbols = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.ImportFrom)
            and node.module
            and node.module.split(".")[0] == "services"
        ):
            symbols.update(alias.name for alias in node.names)
    return symbols


def test_components_do_not_call_forbidden_service_functions_directly():
    violations = {}
    for path in sorted((REPO_ROOT / "components").glob("*.py")):
        hit = _imported_symbols_from_services(path) & FORBIDDEN_SERVICE_SYMBOLS
        if hit:
            violations[path.name] = hit
    assert not violations, (
        f"components/ must render already-prepared data, but found: {violations}. "
        "Move the computation into services/monitoring_service.py and pass the "
        "prepared result in through the callback instead."
    )
