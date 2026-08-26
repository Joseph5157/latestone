"""Metric workspace (ENT-3) — eight merged cells, one interaction authority.

Consolidates the former snapshot-strip and Quick-Trends contracts: each cell
carries label, freshness, latest value, direction versus period start, and the
trend shape — and is exactly ONE link that promotes the metric while preserving
metric/period/custom-bounds URL state.
"""
from __future__ import annotations

import pathlib
import re
from datetime import datetime, timedelta, timezone

from components.metric_workspace import (
    EMPTY_PERIOD_TEXT,
    WORKSPACE_CHART_CONFIG,
    direction_text,
    metric_cell,
    metric_workspace,
)
from config.metrics import get_metric, ordered_metrics
from pages import device_dashboard
from services.monitoring_service import (
    DeltaResult, DeltaStatus, Freshness, MetricView, MonitoringCondition, Reading,
    _build_metric_view,
    quick_trend_bars,
)
from tests.dash_tree import find_by_class, find_by_id, find_by_exact_class, links, text_of, walk

T0 = datetime(2026, 8, 9, tzinfo=timezone.utc)

CSS_TEXT = (
    pathlib.Path(__file__).resolve().parent.parent / "assets" / "app.css"
).read_text(encoding="utf-8")


def _views(with_data=True):
    out = {}
    for m in ordered_metrics():
        series = (
            [Reading(T0 + timedelta(minutes=30 * i), 10.0 + i) for i in range(4)]
            if with_data else []
        )
        out[m.key] = MetricView(
            metric=m, current=10.0, minimum=None, maximum=None, average=None,
            period_change=None, period_change_status=DeltaStatus.OK, series=series,
            last_updated=T0, freshness=Freshness.FRESH,
            condition=MonitoringCondition.UNKNOWN, has_data=with_data,
            change=DeltaResult(1.0, DeltaStatus.OK),
        )
    return out


def _workspace(views, *args, **kwargs):
    """Wraps `metric_workspace`, computing the prepared-bars dict the way
    `callbacks.device.refresh_device_dashboard` does."""
    bars = {key: quick_trend_bars(v) for key, v in views.items()}
    return metric_workspace(views, bars, *args, **kwargs)


def _cells(ws):
    return find_by_exact_class(ws, "metric-cell")


def _figures(ws):
    return [n for n in walk(ws) if getattr(n, "figure", None) is not None]


def _view(key, change: DeltaResult = DeltaResult(1.0, DeltaStatus.OK), series=()):
    return MetricView(
        metric=get_metric(key), current=10.0, minimum=None, maximum=None, average=None,
        period_change=None, period_change_status=DeltaStatus.OK, series=list(series),
        last_updated=T0, freshness=Freshness.FRESH,
        condition=MonitoringCondition.UNKNOWN, has_data=True, change=change,
    )


# ---------------------------------------------------------------------------
# Shape — always eight, always registry order, positions never reflow
# ---------------------------------------------------------------------------


class TestWorkspaceShape:
    def test_renders_one_cell_per_configured_metric(self):
        ws = _workspace(_views(), "temperature", "dev-1")
        assert len(_cells(ws)) == len(ordered_metrics())

    def test_cells_follow_display_order_and_do_not_reflow(self):
        """Fixed positions are the point: cell location becomes muscle memory,
        so it must not depend on which metric is selected."""
        expected = [m.label for m in ordered_metrics()]
        for active in ("temperature", "energy", "power_factor"):
            ws = _workspace(_views(), active, "dev-1")
            labels = [e.children for e in find_by_class(ws, "metric-cell__label")]
            assert labels == expected


# ---------------------------------------------------------------------------
# Merged content — one cell carries everything the two old surfaces split
# ---------------------------------------------------------------------------


class TestMergedContent:
    def test_every_cell_carries_label_value_direction_badge_and_figure(self):
        ws = _workspace(_views(), "temperature", "dev-1")
        assert len(find_by_class(ws, "metric-cell__label")) == 8
        assert len(find_by_class(ws, "metric-cell__value")) == 8
        assert len(find_by_class(ws, "metric-cell__direction")) == 8
        assert len(_figures(ws)) == 8
        badges = [
            e for e in walk(ws)
            if getattr(e, "className", None)
            and "freshness-badge" in str(e.className)
        ]
        assert len(badges) == 8

    def test_no_condition_slot_anywhere(self):
        """D2 gate decision: the permanently-empty condition slot is gone, so
        nobody can later populate it with invented severity semantics."""
        ws = _workspace(_views(), "temperature", "dev-1")
        assert not find_by_class(ws, "snapshot-tile__condition")
        assert not find_by_class(ws, "metric-cell__condition")

    def test_exactly_one_link_per_cell_single_interaction_authority(self):
        """D5 constraint: one clickable unit per metric. Value and sparkline
        are never separate targets."""
        ws = _workspace(_views(), "temperature", "dev-1")
        assert len(links(ws)) == len(ordered_metrics())

    def test_kpi_detail_vocabulary_stays_out_of_the_cells(self):
        """The workspace is a fleet of signals, not eight miniature dashboards;
        Current/Min/Average belong to the KPI row of the selected metric."""
        ws = _workspace(_views(), "temperature", "dev-1")
        for word in ("Minimum", "Maximum", "Average"):
            assert word not in text_of(ws)


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------


class TestSelection:
    def test_exactly_one_cell_is_selected(self):
        ws = _workspace(_views(), "voltage", "dev-1")
        selected = [c for c in _cells(ws) if "metric-cell--selected" in c.className]
        assert len(selected) == 1

    def test_selection_never_borrows_the_warning_or_freshness_classes(self):
        """"The one you are looking at" and "the one with a problem" are
        different statements and must not share styling."""
        ws = _workspace(_views(), "voltage", "dev-1")
        selected = next(
            c for c in _cells(ws) if "metric-cell--selected" in c.className
        )
        assert "warning" not in selected.className
        assert "freshness" not in selected.className
        assert "stale" not in selected.className


# ---------------------------------------------------------------------------
# Promotion — URL state survives
# ---------------------------------------------------------------------------


class TestPromotion:
    def test_every_cell_links_to_its_metric_preserving_period(self):
        ws = _workspace(_views(), "temperature", "dev-1", period="7d")
        hrefs = [href for _label, href in links(ws)]
        assert len(hrefs) == len(ordered_metrics())
        assert all("period=7d" in h for h in hrefs)
        assert any("metric=energy" in h for h in hrefs)

    def test_custom_bounds_survive_promotion(self):
        ws = _workspace(
            _views(), "temperature", "dev-1",
            period="custom", custom_start="2026-08-01", custom_end="2026-08-03",
        )
        hrefs = [href for _label, href in links(ws)]
        assert all("start=2026-08-01" in h and "end=2026-08-03" in h for h in hrefs)

    def test_links_point_at_the_same_device(self):
        ws = _workspace(_views(), "temperature", "dev-1")
        assert all("dev-1" in href for _label, href in links(ws))


# ---------------------------------------------------------------------------
# Empty states and chart types
# ---------------------------------------------------------------------------


class TestEmptyAndTypes:
    def test_empty_metric_keeps_full_cell_height(self):
        """A collapsed cell reads as a layout fault rather than absent data."""
        ws = _workspace(_views(with_data=False), "temperature", "dev-1")
        assert all(g.figure.layout.height for g in _figures(ws))

    def test_empty_metric_shares_the_primary_chart_phrase(self):
        """One phrase for one condition across cells and primary chart."""
        ws = _workspace(_views(with_data=False), "temperature", "dev-1")
        texts = [a.text for g in _figures(ws) for a in g.figure.layout.annotations]
        assert texts and all(t == EMPTY_PERIOD_TEXT for t in texts)

    def test_energy_cell_is_a_bar_chart(self):
        ws = _workspace(_views(), "temperature", "dev-1")
        energy = _figures(ws)[-1]
        assert any(t.type == "bar" for t in energy.figure.data)

    def test_statistics_cells_are_line_charts(self):
        ws = _workspace(_views(), "temperature", "dev-1")
        voltage = _figures(ws)[1]
        assert any(t.type == "scatter" for t in voltage.figure.data)

    def test_hover_states_utc(self):
        ws = _workspace(_views(), "temperature", "dev-1")
        trace = _figures(ws)[0].figure.data[0]
        assert "UTC" in trace.hovertemplate

    def test_no_modebar_anywhere(self):
        """Eight more toolbars would compete with the primary chart."""
        assert WORKSPACE_CHART_CONFIG["displayModeBar"] is False


# ---------------------------------------------------------------------------
# Direction — neutral change versus the period start (D3)
# ---------------------------------------------------------------------------


class TestDirectionText:
    def test_a_rise_is_marked_up(self):
        text = direction_text(get_metric("voltage"), DeltaResult(0.31, DeltaStatus.OK))
        assert text.startswith("▲")

    def test_a_fall_is_marked_down(self):
        text = direction_text(get_metric("voltage"), DeltaResult(-0.31, DeltaStatus.OK))
        assert text.startswith("▼")

    def test_no_change_is_neither(self):
        text = direction_text(get_metric("voltage"), DeltaResult(0.0, DeltaStatus.OK))
        assert not text.startswith("▲")
        assert not text.startswith("▼")

    def test_unknown_change_shows_a_dash(self):
        assert direction_text(
            get_metric("energy"), DeltaResult(None, DeltaStatus.DISCONTINUITY)
        ) == "—"

    def test_insufficient_data_shows_a_dash_too(self):
        assert direction_text(
            get_metric("voltage"), DeltaResult(None, DeltaStatus.INSUFFICIENT_DATA)
        ) == "—"

    def test_value_carries_the_unit(self):
        text = direction_text(get_metric("voltage"), DeltaResult(0.31, DeltaStatus.OK))
        assert "kV" in text

    def test_a_fall_is_not_rendered_with_two_minus_signs(self):
        """The arrow carries the direction; the number must not repeat it."""
        text = direction_text(get_metric("voltage"), DeltaResult(-0.31, DeltaStatus.OK))
        assert text.count("-") + text.count("−") <= 1

    def test_every_cell_shows_a_direction_line_even_when_unknown(self):
        """An absent line would make cells step; the workspace feeds the §6.8
        chart-top budget."""
        views = {"voltage": _view(
            "voltage", DeltaResult(None, DeltaStatus.INSUFFICIENT_DATA)
        )}
        ws = _workspace(views, "voltage", "dev-1")
        assert find_by_class(ws, "metric-cell__direction")


class TestServiceAlwaysPopulatesChange:
    """`change` has a safe default so test factories need not restate it. This
    guards production against ever relying on that default."""

    def test_statistics_metric_gets_a_computed_change(self):
        series = [Reading(T0, 10.0), Reading(T0 + timedelta(minutes=30), 12.5)]
        view = _build_metric_view(get_metric("voltage"), None, series, T0)
        assert view.change == DeltaResult(2.5, DeltaStatus.OK)

    def test_cumulative_metric_reuses_the_period_delta_rules(self):
        series = [Reading(T0, 100.0), Reading(T0 + timedelta(minutes=30), 5.0)]
        view = _build_metric_view(get_metric("energy"), None, series, T0)
        assert view.change.status is DeltaStatus.DISCONTINUITY

    def test_single_reading_yields_insufficient_data(self):
        view = _build_metric_view(get_metric("voltage"), None, [Reading(T0, 10.0)], T0)
        assert view.change.status is DeltaStatus.INSUFFICIENT_DATA


# ---------------------------------------------------------------------------
# Page composition — the merge actually happened in the layout
# ---------------------------------------------------------------------------


class TestPageComposition:
    def test_workspace_slot_present_once(self):
        layout = device_dashboard.layout()
        assert find_by_id(layout, "metric-workspace") is not None
        ids = [getattr(n, "id", None) for n in walk(layout)]
        assert ids.count("metric-workspace") == 1

    def test_old_surfaces_removed_from_the_layout(self):
        """Merge functionality, don't merely restyle two redundant components."""
        layout = device_dashboard.layout()
        assert not find_by_id(layout, "snapshot-strip")
        assert not find_by_id(layout, "trend-grid")

    def test_quick_trends_section_gone(self):
        layout = device_dashboard.layout()
        sections = [
            text_of(s) for s in find_by_class(layout, "device-section")
        ]
        joined = " ".join(sections)
        assert "Quick trends" not in joined
        assert "Supporting metrics" not in joined

    def test_reading_order_workspace_then_controls_then_chart_then_history(self):
        layout = device_dashboard.layout()
        ids = [getattr(n, "id", None) for n in walk(layout)]
        assert ids.index("metric-workspace") < ids.index("kpi-row-container")
        assert ids.index("kpi-row-container") < ids.index("metric-chart")
        assert ids.index("metric-chart") < ids.index("readings-table")

    def test_one_instruction_line_per_interactive_region(self):
        """Hint budget: the promotion instruction appears exactly once and the
        retired duplicated hints are gone."""
        layout = device_dashboard.layout()
        text = text_of(layout)
        assert text.count("Select a metric to promote it to the main chart.") == 1
        assert "Select a tile" not in text


# ---------------------------------------------------------------------------
# CSS source guards
# ---------------------------------------------------------------------------


class TestWorkspaceStyling:
    """Source guards only. Computed widths are verified in a browser per
    spec section 6.9, because a rule present in a stylesheet is not a rule in
    effect - four defects in this codebase have taken that exact shape."""

    def test_multi_column_on_desktop(self):
        assert re.search(
            r"\.metric-workspace\s*\{[^}]*grid-template-columns:\s*repeat\(2,",
            CSS_TEXT, re.S,
        )

    def test_four_columns_grouped_at_wide_desktop(self):
        assert re.search(
            r"@media \(min-width: 1200px\)\s*\{[^}]*\.page--device-dashboard \.metric-workspace"
            r"[^}]*grid-template-columns:\s*repeat\(4,",
            CSS_TEXT, re.S,
        )

    def test_mobile_stacks_single_column_d1(self):
        """D1 gate decision: vertical scan at ≤640px, no hidden off-screen
        cells — deliberately NOT the old horizontal scroll-snap."""
        assert re.search(
            r"@media \(max-width: 640px\)\s*\{\s*\.metric-workspace\s*\{[^}]*"
            r"repeat\(1,",
            CSS_TEXT, re.S,
        )

    def test_no_scroll_snap_carousel_remains_for_the_workspace(self):
        """The retired strip scrolled horizontally; the workspace must not."""
        workspace_css = CSS_TEXT.split("Metric Workspace")[-1]
        assert "scroll-snap" not in workspace_css
        assert "overflow-x: auto" not in workspace_css.split("@media")[0]

    def test_selection_styling_uses_the_accent_token(self):
        match = re.search(r"\.metric-cell--selected\s*\{([^}]*)\}", CSS_TEXT, re.S)
        assert match and "--color-accent" in match.group(1)

    def test_selection_styling_never_borrows_the_warning_palette(self):
        match = re.search(r"\.metric-cell--selected\s*\{([^}]*)\}", CSS_TEXT, re.S)
        for forbidden in ("--color-warning", "--color-danger", "--color-stale"):
            assert forbidden not in match.group(1)

    def test_the_cell_link_carries_no_underline(self):
        """The whole cell is an anchor; underlining it would underline a chart."""
        match = re.search(r"\.metric-cell__link\s*\{([^}]*)\}", CSS_TEXT, re.S)
        assert match and "text-decoration: none" in match.group(1)


class TestDirectionLineCannotGrowTheCell:
    """DEF-2 regression guard, carried over from the strip era.

    The direction line had no CSS rule at all, so it inherited
    `white-space: normal`. On a 7-day energy delta the value read
    "▲ +428.0 MWh", wrapped to two lines, and because the surface is a grid
    that one wrapped cell stretched its row and pushed the primary chart past
    the section 6.8 budget of 420 px.

    It appeared only at some periods, which is why the Task 7 check at the
    default 24h missed it."""

    def _block(self):
        match = re.search(r"\.metric-cell__direction\s*\{([^}]*)\}", CSS_TEXT, re.S)
        assert match, "the direction line must carry an explicit rule"
        return match.group(1)

    def test_the_line_never_wraps(self):
        assert "white-space: nowrap" in self._block()

    def test_the_line_has_a_fixed_height(self):
        """A value-dependent height makes the chart-top budget value-dependent."""
        assert re.search(r"\bheight:\s*\d+px", self._block())

    def test_overflow_is_revealed_not_clipped_silently(self):
        assert "text-overflow: ellipsis" in self._block()
