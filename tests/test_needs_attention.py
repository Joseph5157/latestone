"""Needs Attention exception queue — correctness of the grouped tree.

Pins the ENT-2 contract that:
- only NO_DATA / STALE plants appear; FRESH plants are excluded
- only NON-FRESH branches appear beneath a plant (fresh transformer/device
  rows are the absence of an exception and are omitted)
- NO_DATA sorts above STALE at every level
- the cap counts actionable RTL LEAVES, never group headings; parents render
  automatically beneath whichever leaves are shown
- every state, count and age is derived from the ONE shared FleetHealth —
  building the queue issues no telemetry or hierarchy query at all
- empty state shows the truthful "No current data-freshness exceptions."
- links point at stable /plants/<p>/<t> and /devices/<d> routes
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from dash import Input, Output

from callbacks.listings import (
    NEEDS_ATTENTION_MAX_RTLS,
    build_exception_queue,
    extra_groups_beyond_cap,
    hierarchy_code_index,
    needs_attention_toggle_state,
    sort_needs_attention_rows,
)
from components.needs_attention import needs_attention
from services.monitoring_service import (
    Freshness,
    fleet_health_from_rows,
    severity_rank,
)
from tests.dash_tree import find_by_class, find_by_exact_class, find_by_id, links, text_of

NOW = datetime(2026, 8, 18, 12, 0, tzinfo=timezone.utc)
FRESH_TS = NOW - timedelta(minutes=10)
STALE_TS = NOW - timedelta(days=2)

F, S, N = Freshness.FRESH, Freshness.STALE, Freshness.NO_DATA


class _Plant:
    def __init__(self, plant_id, name, country="Chile", fuel="Hydro", capacity=100.0):
        self.plant_id = plant_id
        self.name = name
        self.country = country
        self.primary_fuel = fuel
        self.capacity_mw = capacity


def _row(plant, device, metric, ts, transformer=None):
    return type("R", (), {
        "plant_id": plant, "device_id": device, "transformer_id": transformer,
        "metric": metric, "reading_ts": ts,
    })()


def _health(triples):
    """FleetHealth from (plant, transformer, device, ts) tuples."""
    return fleet_health_from_rows(
        [_row(p, d, "temperature", ts, t) for p, t, d, ts in triples], now=NOW
    )


def _codes(devices=(), transformers=()):
    return {"device_codes": dict(devices), "transformer_codes": dict(transformers)}


# --------------------------------------------------------------------------
# sort_needs_attention_rows (unchanged flat rule, still used per level)
# --------------------------------------------------------------------------

class TestSortNeedsAttentionRows:
    def test_no_data_sorts_above_stale(self):
        rows = [
            {"_severity": 1, "entity": "Zzz Stale", "_state": "stale"},
            {"_severity": 2, "entity": "Aaa NoData", "_state": "no_data"},
            {"_severity": 0, "entity": "Mmm Fresh", "_state": "fresh"},
        ]
        ordered = sort_needs_attention_rows(rows)
        assert [r["entity"] for r in ordered] == [
            "Aaa NoData", "Zzz Stale", "Mmm Fresh"
        ]

    def test_ties_fall_back_to_entity_name(self):
        rows = [
            {"_severity": 2, "entity": "Zzz", "_state": "no_data"},
            {"_severity": 2, "entity": "Aaa", "_state": "no_data"},
        ]
        ordered = sort_needs_attention_rows(rows)
        assert [r["entity"] for r in ordered] == ["Aaa", "Zzz"]


# --------------------------------------------------------------------------
# build_exception_queue — grouping and branch filtering
# --------------------------------------------------------------------------

class TestQueueGrouping:
    def test_fresh_plants_are_excluded(self):
        health = _health([
            ("p1", "t1", "d1", FRESH_TS),
            ("p2", "t9", "d2", FRESH_TS),
        ])
        plants = [_Plant("p1", "Aaa"), _Plant("p2", "Zzz")]
        queue = build_exception_queue(plants, health, NOW, **_codes())
        assert queue["groups"] == []
        assert queue["total_rtls"] == 0

    def test_stale_plant_appears_as_a_group(self):
        health = _health([("p1", "t1", "d1", FRESH_TS), ("p2", "t2", "d2", STALE_TS)])
        plants = [_Plant("p1", "Aaa"), _Plant("p2", "Zzz")]
        queue = build_exception_queue(plants, health, NOW, **_codes())
        assert len(queue["groups"]) == 1
        group = queue["groups"][0]
        assert group["kind"] == "plant"
        assert group["entity"] == "Zzz"
        assert group["_state"] == "stale"
        assert group["href"] == "/plants/p2"

    def test_no_data_plant_appears(self):
        health = _health([("p1", "t1", "d1", None)])
        queue = build_exception_queue([_Plant("p1", "Aaa")], health, NOW, **_codes())
        assert queue["groups"][0]["_state"] == "no_data"

    def test_plant_absent_from_health_is_header_only_no_data(self):
        """A plant with no rows is NO_DATA over zero devices: an exception with
        nothing actionable, so it renders as a header-only group and consumes
        no leaf budget."""
        health = _health([("p1", "t1", "d1", FRESH_TS)])
        plants = [_Plant("p1", "Fresh"), _Plant("p9", "Ghost")]
        queue = build_exception_queue(plants, health, NOW, **_codes())
        assert len(queue["groups"]) == 1
        group = queue["groups"][0]
        assert group["entity"] == "Ghost"
        assert group["_state"] == "no_data"
        assert group["children"] == []
        assert queue["total_rtls"] == 0

    def test_only_non_fresh_branches_appear(self):
        """Frozen structure: fresh transformers and fresh RTLs are omitted;
        a non-fresh transformer lists only its non-fresh RTLs."""
        health = _health([
            # p1: t1 fully stale (both RTLs listed), t2 fresh (omitted)
            ("p1", "t1", "d_stale1", STALE_TS),
            ("p1", "t1", "d_stale2", STALE_TS),
            ("p1", "t2", "d_ok", FRESH_TS),
            # p2 fully fresh (whole plant omitted)
            ("p2", "t3", "d_ok2", FRESH_TS),
        ])
        plants = [_Plant("p1", "One"), _Plant("p2", "Two")]
        codes = _codes(
            [("d_stale1", "29104"), ("d_stale2", "29111")],
            [("t1", "T04")],
        )
        queue = build_exception_queue(plants, health, NOW, **codes)
        assert len(queue["groups"]) == 1
        children = queue["groups"][0]["children"]
        assert [c["entity"] for c in children] == ["T04"]
        leaves = children[0]["children"]
        assert sorted(l["entity"] for l in leaves) == ["29104", "29111"]
        assert all(l["kind"] == "device" for l in leaves)
        assert queue["total_rtls"] == 2

    def test_exception_first_ordering_at_every_level(self):
        health = _health([
            ("p_fresh", "t0", "d0", FRESH_TS),
            ("p_stale", "t_s", "d_s", STALE_TS),
            ("p_none", "t_n", "d_n", None),
        ])
        plants = [
            _Plant("p_fresh", "Aaa"),
            _Plant("p_stale", "Zzz"),
            _Plant("p_none", "Mmm"),
        ]
        queue = build_exception_queue(plants, health, NOW, **_codes())
        states = [g["_state"] for g in queue["groups"]]
        assert states == ["no_data", "stale"]

    def test_row_carries_ids_and_hrefs_for_drill_through(self):
        health = _health([
            ("p1", "t1", "d1", STALE_TS),
            ("p1", "t1", "d2", None),
        ])
        codes = _codes([("d1", "29104"), ("d2", "29111")], [("t1", "T04")])
        queue = build_exception_queue([_Plant("p1", "Itaipu")], health, NOW, **codes)
        group = queue["groups"][0]
        branch = group["children"][0]

        assert branch["href"] == "/plants/p1/t1"
        # Worst first within the transformer too: NO_DATA leaf leads.
        leaf_none, leaf_stale = branch["children"]
        assert leaf_none["entity"] == "29111"
        assert leaf_stale["entity"] == "29104"
        assert all(leaf["href"].startswith("/devices/") for leaf in (leaf_stale, leaf_none))

    def test_unknown_code_falls_back_to_raw_id_not_a_guess(self):
        health = _health([("p1", "t1", "d1", STALE_TS)])
        queue = build_exception_queue([_Plant("p1", "Itaipu")], health, NOW, **_codes())
        branch = queue["groups"][0]["children"][0]
        assert branch["entity"] == "t1"
        assert branch["children"][0]["entity"] == "d1"

    def test_ages_come_from_device_timestamps(self):
        health = _health([("p1", "t1", "d1", STALE_TS), ("p1", "t1", "d2", None)])
        queue = build_exception_queue([_Plant("p1", "Itaipu")], health, NOW, **_codes())
        branch = queue["groups"][0]["children"][0]
        none_leaf, stale_leaf = branch["children"]
        assert "ago" in stale_leaf["last_update"]
        assert "No readings" in none_leaf["last_update"]
        # Transformer age derives from its devices' own timestamps.
        assert "ago" in branch["last_update"]

    def test_builder_issues_no_queries(self, monkeypatch):
        """The queue is pure derivation. Telemetry AND hierarchy lookups must
        both raise if attempted here — codes arrive as plain dicts."""
        from repositories import plant_monitoring_repository as repo
        from services import hierarchy_service

        def boom(*a, **k):
            raise AssertionError("the exception builder issued a query")

        monkeypatch.setattr(repo, "latest_reading_times", boom)
        monkeypatch.setattr(hierarchy_service, "list_all_devices", boom)

        health = _health([("p1", "t1", "d1", STALE_TS)])
        queue = build_exception_queue([_Plant("p1", "Itaipu")], health, NOW, **_codes())
        assert queue["total_rtls"] == 1


# --------------------------------------------------------------------------
# Cap semantics — leaves count, headings do not
# --------------------------------------------------------------------------

class TestLeafCap:
    def _wide_health(self, stale_plants: int, rtls_per_plant: int):
        triples = []
        for i in range(stale_plants):
            pid = f"p{i}"
            for j in range(rtls_per_plant):
                triples.append((pid, f"{pid}-t{j}", f"{pid}-d{j}", STALE_TS))
        return _health(triples)

    def test_cap_limits_leaves_not_headings(self):
        plants = [_Plant(f"p{i}", f"Plant {i}") for i in range(3)]
        health = self._wide_health(3, 4)  # 12 affected RTLs across 3 plants
        queue = build_exception_queue(plants, health, NOW, **_codes())

        assert queue["total_rtls"] == 12
        assert queue["shown_rtls"] == NEEDS_ATTENTION_MAX_RTLS
        shown_leaves = sum(
            len(t["children"])
            for g in queue["groups"] for t in g["children"]
        )
        assert shown_leaves == NEEDS_ATTENTION_MAX_RTLS

    def test_parents_render_automatically_beneath_shown_leaves(self):
        """Five leaves under two plants must show both plant rows and every
        intermediate transformer row — context is free, only leaves count."""
        plants = [_Plant(f"p{i}", f"Plant {i}") for i in range(3)]
        health = self._wide_health(3, 4)
        queue = build_exception_queue(plants, health, NOW, **_codes())

        rendered_plants = queue["groups"]
        assert len(rendered_plants) >= 2
        for group in rendered_plants:
            # No empty branches: every shown transformer has >= 1 leaf.
            assert all(t["children"] for t in group["children"])

    def test_partially_shown_transformer_drops_empty_branches(self):
        """A transformer whose leaves were consumed by earlier groups must not
        render as a bare heading."""
        plants = [_Plant(f"p{i}", f"Plant {i}") for i in range(3)]
        health = self._wide_health(3, 4)
        queue = build_exception_queue(plants, health, NOW, **_codes())

        for group in queue["groups"]:
            for branch in group["children"]:
                assert branch["children"], "empty transformer heading rendered"

    def test_single_small_queue_is_uncapped(self):
        plants = [_Plant("p0", "One")]
        health = self._wide_health(1, 3)
        queue = build_exception_queue(plants, health, NOW, **_codes())
        assert queue["shown_rtls"] == 3
        assert queue["shown_rtls"] == queue["total_rtls"]


# --------------------------------------------------------------------------
# hierarchy_code_index — one bulk read, only when exceptions exist
# --------------------------------------------------------------------------

class TestHierarchyCodeIndex:
    def _rows(self):
        from repositories.plant_monitoring_repository import AdminDeviceRow

        return [
            AdminDeviceRow(
                device_id="p1-t1-d1", device_code="29104", status="active",
                transformer_id="p1-t1", transformer_code="T04",
                plant_id="p1", plant_name="One",
            ),
            AdminDeviceRow(
                device_id="p1-t1-d2", device_code="29111", status="active",
                transformer_id="p1-t1", transformer_code="T04",
                plant_id="p1", plant_name="One",
            ),
        ]

    def test_healthy_fleet_issues_no_lookup(self, monkeypatch):
        from services import hierarchy_service

        def boom():
            raise AssertionError("lookup ran on a healthy fleet")

        monkeypatch.setattr(hierarchy_service, "list_all_devices", boom)
        health = _health([("p1", "t1", "d1", FRESH_TS)])
        index = hierarchy_code_index([_Plant("p1", "One")], health)
        assert index == {"device_codes": {}, "transformer_codes": {}}

    def test_exceptions_trigger_exactly_one_bulk_lookup(self, monkeypatch):
        from services import hierarchy_service

        calls = []

        def once():
            calls.append(1)
            return self._rows()

        monkeypatch.setattr(hierarchy_service, "list_all_devices", once)
        health = _health([("p1", "t1", "d1", STALE_TS)])
        index = hierarchy_code_index([_Plant("p1", "One")], health)
        assert calls == [1]
        assert index["device_codes"]["p1-t1-d1"] == "29104"
        assert index["transformer_codes"]["p1-t1"] == "T04"


def _leaf_ids(groups: list[dict]) -> list[str]:
    return [leaf["id"] for g in groups for t in g["children"] for leaf in t["children"]]


# --------------------------------------------------------------------------
# extra_groups_beyond_cap — the "Show all" expansion content
# --------------------------------------------------------------------------

class TestExtraGroupsBeyondCap:
    def _six_across_three(self):
        """6 affected RTLs across 3 plants; the cap of 5 spans all three."""
        plants = [_Plant(f"p{i}", f"Plant {i}") for i in range(3)]
        triples = [
            (f"p{i}", f"p{i}-t1", f"{i}-{j}", STALE_TS)
            for i in range(3) for j in range(2)
        ]
        health = _health(triples)
        return plants, health

    def test_extra_holds_exactly_what_the_cap_dropped(self):
        plants, health = self._six_across_three()
        shown = build_exception_queue(plants, health, NOW, **_codes())
        full = build_exception_queue(plants, health, NOW, **_codes(), max_rtls=None)
        extra = extra_groups_beyond_cap(full["groups"], shown["groups"])
        assert len(_leaf_ids(extra)) == 1

    def test_shown_and_extra_together_equal_the_full_tree_with_no_duplicates(self):
        plants, health = self._six_across_three()
        shown = build_exception_queue(plants, health, NOW, **_codes())
        full = build_exception_queue(plants, health, NOW, **_codes(), max_rtls=None)
        extra = extra_groups_beyond_cap(full["groups"], shown["groups"])
        shown_ids = _leaf_ids(shown["groups"])
        extra_ids = _leaf_ids(extra)
        assert set(shown_ids).isdisjoint(extra_ids)
        assert sorted(shown_ids + extra_ids) == sorted(_leaf_ids(full["groups"]))

    def test_nothing_extra_when_the_queue_was_never_capped(self):
        queue = build_exception_queue(
            [_Plant("p1", "Plant A")],
            _health([("p1", "t1", "d1", STALE_TS)]),
            NOW, **_codes(),
        )
        full = build_exception_queue(
            [_Plant("p1", "Plant A")],
            _health([("p1", "t1", "d1", STALE_TS)]),
            NOW, **_codes(), max_rtls=None,
        )
        assert extra_groups_beyond_cap(full["groups"], queue["groups"]) == []

    def test_a_zero_leaf_ghost_plant_is_never_duplicated_into_extra(self):
        """A NO_DATA-over-zero-devices plant costs no budget and is always
        already in `shown_groups` — it must not reappear in `extra`."""
        plants = [_Plant(f"p{i}", f"Plant {i}") for i in range(3)] + [
            _Plant("p9", "Ghost")
        ]
        triples = [
            (f"p{i}", f"p{i}-t1", f"{i}-{j}", STALE_TS)
            for i in range(3) for j in range(2)
        ]
        health = _health(triples)
        shown = build_exception_queue(plants, health, NOW, **_codes())
        full = build_exception_queue(plants, health, NOW, **_codes(), max_rtls=None)
        assert "Ghost" in text_of_groups(shown["groups"])
        extra = extra_groups_beyond_cap(full["groups"], shown["groups"])
        assert "Ghost" not in text_of_groups(extra)


def text_of_groups(groups: list[dict]) -> str:
    names = []
    for g in groups:
        names.append(g["entity"])
        for t in g["children"]:
            names.append(t["entity"])
            for leaf in t["children"]:
                names.append(leaf["entity"])
    return " ".join(names)


# --------------------------------------------------------------------------
# needs_attention_toggle_state — the "Show all" / "Show less" click parity
# --------------------------------------------------------------------------

class TestNeedsAttentionToggleState:
    def test_no_clicks_is_collapsed(self):
        assert needs_attention_toggle_state(None) == (
            "card needs-attention", "Show all", "false",
        )
        assert needs_attention_toggle_state(0) == (
            "card needs-attention", "Show all", "false",
        )

    def test_odd_clicks_is_expanded(self):
        assert needs_attention_toggle_state(1) == (
            "card needs-attention needs-attention--expanded", "Show less", "true",
        )

    def test_even_clicks_collapses_again(self):
        assert needs_attention_toggle_state(2) == (
            "card needs-attention", "Show all", "false",
        )


# --------------------------------------------------------------------------
# Component rendering
# --------------------------------------------------------------------------

class TestNeedsAttentionComponent:
    def _queue(self):
        return build_exception_queue(
            [_Plant("p1", "Plant A")],
            _health([
                ("p1", "t1", "d1", STALE_TS),
                ("p1", "t1", "d2", None),
            ]),
            NOW,
            **_codes([("d1", "29104"), ("d2", "29111")], [("t1", "T04")]),
        )

    def test_renders_heading(self):
        panel = needs_attention(self._queue())
        titles = [text_of(n) for n in find_by_class(panel, "card__title")]
        assert titles == ["Needs attention"]

    def test_renders_the_full_grouped_hierarchy(self):
        panel = needs_attention(self._queue())
        text = text_of(panel)
        assert "Plant A" in text
        assert "T04" in text
        assert "29104" in text
        assert "29111" in text

    def test_state_badges_use_freshness_vocabulary_only(self):
        panel = needs_attention(self._queue())
        badges = [
            text_of(n) for n in find_by_class(panel, "needs-attention__badge")
        ]
        assert set(badges) <= {"Fresh", "Stale", "No data"}
        for banned in ("Critical", "Warning"):
            assert banned not in text_of(panel)

    def test_badge_renders_only_on_the_plant_row(self):
        """The redesign's one loud signal per group: transformer/device rows
        use a quiet dot instead of repeating the full text chip."""
        panel = needs_attention(self._queue())  # 1 plant, 1 transformer, 2 devices
        assert len(find_by_exact_class(panel, "needs-attention__badge")) == 1
        assert len(find_by_exact_class(panel, "needs-attention__dot")) == 3

    def test_dot_carries_a_visually_hidden_state_label(self):
        """Colour alone never carries the state — a dot's severity stays in
        the accessibility tree even though nothing shows visually."""
        panel = needs_attention(self._queue())
        dots = find_by_exact_class(panel, "needs-attention__dot")
        for dot in dots:
            hidden_label = find_by_exact_class(dot, "visually-hidden")
            assert len(hidden_label) == 1
            assert text_of(hidden_label[0]) in {"Fresh", "Stale", "No data"}

    def test_leaf_rows_carry_no_issue_text(self):
        """A device row's state is fully carried by its dot; the old
        `.needs-attention__detail` on a leaf only ever repeated that dot's
        word and has been removed."""
        panel = needs_attention(self._queue())
        device_rows = find_by_exact_class(panel, "needs-attention__row--device")
        assert device_rows  # sanity: there really are device rows here
        for row in device_rows:
            assert find_by_exact_class(row, "needs-attention__detail") == []

    def test_transformer_detail_drops_the_redundant_state_prefix(self):
        """"No data · 1 of 2 devices" becomes "1 of 2 devices" next to the
        dot that already says No data — the dot and the word must never
        both say it verbatim, the same redundancy leaf rows had entirely
        removed."""
        panel = needs_attention(self._queue())
        transformer_rows = find_by_exact_class(panel, "needs-attention__row--transformer")
        assert transformer_rows
        for row in transformer_rows:
            detail = find_by_exact_class(row, "needs-attention__detail")
            assert len(detail) == 1
            assert text_of(detail[0]) == "1 of 2 devices"
            assert "Stale" not in text_of(detail[0])
            assert "No data" not in text_of(detail[0])

    def test_links_target_transformer_and_device_routes(self):
        panel = needs_attention(self._queue())
        hrefs = dict(links(panel))
        assert hrefs["Open"] == "/plants/p1"
        assert hrefs["T04"] == "/plants/p1/t1"
        assert any(h.startswith("/devices/") for h in hrefs.values())

    def test_view_full_fleet_is_a_real_anchor(self):
        """A plain anchor scrolls to the inventory; dcc.Link would rewrite the
        URL instead (ENT-2 gate decision)."""
        from dash import html as dash_html

        panel = needs_attention(self._queue())
        anchors = [
            n for n in find_by_class(panel, "needs-attention__all")
            if isinstance(n, dash_html.A)
        ]
        assert len(anchors) == 1
        assert anchors[0].href == "#fleet-plants"

    def test_discloses_truncated_totals_in_reviewer_wording(self):
        plants = [_Plant(f"p{i}", f"Plant {i}") for i in range(3)]
        triples = [
            (f"p{i}", f"p{i}-t1", f"{i}-{j}", STALE_TS)
            for i in range(3) for j in range(2)
        ]  # 6 affected RTLs across 3 plants; the cap of 5 spans all three
        queue = build_exception_queue(plants, _health(triples), NOW, **_codes())
        panel = needs_attention(queue)
        assert queue["shown_rtls"] == 5
        assert "Showing 5 of 6 affected RTLs across 3 plants." in text_of(panel)

    def test_discloses_full_totals_when_uncapped(self):
        queue = self._queue()  # 2 affected RTLs, both shown
        panel = needs_attention(queue)
        assert "2 affected RTLs across 1 plant." in text_of(panel)

    def test_ghost_plant_disclosure_names_plants_not_rtls(self):
        queue = build_exception_queue(
            [_Plant("p9", "Ghost")], _health([]), NOW, **_codes()
        )
        panel = needs_attention(queue)
        assert "1 affected plant." in text_of(panel)

    def test_empty_state_message(self):
        queue = {"groups": [], "total_rtls": 0, "shown_rtls": 0, "plant_count": 0}
        panel = needs_attention(queue)
        assert "No current data-freshness exceptions." in text_of(panel)

    def test_empty_panel_has_heading(self):
        panel = needs_attention({"groups": [], "total_rtls": 0,
                                 "shown_rtls": 0, "plant_count": 0})
        titles = [text_of(n) for n in find_by_class(panel, "card__title")]
        assert titles == ["Needs attention"]

    def test_no_rows_render_for_an_empty_queue(self):
        panel = needs_attention({"groups": [], "total_rtls": 0,
                                 "shown_rtls": 0, "plant_count": 0})
        assert find_by_class(panel, "needs-attention__row") == []

    def _capped_queue_and_extra(self):
        plants = [_Plant(f"p{i}", f"Plant {i}") for i in range(3)]
        triples = [
            (f"p{i}", f"p{i}-t1", f"{i}-{j}", STALE_TS)
            for i in range(3) for j in range(2)
        ]  # 6 affected RTLs across 3 plants; cap 5, so exactly 1 is "extra"
        health = _health(triples)
        shown = build_exception_queue(plants, health, NOW, **_codes())
        full = build_exception_queue(plants, health, NOW, **_codes(), max_rtls=None)
        extra = extra_groups_beyond_cap(full["groups"], shown["groups"])
        return shown, extra

    def test_no_toggle_or_extra_content_when_nothing_was_capped(self):
        panel = needs_attention(self._queue())  # 2 of 2 shown, nothing extra
        assert find_by_id(panel, "needs-attention-toggle") is None
        assert find_by_id(panel, "needs-attention-extra") is None

    def test_toggle_and_extra_content_render_when_capped(self):
        queue, extra = self._capped_queue_and_extra()
        panel = needs_attention(queue, extra)
        toggle = find_by_id(panel, "needs-attention-toggle")
        assert toggle is not None
        assert text_of(toggle) == "Show all"
        assert toggle.n_clicks == 0
        assert find_by_id(panel, "needs-attention-extra") is not None

    def test_extra_content_is_not_duplicated_in_the_visible_list(self):
        queue, extra = self._capped_queue_and_extra()
        panel = needs_attention(queue, extra)
        visible_list = find_by_id(panel, "needs-attention-card").children[1]
        extra_ids = set(_leaf_ids(extra))
        assert not extra_ids & set(_leaf_ids(queue["groups"]))
        assert extra_ids  # sanity: there really is something extra here
        assert text_of_groups(extra) not in text_of(visible_list)

    def test_card_carries_the_toggle_target_id(self):
        panel = needs_attention(self._queue())
        assert panel.id == "needs-attention-card"

    def test_extra_list_is_hidden_by_a_dedicated_css_class_not_inline_style(self):
        """Hidden by `.needs-attention__list--extra` in app.css, revealed by
        the toggle callback flipping the card's className — never an inline
        style the toggle callback would then have to fight."""
        queue, extra = self._capped_queue_and_extra()
        panel = needs_attention(queue, extra)
        extra_node = find_by_id(panel, "needs-attention-extra")
        assert "needs-attention__list--extra" in extra_node.className
        assert not getattr(extra_node, "style", None)


# --------------------------------------------------------------------------
# No regression to the overview table / FleetHealth contracts
# --------------------------------------------------------------------------

class TestNoRegressionToOverviewTable:
    def test_plant_columns_keep_operational_fields_only(self):
        from callbacks.listings import PLANT_COLUMNS
        assert [c["id"] for c in PLANT_COLUMNS] == [
            "plant", "country", "transformers", "devices", "freshness",
        ]

    def test_build_plant_rows_unaffected(self):
        from callbacks.listings import build_plant_rows
        health = _health([
            ("p_fresh", "t1", "d1", FRESH_TS), ("p_stale", "t2", "d2", STALE_TS),
        ])
        plants = [_Plant("p_fresh", "Aaa"), _Plant("p_stale", "Zzz")]
        rows = build_plant_rows(plants, {"p_fresh": (1, 1), "p_stale": (1, 1)}, health)
        assert len(rows) == 2
        assert {r["plant"] for r in rows} == {"Aaa", "Zzz"}

    def test_legacy_fixture_rows_without_transformer_id_still_build(self):
        """fleet_health_from_rows tolerates rows lacking `transformer_id`
        (older fixtures); the additive fields must not change that."""
        legacy_row = type("R", (), {
            "plant_id": "p1", "device_id": "d1",
            "metric": "temperature", "reading_ts": FRESH_TS,
        })()
        health = fleet_health_from_rows([legacy_row], now=NOW)
        assert health.device_last_updated["d1"] == FRESH_TS


class TestFleetHealthAdditiveContract:
    def test_device_last_updated_keeps_the_newest_metric_sample(self):
        t_new = NOW - timedelta(hours=1)
        t_old = NOW - timedelta(hours=5)
        health = _health([
            ("p1", "t1", "d1", t_new),
            ("p1", "t1", "d1", t_old),  # second metric, older sample
        ])
        assert health.device_last_updated["d1"] == t_new

    def test_device_with_no_readings_has_no_entry(self):
        health = _health([("p1", "t1", "d1", None)])
        assert health.device_last_updated.get("d1") is None

    def test_devices_for_transformer_selects_only_that_subtree(self):
        health = _health([
            ("p1", "t1", "d1", STALE_TS),
            ("p1", "t1", "d2", FRESH_TS),
            ("p1", "t2", "d3", FRESH_TS),
        ])
        subtree = health.devices_for_transformer("t1")
        assert set(subtree) == {"d1", "d2"}

    def test_transformer_age_derives_from_device_timestamps(self):
        t_new = NOW - timedelta(hours=2)
        t_old = NOW - timedelta(days=3)
        health = _health([
            ("p1", "t1", "d1", t_old),
            ("p1", "t1", "d2", t_new),
            ("p2", "t2", "d3", None),
        ])
        assert health.last_updated_for_transformer("t1") == t_new
        assert health.last_updated_for_transformer("t2") is None
        assert health.last_updated_for_transformer("unknown") is None


class TestPlantLastUpdated:
    def test_plant_last_updated_populated(self):
        health = _health([
            ("p1", "t1", "d1", FRESH_TS),
            ("p1", "t1", "d2", STALE_TS),
            ("p2", "t9", "d3", None),
        ])
        assert "p1" in health.plant_last_updated
        assert health.plant_last_updated["p1"] == FRESH_TS
        assert health.plant_last_updated.get("p2") is None

    def test_plant_with_mixed_timestamps_keeps_latest(self):
        t1 = NOW - timedelta(hours=1)
        t2 = NOW - timedelta(hours=5)
        health = _health([
            ("p1", "t1", "d1", t1),
            ("p1", "t1", "d2", t2),
        ])
        assert health.plant_last_updated["p1"] == t1


# --------------------------------------------------------------------------
# toggle_needs_attention_extra — the "Show all" callback wiring
# --------------------------------------------------------------------------

@pytest.fixture
def needs_attention_toggle_callback():
    """Same Capture pattern as the my-rtls navigation wiring tests, for the
    "Show all" toggle callback instead."""
    from callbacks import listings

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
    return (
        capture.functions["toggle_needs_attention_extra"],
        capture.specs["toggle_needs_attention_extra"],
    )


class TestNeedsAttentionToggleWiring:
    def test_the_callback_is_wired_to_the_toggle_button(self, needs_attention_toggle_callback):
        _fn, (args, kwargs) = needs_attention_toggle_callback
        assert [(a.component_id, a.component_property) for a in args if isinstance(a, Input)] == [
            ("needs-attention-toggle", "n_clicks"),
        ]
        outputs = [(a.component_id, a.component_property) for a in args if isinstance(a, Output)]
        assert outputs == [
            ("needs-attention-card", "className"),
            ("needs-attention-toggle", "children"),
            ("needs-attention-toggle", "aria-expanded"),
        ]
        assert kwargs == {"prevent_initial_call": True}

    def test_the_callback_delegates_to_the_pure_toggle_function(self, needs_attention_toggle_callback):
        fn, _spec = needs_attention_toggle_callback
        assert fn(1) == needs_attention_toggle_state(1)
        assert fn(None) == needs_attention_toggle_state(None)
