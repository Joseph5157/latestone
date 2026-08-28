"""Layer 2 presentation and its unchanged listing/service boundary."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import unquote
from unittest.mock import Mock

import pytest
from dash import html, no_update

from callbacks import listings
from components.fleet_condition import (
    condition_wording, data_freshness, fleet_condition_summary, fleet_inventory,
    fleet_condition_panels, fresh_data_coverage,
)
from pages.plants_overview import layout
from services.device_scope import UNRESTRICTED
from services.monitoring_service import Freshness, fleet_health_from_rows
from tests.dash_tree import find_by_exact_class, find_by_id, links, text_of, walk

F, S, N = Freshness.FRESH, Freshness.STALE, Freshness.NO_DATA


@pytest.mark.parametrize("counts,headline,numerator,label", [
    ({F: 0, S: 7, N: 0}, "All RTLs are stale", 7, "Stale or no data"),
    ({F: 3, S: 1, N: 0}, "Some RTLs require attention", 1, "Stale or no data"),
    ({F: 3, S: 1, N: 2}, "Some RTLs require attention", 3, "Stale or no data"),
    ({F: 3, S: 0, N: 2}, "Some RTLs have no data", 2, "Stale or no data"),
    ({F: 0, S: 0, N: 8}, "All RTLs have no data", 8, "Stale or no data"),
    ({F: 9, S: 0, N: 0}, "All RTLs are fresh", 0, "Stale or no data"),
    ({}, "No RTLs to assess", 0, "Stale or no data"),
    ({F: 0, S: 0, N: 0}, "No RTLs to assess", 0, "Stale or no data"),
])
def test_summary_uses_dynamic_condition_and_real_ring_ratio(counts, headline, numerator, label):
    block = fleet_condition_summary(counts)
    total = sum(counts.values())
    assert condition_wording(counts)[1] == headline
    assert headline in text_of(block)
    assert text_of(find_by_exact_class(block, "fleet-condition__number")) == str(numerator)
    assert f"{numerator} of {total} monitored RTLs require attention" in text_of(block)
    ring = find_by_exact_class(block, "fleet-condition__ring")[0]
    assert getattr(ring, "aria-label") == f"Attention Required: {numerator} of {total} monitored RTLs (Stale or No Data)"
    arc = find_by_exact_class(block, "fleet-condition__arc")[1]
    percentage = 100 * numerator / total if total else 0
    assert f'stroke-dasharray="{percentage} 100"' in unquote(arc.style["maskImage"])
    if counts.get(S, 0) != total or not total:
        assert "All RTLs are stale" not in text_of(block)


@pytest.mark.parametrize("counts,percentages", [
    ({F: 90, S: 27, N: 3}, ["75.0%", "22.5%", "2.5%"]),
    ({F: 1, S: 1, N: 1}, ["33.3%", "33.3%", "33.3%"]),
    ({S: 11}, ["0.0%", "100.0%", "0.0%"]),
    ({}, ["0.0%", "0.0%", "0.0%"]),
])
def test_freshness_counts_percentages_and_exact_segment_widths(counts, percentages):
    block = data_freshness(counts)
    assert [text_of(n) for n in find_by_exact_class(block, "fleet-condition__stat-label")] == ["Fresh", "Stale", "No Data"]
    assert [text_of(n) for n in find_by_exact_class(block, "fleet-condition__stat-value")] == [str(counts.get(s, 0)) for s in (F, S, N)]
    assert [text_of(n) for n in find_by_exact_class(block, "fleet-condition__stat-meta")] == percentages
    segments = find_by_exact_class(block, "fleet-condition__segment")
    expected = [100 * counts.get(s, 0) / sum(counts.values()) if sum(counts.values()) else 0 for s in (F, S, N)]
    assert [float(n.style["width"].rstrip("%")) for n in segments] == pytest.approx(expected)


@pytest.mark.parametrize("plants,transformers,devices", [(3, 7, 19), (0, 0, 0), (12, 46, 321)])
def test_inventory_uses_supplied_hierarchy_counts(plants, transformers, devices):
    block = fleet_inventory(plants, transformers, devices)
    assert [text_of(n) for n in find_by_exact_class(block, "fleet-condition__stat-value")] == list(map(str, (plants, transformers, devices)))
    assert [text_of(n) for n in find_by_exact_class(block, "fleet-condition__stat-label")] == ["Plants", "Transformers", "RTL Devices"]
    assert "Monitored assets in your current scope" in text_of(block)
    assert [text_of(n) for n in find_by_exact_class(block, "fleet-condition__stat-meta")] == ["Monitored"] * 3


def test_condition_copy_discloses_both_nonfresh_states_without_scores():
    rendered = text_of(fleet_condition_summary({F: 5, S: 2, N: 4}))
    assert "6 of 11 monitored RTLs require attention" in rendered
    assert condition_wording({F: 5, S: 2, N: 4})[2] == "Of 11 monitored RTLs, 2 are stale, 4 have no data and 5 are fresh."
    assert not any(term in rendered.lower() for term in ("healthy", "critical", "risk", "score", "probability"))


def test_cta_only_for_attention_and_uses_existing_anchor():
    assert links(fleet_condition_summary({S: 2})) == [("View needs attention →", "#needs-attention")]
    assert find_by_id(layout(), "needs-attention") is not None
    assert not links(fleet_condition_summary({F: 2}))
    assert not links(fleet_condition_summary({}))


def test_three_existing_slots_and_lower_sections_keep_ids_and_reading_order():
    page = layout()
    ids = [n.id for n in walk(page) if getattr(n, "id", None)]
    assert len(ids) == len(set(ids))
    for component_id in ("fleet-systemic-state", "fleet-health-distribution", "fleet-kpis", "needs-attention", "fleet-plants", "plants-table", "admin-summary"):
        assert component_id in ids
    assert ids.index("fleet-systemic-state") < ids.index("needs-attention") < ids.index("fleet-plants") < ids.index("admin-summary")
    assert "Operating status" not in text_of(page)
    assert links(page)[-1] == ("Refresh", "/plants")


@pytest.fixture
def overview_callback():
    class Capture:
        def __init__(self):
            self.functions = {}
            self.specs = {}

        def callback(self, *args, **kwargs):
            def register(fn):
                self.functions[fn.__name__] = fn
                self.specs[fn.__name__] = (args, kwargs)
                return fn
            return register

    capture = Capture()
    listings.register(capture)
    return capture.functions["populate_overview"], capture.specs["populate_overview"]


def test_listing_callback_ids_inputs_and_state_are_unchanged(overview_callback):
    from dash import Input, Output, State
    _fn, (args, kwargs) = overview_callback
    assert [(a.component_id, a.component_property) for a in args if isinstance(a, Output)] == [
        ("plants-table", "data"), ("plants-table", "columns"), ("plants-error", "children"),
        ("fleet-kpis", "children"), ("fleet-health-distribution", "children"),
        ("fleet-systemic-state", "children"), ("admin-summary", "children"),
        ("needs-attention", "children"), ("fleet-subtitle", "children"), ("fleet-refreshed", "children"),
    ]
    assert [(a.component_id, a.component_property) for a in args if isinstance(a, Input)] == [("page-context", "data")]
    assert [(a.component_id, a.component_property) for a in args if isinstance(a, State)] == [("auth-store", "data")]
    assert kwargs == {"prevent_initial_call": True}


def test_existing_single_service_snapshot_feeds_layer2_and_lower_outputs(monkeypatch, overview_callback):
    now = datetime.now(timezone.utc)
    plant = SimpleNamespace(plant_id="p1", name="Test Plant", country="Test", primary_fuel="Gas", capacity_mw=400)
    rows = [SimpleNamespace(plant_id="p1", transformer_id="t1", device_id=f"d{i}", metric="temperature", reading_ts=ts)
            for i, ts in enumerate((now, now, now - timedelta(days=20), None))]
    health = fleet_health_from_rows(rows, now)
    read_plants = Mock(return_value=[plant])
    read_counts = Mock(return_value={"p1": (3, 4)})
    read_health = Mock(return_value=health)
    monkeypatch.setattr(listings.hierarchy_service, "list_plants", read_plants)
    monkeypatch.setattr(listings.hierarchy_service, "get_plant_hierarchy_counts", read_counts)
    monkeypatch.setattr(listings.monitoring_service, "get_fleet_health", read_health)
    monkeypatch.setattr(listings, "scope_from_session", lambda _: UNRESTRICTED)
    # The stale/no-data rows above make hierarchy_code_index fetch display
    # codes; without this the callback reaches the real database and this
    # test stops being a "not db" test.
    monkeypatch.setattr(listings.hierarchy_service, "list_all_devices", Mock(return_value=[]))
    admin = html.Div("Existing Administration / Unassigned RTLs")
    monkeypatch.setattr(listings, "administration_section", lambda *_: admin)
    fn, _spec = overview_callback
    result = fn({"route": "overview"}, None)
    assert result[2] is None
    assert len(result) == 10
    assert result[0] == listings.sort_plant_rows_exception_first(listings.build_plant_rows([plant], {"p1": (3, 4)}, health))
    assert text_of(result[3]) == text_of(fleet_inventory(1, 3, 4))
    assert text_of(result[4]) == text_of(data_freshness(health.counts))
    assert text_of(result[5]) == text_of(fleet_condition_panels(health.counts))
    assert "Fleet-wide freshness issue" not in text_of(result)
    assert result[6] is admin
    assert "Needs attention" in text_of(result[7])
    read_plants.assert_called_once_with(scope=UNRESTRICTED)
    read_counts.assert_called_once_with(scope=UNRESTRICTED)
    read_health.assert_called_once()
    assert read_health.call_args.kwargs == {"scope": UNRESTRICTED}
    assert result[9] == listings.format_render_stamp(read_health.call_args.args[0])


def test_query_failure_remains_an_error_not_a_fabricated_empty_fleet(monkeypatch, overview_callback):
    monkeypatch.setattr(listings.hierarchy_service, "list_plants", Mock(side_effect=RuntimeError("test unavailable")))
    fn, _spec = overview_callback
    result = fn({"route": "overview"}, None)
    assert result[2] is not None
    assert result[3:6] == (None, None, None)


def test_other_routes_remain_no_update(overview_callback):
    fn, _spec = overview_callback
    assert fn({"route": "plant"}, None) == (no_update,) * 10


def test_layer2_styles_are_scoped_and_use_existing_tokens():
    css = (Path(__file__).resolve().parents[1] / "assets/app.css").read_text(encoding="utf-8")
    layer2 = css.split("/* ---------- Layer 2")[1].split("/* ---------- Fleet Data Health")[0]
    assert "minmax(0, 1fr) minmax(0, 1fr) minmax(0, 1.06fr)" in layer2
    assert "--state-fresh-text" in layer2 and "--state-stale-text" in layer2 and "--state-none-text" in layer2
    assert "tabular-nums" in layer2
    assert "gradient" not in layer2
    assert ".app-shell" not in layer2 and ".needs-attention" not in layer2


@pytest.mark.parametrize("counts,expected", [
    ({F: 17, S: 5, N: 3}, 68.0),
    ({F: 4, S: 0, N: 0}, 100.0),
    ({F: 0, S: 9, N: 0}, 0.0),
    ({F: 0, S: 0, N: 9}, 0.0),
    ({}, 0.0),
    ({F: 1, S: 2, N: 0}, 100 / 3),
])
def test_fresh_data_coverage_uses_fresh_only_with_exact_arc(counts, expected):
    block = fresh_data_coverage(counts)
    rendered = text_of(block)
    assert "Fresh Data Coverage" in rendered
    assert "RTLs with all monitored metrics within the freshness threshold" in rendered
    assert f"{counts.get(F, 0)} of {sum(counts.values())} monitored RTLs have fresh data" in rendered
    assert f"{expected:.1f}%" in rendered
    arcs = find_by_exact_class(block, "fleet-condition__arc")
    assert 'stroke-dasharray="100 100"' in unquote(arcs[0].style["maskImage"])
    mask = unquote(arcs[1].style["maskImage"])
    assert 'M 10 80 A 70 70 0 0 1 150 80' in mask
    assert float(mask.split('stroke-dasharray="')[1].split()[0]) == pytest.approx(expected)
    assert not any(word in rendered.lower() for word in ("healthy", "online", "reporting", "good"))


def test_freshness_threshold_copy_uses_current_configuration(monkeypatch):
    import components.fleet_condition as component
    monkeypatch.setattr(component, "monitoring", SimpleNamespace(stale_after_minutes=135))
    rendered = text_of(data_freshness({F: 3, S: 1, N: 1}))
    assert "All metrics ≤ 135 min" in rendered
    assert "At least one metric > 135 min" in rendered
    assert "At least one metric has no reading" in rendered


def test_four_sections_are_composed_from_existing_slots():
    page = layout()
    find_by_id(page, "fleet-systemic-state").children = fleet_condition_panels({F: 3, S: 2, N: 1})
    find_by_id(page, "fleet-health-distribution").children = data_freshness({F: 3, S: 2, N: 1})
    find_by_id(page, "fleet-kpis").children = fleet_inventory(2, 3, 6)
    headings = [text_of(n) for n in walk(page) if type(n).__name__ == "H3"]
    assert headings == ["Fleet Condition Summary", "Fresh Data Coverage", "Data Freshness", "Fleet Inventory"]


def test_partial_metric_readings_do_not_count_as_fresh_coverage():
    now = datetime.now(timezone.utc)
    rows = [SimpleNamespace(plant_id="p", transformer_id="t", device_id="d", metric=metric, reading_ts=ts)
            for metric, ts in (("temperature", now), ("voltage", None))]
    health = fleet_health_from_rows(rows, now)
    assert health.counts[N] == health.device_count == 1
    assert "0 of 1 monitored RTLs have fresh data" in text_of(fresh_data_coverage(health.counts))
    assert "1 of 1 monitored RTLs require attention" in text_of(fleet_condition_summary(health.counts))


@pytest.mark.parametrize("counts", [{F: 7, S: 2, N: 1}, {F: 10}, {S: 10}, {N: 10}, {}])
def test_attention_and_coverage_reconcile_to_same_population(counts):
    total = sum(counts.values())
    affected = counts.get(S, 0) + counts.get(N, 0)
    assert counts.get(F, 0) + affected == total
    assert f"{affected} of {total} monitored RTLs" in text_of(fleet_condition_summary(counts))
    assert f"{counts.get(F, 0)} of {total} monitored RTLs" in text_of(fresh_data_coverage(counts))
    assert f"{total} monitored RTLs" in text_of(data_freshness(counts))


@pytest.mark.parametrize("counts", [{F: 17, S: 5, N: 3}, {F: 8}, {S: 8}, {N: 8}, {}])
def test_donut_details_match_authoritative_freshness_distribution(counts):
    summary = fleet_condition_summary(counts)
    rows = find_by_exact_class(summary, "fleet-condition__detail-row")
    distribution = data_freshness(counts)
    assert [text_of(row.children[0]) for row in rows] == ["Fresh", "Stale", "No Data"]
    assert [text_of(row.children[1]) for row in rows] == [text_of(n) for n in find_by_exact_class(distribution, "fleet-condition__stat-value")]
    assert [text_of(row.children[2]) for row in rows] == [text_of(n) for n in find_by_exact_class(distribution, "fleet-condition__stat-meta")]
    assert f"of {sum(counts.values())}" in text_of(find_by_exact_class(summary, "fleet-condition__center-total"))
    total = sum(counts.values())
    affected = counts.get(S, 0) + counts.get(N, 0)
    insight = text_of(find_by_exact_class(summary, "fleet-condition__insight"))
    assert insight == (f"{100 * affected / total:.1f}% of monitored RTLs require attention" if total else "No monitored RTLs to assess")


@pytest.mark.parametrize("counts", [{F: 17, S: 5, N: 3}, {F: 8}, {S: 8}, {N: 8}, {}])
def test_coverage_details_use_same_population_and_include_missing_data(counts):
    block = fresh_data_coverage(counts)
    details = find_by_exact_class(block, "fleet-condition__coverage-details")[0]
    values = [int(text_of(n)) for n in find_by_exact_class(details, "fleet-condition__detail-count")]
    assert values == [counts.get(F, 0), counts.get(S, 0) + counts.get(N, 0)]
    assert sum(values) == sum(counts.values())
    assert "Outside freshness threshold" in text_of(details)
    assert "Includes Stale and No Data" in text_of(details)


def test_coverage_metadata_uses_same_config_as_freshness(monkeypatch):
    import components.fleet_condition as component
    monkeypatch.setattr(component, "monitoring", SimpleNamespace(stale_after_minutes=135))
    metadata = text_of(find_by_exact_class(fresh_data_coverage({F: 2}), "fleet-condition__metadata"))
    assert "Freshness target ≤ 135 min" in metadata
    assert "Evaluation scope All monitored metrics must be fresh" in metadata
    assert "All metrics ≤ 135 min" in text_of(data_freshness({F: 2}))


def test_coverage_does_not_use_historical_reporting_count():
    import inspect
    assert "reporting_count" not in inspect.getsource(fresh_data_coverage)


def test_chart_zones_share_fixed_top_height_and_number_anchor():
    css = (Path(__file__).resolve().parents[1] / "assets/app.css").read_text(encoding="utf-8")
    stage = css.split(".fleet-condition__chart-stage {")[1].split("}")[0]
    assert "align-items: flex-start" in stage
    assert "height: 176px" in stage and "flex: 0 0 176px" in stage
    for selector in (".fleet-condition__center", ".fleet-condition__gauge-value"):
        rule = css.split(selector + " {")[1].split("}")[0]
        assert "inset: var(--fleet-number-top) 0 auto" in rule


def test_chart_typography_uses_scoped_tokens_and_bundled_fonts():
    root = Path(__file__).resolve().parents[1]
    css = (root / "assets/app.css").read_text(encoding="utf-8")
    scope = css.split(".fleet-condition__summary,\n.fleet-condition__coverage {")[1].split("}")[0]
    # The family is named once, in --font-ui, and this scope takes it from
    # there. Restating the stack here is what let the chart face drift from
    # the application face; see tests/test_typography.py.
    assert "--font-fleet-chart: var(--font-ui)" in scope
    assert "--fs-fleet-chart-value: 2.5rem" in scope
    assert "--fs-meta: var(--fs-fleet-chart-caption)" in scope
    number = css.split(".fleet-condition__number {")[1].split("}")[0]
    assert "font-size: var(--fs-fleet-chart-value)" in number
    assert "font-weight: 600" in number
    assert "lining-nums tabular-nums" in number
    for selector in (".fleet-condition__center", ".fleet-condition__gauge-value"):
        rule = css.split(selector + " {")[1].split("}")[0]
        assert "font-size: var(--fs-fleet-chart-label)" in rule
        assert "color: var(--color-text)" in rule
    for weight in ("Regular", "SemiBold"):
        relative = f"fonts/ibm-plex-sans/IBMPlexSans-{weight}.woff2"
        assert f'url("{relative}") format("woff2")' in css
        assert (root / "assets" / relative).read_bytes()[:4] == b"wOF2"
    assert "SIL OPEN FONT LICENSE Version 1.1" in (root / "assets/fonts/ibm-plex-sans/LICENSE.txt").read_text(encoding="utf-8")


def test_gauge_value_has_overflow_guard_against_arc_collision():
    """The gauge's percentage line sits closer to the semicircle's stroke
    than the ring's number does (measured ~6px margin at "100.0%" vs ~89px
    for the ring's number, both sharing .fleet-condition__number). A wider
    future value (locale, larger font token) must ellipsis rather than
    visually collide with the arc, so this line needs its own max-width
    guard the ring's number does not need.
    """
    root = Path(__file__).resolve().parents[1]
    css = (root / "assets/app.css").read_text(encoding="utf-8")
    rule = css.split(".fleet-condition__gauge-value .fleet-condition__number {")[1].split("}")[0]
    assert "max-width" in rule
    assert "overflow: hidden" in rule
    assert "text-overflow: ellipsis" in rule


def test_gauge_value_uses_its_own_smaller_font_size_than_the_ring():
    """The gauge's percentage line is set smaller than the ring's number
    (--fs-fleet-chart-value, 2.5rem) — requested to give it more visual
    breathing room from the arc. The ring's own number is untouched.
    """
    root = Path(__file__).resolve().parents[1]
    css = (root / "assets/app.css").read_text(encoding="utf-8")
    scope = css.split(".fleet-condition__summary,\n.fleet-condition__coverage {")[1].split("}")[0]
    assert "--fs-fleet-gauge-value:" in scope
    rule = css.split(".fleet-condition__gauge-value .fleet-condition__number {")[1].split("}")[0]
    assert "font-size: var(--fs-fleet-gauge-value)" in rule


@pytest.mark.parametrize("counts", [{}, {S: 120}, {F: 9999}, {S: 9999}])
def test_donut_center_has_three_lines_with_complete_denominator(counts):
    center = find_by_exact_class(fleet_condition_summary(counts), "fleet-condition__center")[0]
    assert len(center.children) == 3
    assert text_of(center.children[1]) == "RTLs require attention"
    assert text_of(center.children[2]) == f"of {sum(counts.values())} monitored RTLs"
