"""RTL-UID-DETAIL-01 — the `/rtls/<uid>` page, its callback and the Fleet link.

Covers what the operator actually sees: client-facing wording, explicit
missing states instead of raw nulls, the three history windows, and the
absence of everything this source cannot support — Online/Offline, lifecycle
state, and the seven electrical metrics.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from dash import html

from callbacks import rtl_detail as cb
from components import rtl_detail as ui
from components import rtl_fleet
from pages import rtl_detail as page
from routes import rtl_detail_href
from services import rtl_detail_service as detail
from services.rtl_fleet_service import (
    HierarchyContext,
    HierarchyState,
    RTLFleetRow,
    TemperatureState,
)
from tests.dash_tree import find_by_class, links, text_of, walk

A_UID = 29042
LAST = datetime(2022, 4, 13, 5, 54)


def _detail(**overrides) -> detail.RTLDetail:
    base = dict(
        device_uid=A_UID,
        temperature_state=TemperatureState.VALUE,
        temperature=Decimal("35.5"),
        ambiguous_values=(),
        last_reported=LAST,
        transformer_codes=("AA12",),
        hierarchy_state=HierarchyState.AVAILABLE,
        hierarchy=HierarchyContext("Distribution", "North", "Sector 4", "CNC 2", "Feeder 7"),
    )
    base.update(overrides)
    return detail.RTLDetail(**base)


def _words(node_or_text) -> set[str]:
    import re

    text = node_or_text if isinstance(node_or_text, str) else text_of(node_or_text)
    return set(re.findall(r"[A-Za-z]+", text))


def _code_names(module) -> set[str]:
    """Identifiers the module's CODE mentions — docstrings/comments excluded.

    These modules document precisely what they deliberately do NOT use (the
    freshness badge, the metric selector, the shared missing-state literals),
    so a raw-source scan matches the sentence saying so. What matters is what
    the code reaches for.
    """
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(module))
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


def _code_strings(module) -> set[str]:
    """Every string literal in the module's code, docstrings excluded."""
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(module))
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef)):
            doc = ast.get_docstring(node, clean=False)
            if doc is not None:
                docstrings.add(doc)
    return {
        n.value for n in ast.walk(tree)
        if isinstance(n, ast.Constant) and isinstance(n.value, str)
        and n.value not in docstrings
    }


# ---------------------------------------------------------------------------
# Page shell and wording
# ---------------------------------------------------------------------------


class TestPageShell:
    def test_the_layout_takes_the_uid_and_names_it(self):
        text = text_of(page.layout(A_UID))
        assert "RTL Details" in text
        assert f"RTL UID {A_UID}" in text

    def test_the_breadcrumb_is_client_facing(self):
        """`Registered RTLs > RTL 29042` — never `Plants > Device 29042`."""
        crumb = find_by_class(page.layout(A_UID), "header__breadcrumb")
        assert len(crumb) == 1
        text = text_of(crumb[0])
        assert "Registered RTLs" in text
        assert f"RTL {A_UID}" in text

    def test_the_breadcrumb_links_back_to_the_registered_directory(self):
        # RTL-LIST-ROUTE-01: the canonical list address.
        assert ("Registered RTLs", "/rtls") in links(page.layout(A_UID))

    @pytest.mark.parametrize("word", ["Plant", "Plants", "Device", "Devices"])
    def test_no_synthetic_vocabulary_appears(self, word):
        assert word not in _words(page.layout(A_UID))

    def test_the_page_performs_no_queries(self):
        """Layout is pure; the callback owns every read (same contract as
        the Fleet page)."""
        import ast
        import inspect

        names = {
            n.attr for n in ast.walk(ast.parse(inspect.getsource(page)))
            if isinstance(n, ast.Attribute)
        }
        assert not {n for n in names if n.startswith("get_")}

    def test_the_three_history_windows_are_offered(self):
        """The labels live in the control's `options` prop, not in its
        children, so they are read from the component rather than the text."""
        from tests.dash_tree import find_by_id

        control = find_by_id(page.layout(A_UID), page.WINDOW_ID)
        assert [o["label"] for o in control.options] == [
            w.label for w in detail.HISTORY_WINDOWS
        ]
        assert [o["value"] for o in control.options] == ["24h", "7d", "30d"]
        assert control.value == detail.DEFAULT_WINDOW_KEY


# ---------------------------------------------------------------------------
# Summary and context rendering
# ---------------------------------------------------------------------------


class TestSummaryRendering:
    def test_a_value_reading_shows_the_source_temperature(self):
        text = text_of(ui.summary(_detail()))
        assert "35.5 °C" in text

    def test_the_last_reading_is_the_naive_source_time_labelled_sast(self):
        text = text_of(ui.summary(_detail()))
        assert "13 Apr 2022 05:54 SAST" in text

    def test_an_ambiguous_latest_value_is_marked_not_resolved(self):
        text = text_of(ui.summary(_detail(
            temperature_state=TemperatureState.AMBIGUOUS,
            temperature=None,
            ambiguous_values=(Decimal("21.0"), Decimal("48.0")),
        )))
        assert rtl_fleet.AMBIGUOUS in text
        assert "21.0 °C" in text and "48.0 °C" in text

    def test_no_temperature_is_stated_in_words(self):
        text = text_of(ui.summary(_detail(
            temperature_state=TemperatureState.NO_DATA, temperature=None, last_reported=None,
        )))
        assert rtl_fleet.NO_TEMPERATURE in text

    def test_an_unmapped_rtl_says_so(self):
        text = text_of(ui.summary(_detail(
            transformer_codes=(), hierarchy_state=HierarchyState.NOT_MAPPED, hierarchy=None,
        )))
        assert rtl_fleet.NO_MAPPING in text

    def test_the_missing_state_wording_is_shared_with_the_fleet_page(self):
        """One vocabulary. A second copy is how two screens start disagreeing
        about what "no mapping" is called."""
        names = _code_names(ui)
        assert {"NO_TEMPERATURE", "NO_MAPPING", "NO_HIERARCHY", "AMBIGUOUS"} <= names
        # The literals themselves are defined once, in rtl_fleet.
        for literal in ("No temperature data", "No current transformer mapping",
                        "Hierarchy unavailable"):
            assert literal not in _code_strings(ui)

    @pytest.mark.parametrize("raw", ["None", "null", "NULL", "nan", "NaN", "undefined"])
    def test_no_raw_null_is_ever_rendered(self, raw):
        for rtl in (
            _detail(temperature_state=TemperatureState.NO_DATA, temperature=None, last_reported=None),
            _detail(transformer_codes=(), hierarchy_state=HierarchyState.NOT_MAPPED, hierarchy=None),
            _detail(hierarchy_state=HierarchyState.UNAVAILABLE, hierarchy=None),
        ):
            assert raw not in text_of(ui.summary(rtl))
            assert raw not in text_of(ui.network_context(rtl))


class TestNetworkContext:
    def test_the_client_hierarchy_levels_are_labelled(self):
        text = text_of(ui.network_context(_detail()))
        for level in ("Zone", "Sector", "CNC", "Feeder", "Transformer"):
            assert level in text

    def test_the_hierarchy_values_are_the_source_values(self):
        text = text_of(ui.network_context(_detail()))
        for value in ("North", "Sector 4", "CNC 2", "Feeder 7", "AA12"):
            assert value in text

    def test_a_mapped_rtl_without_hierarchy_says_hierarchy_unavailable(self):
        text = text_of(ui.network_context(
            _detail(hierarchy_state=HierarchyState.UNAVAILABLE, hierarchy=None)
        ))
        assert rtl_fleet.NO_HIERARCHY in text
        assert "AA12" in text  # the mapping itself is still a fact

    def test_an_unmapped_rtl_shows_no_invented_hierarchy(self):
        text = text_of(ui.network_context(_detail(
            transformer_codes=(), hierarchy_state=HierarchyState.NOT_MAPPED, hierarchy=None,
        )))
        assert rtl_fleet.NO_MAPPING in text

    def test_operating_unit_is_not_called_a_plant(self):
        assert "Plant" not in _words(ui.network_context(_detail()))


# ---------------------------------------------------------------------------
# What must never appear (gate sections 10 and 11)
# ---------------------------------------------------------------------------


class TestNoUnsupportedClaims:
    #: The seven metrics this source cannot support. "Current" is deliberately
    #: spelled as the electrical quantity with its unit: the bare word is a
    #: legitimate English adjective this page needs ("Current mapping", "No
    #: current transformer mapping"), and banning it would forbid the correct
    #: wording rather than the fabricated metric.
    UNSUPPORTED_METRICS = (
        "Voltage", "Current (A)", "Active Power", "Reactive Power",
        "Power Factor", "Frequency", "Energy",
    )
    STATE_WORDS = ("Online", "Offline", "Active", "Inactive", "Healthy", "Unhealthy")

    def _every_surface(self):
        rtl = _detail()
        return [
            page.layout(A_UID),
            ui.summary(rtl),
            ui.network_context(rtl),
            ui.history_panel(detail.RTLHistory(
                detail.HistoryStatus.DATA, A_UID, "24h", "24 hours",
                LAST - timedelta(hours=24), LAST, (),
            )),
        ]

    @pytest.mark.parametrize("metric", UNSUPPORTED_METRICS)
    def test_no_unsupported_metric_is_offered(self, metric):
        for node in self._every_surface():
            assert metric not in text_of(node)

    @pytest.mark.parametrize("word", STATE_WORDS)
    def test_no_communication_or_lifecycle_state_is_claimed(self, word):
        for node in self._every_surface():
            assert word not in _words(node)

    @pytest.mark.parametrize(
        "banned",
        ["metric_chart", "metric_workspace", "ordered_metrics", "METRIC_KEYS",
         "readings_table", "freshness_badge", "Freshness", "device_operations",
         "device_manage_drawer"],
    )
    def test_the_synthetic_device_dashboard_is_not_reused(self, banned):
        """Every one of these carries a claim this source cannot support."""
        assert banned not in _code_names(page)
        assert banned not in _code_names(ui)

    @pytest.mark.parametrize("banned", ["status_colors", "KIND_TONE", "TONE_CHART_COLOUR"])
    def test_no_status_colour_implies_health(self, banned):
        assert banned not in _code_names(page)
        assert banned not in _code_names(ui)


# ---------------------------------------------------------------------------
# History panel
# ---------------------------------------------------------------------------


class TestHistoryPanel:
    def _history(self, status, readings=(), start=None, end=None):
        return detail.RTLHistory(status, A_UID, "24h", "24 hours", start, end, readings)

    def test_a_populated_window_states_its_exact_range(self):
        start, end = LAST - timedelta(hours=24), LAST
        readings = (type("R", (), {"reading_time": LAST, "temperature": Decimal("30")})(),)
        text = text_of(ui.history_panel(self._history(
            detail.HistoryStatus.DATA, readings, start, end,
        )))
        assert "12 Apr 2022 05:54 SAST" in text
        assert "13 Apr 2022 05:54 SAST" in text

    def test_the_reading_count_is_singular_for_one(self):
        """A real RTL with exactly one reading in its 24-hour window read
        "1 readings" in the first browser run."""
        one = (type("R", (), {"reading_time": LAST, "temperature": Decimal("29")})(),)
        text = text_of(ui.history_panel(self._history(
            detail.HistoryStatus.DATA, one, LAST - timedelta(hours=24), LAST,
        )))
        assert "1 reading" in text
        assert "1 readings" not in text

    def test_the_reading_count_is_plural_for_more_than_one(self):
        many = tuple(
            type("R", (), {"reading_time": LAST - timedelta(hours=h), "temperature": Decimal(20)})()
            for h in (1, 0)
        )
        assert "2 readings" in text_of(ui.history_panel(self._history(
            detail.HistoryStatus.DATA, many, LAST - timedelta(hours=24), LAST,
        )))

    def test_an_empty_window_is_an_explicit_no_data_state(self):
        text = text_of(ui.history_panel(self._history(detail.HistoryStatus.NO_DATA)))
        assert "No temperature readings" in text

    def test_an_unavailable_source_is_not_shown_as_empty(self):
        text = text_of(ui.history_panel(self._history(detail.HistoryStatus.UNAVAILABLE)))
        assert "unavailable" in text.lower()
        assert "No temperature readings" not in text

    def test_the_chart_plots_only_temperature(self):
        """Ascending source time, as the service returns it — the component
        re-sorts nothing, so a re-ordering bug stays visible in the service."""
        readings = tuple(
            type("R", (), {
                "reading_time": LAST - timedelta(hours=h),
                "temperature": Decimal(20 + h),
            })()
            for h in (2, 1, 0)
        )
        figure = ui.history_figure(self._history(
            detail.HistoryStatus.DATA, readings, LAST - timedelta(hours=24), LAST,
        ))
        assert len(figure.data) == 1
        assert figure.data[0].y == (Decimal("22"), Decimal("21"), Decimal("20"))
        assert figure.data[0].x == (
            LAST - timedelta(hours=2), LAST - timedelta(hours=1), LAST,
        )

    def test_an_empty_figure_says_so_rather_than_drawing_nothing(self):
        figure = ui.history_figure(self._history(detail.HistoryStatus.NO_DATA))
        assert figure.layout.annotations
        assert not figure.data


# ---------------------------------------------------------------------------
# The callback
# ---------------------------------------------------------------------------


class TestCallback:
    def _context(self, uid=A_UID, route="rtl_detail"):
        return {"route": route, "rtl_uid": uid}

    def test_it_ignores_a_context_for_another_route(self):
        from dash import no_update

        result = cb.populate(
            {"route": "overview"}, "24h",
            fetch_detail=lambda *a, **k: pytest.fail("must not read"),
            fetch_history=lambda *a, **k: pytest.fail("must not read"),
        )
        assert all(part is no_update for part in result)

    def test_a_registered_uid_renders_the_detail(self):
        rtl = _detail()
        result = cb.populate(
            self._context(), "24h",
            fetch_detail=lambda uid, **k: detail.RTLDetailResult(
                detail.DetailStatus.DATA, uid, rtl),
            fetch_history=lambda uid, key, **k: detail.RTLHistory(
                detail.HistoryStatus.NO_DATA, uid, key, "24 hours"),
        )
        assert "35.5 °C" in text_of(result[0])

    def test_an_unregistered_uid_renders_not_found_and_no_facts(self):
        result = cb.populate(
            self._context(uid=41000), "24h",
            fetch_detail=lambda uid, **k: detail.RTLDetailResult(
                detail.DetailStatus.NOT_REGISTERED, uid),
            fetch_history=lambda *a, **k: pytest.fail("history must not be read"),
        )
        rendered = " ".join(text_of(part) for part in result if isinstance(part, object)
                            and not isinstance(part, dict) and part is not None)
        assert "not found" in rendered.lower()
        assert "°C" not in rendered

    def test_an_unregistered_uid_hides_the_history_control(self):
        """Offering 24h/7d/30d for an RTL that does not exist implies there
        is something behind it to select."""
        *_, style = cb.populate(
            self._context(uid=41000), "24h",
            fetch_detail=lambda uid, **k: detail.RTLDetailResult(
                detail.DetailStatus.NOT_REGISTERED, uid),
            fetch_history=lambda *a, **k: pytest.fail("history must not be read"),
        )
        assert style == page.HIDDEN_STYLE

    def test_a_registered_uid_shows_the_history_control(self):
        *_, style = cb.populate(
            self._context(), "24h",
            fetch_detail=lambda uid, **k: detail.RTLDetailResult(
                detail.DetailStatus.DATA, uid, _detail()),
            fetch_history=lambda uid, key, **k: detail.RTLHistory(
                detail.HistoryStatus.NO_DATA, uid, key, "24 hours"),
        )
        assert style == page.VISIBLE_STYLE

    def test_an_unavailable_source_hides_the_history_control(self):
        *_, style = cb.populate(
            self._context(), "24h",
            fetch_detail=lambda uid, **k: detail.RTLDetailResult(
                detail.DetailStatus.UNAVAILABLE, uid),
            fetch_history=lambda *a, **k: detail.RTLHistory(detail.HistoryStatus.UNAVAILABLE),
        )
        assert style == page.HIDDEN_STYLE

    def test_an_unavailable_source_is_distinguished_from_not_found(self):
        result = cb.populate(
            self._context(), "24h",
            fetch_detail=lambda uid, **k: detail.RTLDetailResult(
                detail.DetailStatus.UNAVAILABLE, uid),
            fetch_history=lambda *a, **k: detail.RTLHistory(detail.HistoryStatus.UNAVAILABLE),
        )
        rendered = " ".join(
            text_of(part) for part in result if part is not None and not isinstance(part, dict)
        )
        assert "unavailable" in rendered.lower()
        assert "not found" not in rendered.lower()

    @pytest.mark.parametrize("key", ["24h", "7d", "30d"])
    def test_the_selected_window_is_passed_through(self, key):
        seen = {}

        def fetch_history(uid, window_key, **k):
            seen["key"] = window_key
            return detail.RTLHistory(detail.HistoryStatus.NO_DATA, uid, window_key, key)

        cb.populate(
            self._context(), key,
            fetch_detail=lambda uid, **k: detail.RTLDetailResult(
                detail.DetailStatus.DATA, uid, _detail()),
            fetch_history=fetch_history,
        )
        assert seen["key"] == key

    def test_an_unknown_window_is_not_substituted_silently(self):
        seen = {}

        def fetch_history(uid, window_key, **k):
            seen["key"] = window_key
            return detail.RTLHistory(detail.HistoryStatus.NO_DATA, uid, window_key)

        cb.populate(
            self._context(), "all-time",
            fetch_detail=lambda uid, **k: detail.RTLDetailResult(
                detail.DetailStatus.DATA, uid, _detail()),
            fetch_history=fetch_history,
        )
        assert seen["key"] == "all-time"


# ---------------------------------------------------------------------------
# Fleet -> detail navigation (gate sections 4 and 14)
# ---------------------------------------------------------------------------


def _row(uid=A_UID, **overrides) -> RTLFleetRow:
    base = dict(
        device_uid=uid,
        temperature_state=TemperatureState.VALUE,
        temperature=Decimal("35.5"),
        ambiguous_values=(),
        last_reported=LAST,
        transformer_codes=("AA12",),
        hierarchy_state=HierarchyState.AVAILABLE,
        hierarchy=HierarchyContext("Distribution", "North", "Sector 4", "CNC 2", "Feeder 7"),
    )
    base.update(overrides)
    return RTLFleetRow(**base)


class TestFleetRowsLinkToTheCanonicalRoute:
    def test_a_row_links_to_the_uid_route(self):
        assert (str(A_UID), f"/rtls/{A_UID}") in links(rtl_fleet.fleet_table((_row(),)))

    def test_no_row_links_through_the_synthetic_device_route(self):
        table = rtl_fleet.fleet_table((_row(), _row(29006)))
        assert all("/devices" not in href for _label, href in links(table))
        assert all("/plants/" not in href for _label, href in links(table))

    def test_every_row_links_whatever_its_data_state(self):
        """Registration is what makes a detail page exist — not telemetry and
        not a mapping. An RTL with neither must still be openable."""
        rows = (
            _row(29001, temperature_state=TemperatureState.NO_DATA,
                 temperature=None, last_reported=None),
            _row(29002, transformer_codes=(),
                 hierarchy_state=HierarchyState.NOT_MAPPED, hierarchy=None),
            _row(29003, temperature_state=TemperatureState.AMBIGUOUS, temperature=None,
                 ambiguous_values=(Decimal("21"), Decimal("48"))),
        )
        hrefs = dict(links(rtl_fleet.fleet_table(rows)))
        for uid in (29001, 29002, 29003):
            assert hrefs[str(uid)] == rtl_detail_href(uid)

    def test_the_link_is_built_from_the_shared_route_helper(self):
        """Not a hand-written f-string, which is how the two would drift."""
        import inspect

        source = inspect.getsource(rtl_fleet)
        assert "rtl_detail_href" in source
        assert '"/rtls' not in source and "'/rtls" not in source

    def test_the_restricted_panel_still_offers_no_uid_at_all(self):
        """A role refused the Fleet must not be handed a detail link either."""
        panel = rtl_fleet.restricted_panel()
        assert links(panel) == []
        assert str(A_UID) not in text_of(panel)
