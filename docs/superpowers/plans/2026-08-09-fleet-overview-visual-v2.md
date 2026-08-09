# Fleet Overview Visual Slice v2 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Raise the Fleet Overview page to a portfolio monitoring screen — wider layout, stronger typography, exception-led Data Health, denser table with accessible overflow — without disturbing the frozen Device reference.

**Architecture:** Additive, Fleet-scoped CSS tokens and modifier classes. Existing Device-consumed tokens keep their values byte-for-byte, so Device is unchanged by construction. Domain logic changes are confined to how freshness is *worded* and *identified*, never to how it is *computed*.

**Tech Stack:** Python, Plotly Dash 2.17, `dash_table`, plain CSS custom properties, pytest.

**Spec:** `docs/superpowers/specs/2026-08-09-fleet-overview-visual-v2-design.md` (commits `1a7c9f5`, `33678bd`)

## Global Constraints

Every task's requirements implicitly include these.

- **Run tests with** `.venv/Scripts/python.exe -m pytest`. `-m "not db"` skips Docker-dependent tests.
- **Baseline: 526 passing** under `-m "not db"`. No task may reduce this without a written reason.
- **Multi-line commit messages** must use `git commit -F <file>` or a heredoc. PowerShell here-strings break on embedded quotes.
- **Do not modify:** URL contracts, `app.layout`, equipment selector placement, `aggregate_freshness`, `evaluate_freshness`, the active-equipment population rule.
- **Do not change the values of** `--fs-kpi`, `--fs-page-title`, `--fs-body`, `--fs-meta`, or the `.page h1` rule.
- **No thresholds, alarms, electrical conditions, charts, maps, or icons beyond `●`.** `MonitoringCondition` stays `UNKNOWN`.
- **Never bind state styling to display text** (`"Stale"`) or to a bare rank literal (`0`/`1`/`2`). Use `_state`, sourced from the `Freshness` enum.
- **No `!important`.** If the cascade needs forcing, the selector is wrong.
- **Do not import `PLANT_COLUMNS` from `callbacks.listings` into `pages.plants_overview`**, even if no circular import occurs.
- **Never fix anything outside this slice.** Log it in `docs/UX_DEBT.md` or the acceptance record instead.

## File Structure

| File | Responsibility | Tasks |
|---|---|---|
| `components/fleet_summary.py` | Data Health wording and card composition | 1 |
| `components/entity_table.py` | Table presentation: alignment, state styling, overflow | 2, 3, 7 |
| `callbacks/listings.py` | Row data (`_state`), render instant | 2, 5 |
| `services/monitoring_service.py` | `get_fleet_health(now=...)` pass-through only | 5 |
| `pages/plants_overview.py` | Fleet layout: title, subtitle, refresh slot, container | 4, 5, 6, 8 |
| `pages/plant_detail.py`, `pages/transformer_detail.py`, `pages/device_dashboard.py` | breadcrumb root label | 4 |
| `assets/app.css` | tokens, containers, type scale, density, reveal | 6, 7 |
| `tests/test_fleet_overview.py` | Data Health wording, render instant, column guard | 1, 5, 8 |
| `tests/test_entity_table.py` *(new)* | alignment, state rules, overflow config | 2, 3, 7 |
| `tests/test_fleet_naming.py` *(new)* | breadcrumb root and page title | 4 |
| `docs/UX_ACCEPTANCE_FLEET.md` *(new)* | measured acceptance record | 9 |

---

### Task 1: Exception-led Data Health wording

Rewrites the shared `_health_summary()` so the headline names the **worst state present**, and drops the accent treatment from the Data Health card.

**Files:**
- Modify: `components/fleet_summary.py:17-73` (`_EXCEPTION_STATES`, `_health_summary`, `fleet_kpi_cards`) and the `accent=True` argument at lines 71, 91, 111
- Test: `tests/test_fleet_overview.py`

**Interfaces:**
- Consumes: `Freshness`, `severity_rank` from `services.monitoring_service`
- Produces: `_health_summary(counts: dict[Freshness, int]) -> tuple[str, str]` — unchanged signature, new wording. Consumed unchanged by `fleet_kpi_cards`, `plant_kpi_cards`, `transformer_kpi_cards`.

**The rule, stated exactly:**

- Empty population (total 0) → `("No active devices", "No data available")`
- All fresh → `(f"{n} fresh", "No stale or missing feeds")`
- Otherwise → value is the **worst state present** by `severity_rank`; secondary lists the remaining states in **ascending** severity, including `FRESH` even when its count is zero, and excluding other zero-count states.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_fleet_overview.py — append
from components.fleet_summary import _health_summary
from services.monitoring_service import Freshness


def test_health_summary_leads_with_stale_when_nothing_is_fresh():
    value, secondary = _health_summary({Freshness.FRESH: 0, Freshness.STALE: 120})
    assert value == "120 stale"
    assert secondary == "0 fresh"


def test_health_summary_leads_with_no_data_over_stale():
    """NO_DATA outranks STALE, the same worst-of order as aggregation.

    Guards the whole point of the change: the lead is derived from severity,
    never hardcoded to stale because stale is the common case today.
    """
    value, secondary = _health_summary(
        {Freshness.FRESH: 102, Freshness.STALE: 15, Freshness.NO_DATA: 3}
    )
    assert value == "3 no data"
    assert secondary == "102 fresh · 15 stale"


def test_health_summary_leads_with_health_when_all_fresh():
    value, secondary = _health_summary({Freshness.FRESH: 120})
    assert value == "120 fresh"
    assert secondary == "No stale or missing feeds"


def test_health_summary_omits_zero_exception_states():
    value, secondary = _health_summary(
        {Freshness.FRESH: 100, Freshness.STALE: 0, Freshness.NO_DATA: 20}
    )
    assert value == "20 no data"
    assert secondary == "100 fresh"


def test_health_summary_on_an_empty_population_does_not_read_as_healthy():
    """Zero devices is not zero problems.

    The wording is specified in the spec rather than read off the
    implementation, so this test asserts an intended sentence.
    """
    assert _health_summary({}) == ("No active devices", "No data available")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_fleet_overview.py -k health_summary -v`
Expected: FAIL — the current implementation returns `"0 fresh"` as the value.

- [ ] **Step 3: Replace `_EXCEPTION_STATES` and `_health_summary`**

Replace `components/fleet_summary.py` lines 15-47 with:

```python
#: Display noun per state. Separate from the enum values so wording can change
#: without touching the identity the styling layer joins on.
_HEALTH_NOUNS = {
    Freshness.FRESH: "fresh",
    Freshness.STALE: "stale",
    Freshness.NO_DATA: "no data",
}


def _health_summary(counts: dict[Freshness, int]) -> tuple[str, str]:
    """(value, secondary) for a Data Health card over any device population.

    The headline names the **worst state present**, walking `Freshness` in
    canonical severity order. That is the same rule as worst-of aggregation, so
    the card cannot develop a second opinion about which state matters most —
    leading with "stale" because stale is today's common case would be exactly
    that kind of drift.

    The supporting line carries the remaining states cheapest-first, always
    including the fresh count: "120 stale" alone does not tell an operator
    whether anything is still reporting.

    Shared by the fleet, plant and transformer cards so the three cannot drift
    apart in wording or in what counts as healthy.
    """
    total = sum(counts.values())

    # Zero devices is not zero problems. A population with nothing in it has
    # produced no evidence of health, and "0 fresh · no stale feeds" would be a
    # true sentence hiding the fact that nothing is monitored at all.
    if total == 0:
        return "No active devices", "No data available"

    worst_first = sorted(Freshness, key=severity_rank, reverse=True)
    present = [s for s in worst_first if counts.get(s, 0)]
    lead = present[0]
    value = f"{counts[lead]} {_HEALTH_NOUNS[lead]}"

    if lead is Freshness.FRESH:
        return value, "No stale or missing feeds"

    # Ascending severity: the reassuring number first, the worst remaining last.
    # FRESH is always shown even at zero — its absence is the point.
    rest = [
        f"{counts.get(s, 0)} {_HEALTH_NOUNS[s]}"
        for s in reversed(worst_first)
        if s is not lead and (counts.get(s, 0) or s is Freshness.FRESH)
    ]
    return value, " · ".join(rest)
```

Update the import at line 13 to include `severity_rank`:

```python
from services.monitoring_service import FleetHealth, Freshness, severity_rank
```

- [ ] **Step 4: Drop the accent from all three Data Health cards**

In `components/fleet_summary.py`, change the Data Health `kpi_card(...)` call in `fleet_kpi_cards`, `transformer_kpi_cards` and `plant_kpi_cards` from:

```python
            kpi_card("Data Health", value, secondary=secondary, accent=True),
```

to:

```python
            # No accent: --color-accent is selection colour (app.css §tokens),
            # and a permanently accented card spends the selection signal on
            # something that is never selected. State reads from the dot and
            # the wording instead.
            kpi_card("Data Health", value, secondary=secondary),
```

- [ ] **Step 5: Run the full non-db suite**

Run: `.venv/Scripts/python.exe -m pytest -m "not db" -q`
Expected: the five new tests pass. Existing tests asserting the old `"0 fresh"` wording or `kpi-card--accent` on Data Health will fail — update them to the new expectations; do not weaken an assertion to make it pass. Report the resulting count against the 526 baseline.

- [ ] **Step 6: Commit**

```bash
git add components/fleet_summary.py tests/test_fleet_overview.py
git commit -F - <<'EOF'
feat(fleet): lead Data Health with the worst state present

The headline was the fresh count, so an all-stale fleet announced itself
as "0 fresh" — technically true and operationally backwards. It now names
the worst state present, derived by walking Freshness in canonical
severity order, so NO_DATA leads over STALE rather than the lead being
hardcoded to today's common case.

Empty populations get an explicit sentence rather than "0 fresh": zero
devices is not zero problems, and a scope with nothing in it must not
read as healthy.

Data Health also loses its accent treatment. --color-accent is documented
as selection colour, and a card that is permanently accented spends that
signal on something that is never selected.

Shared by the fleet, plant and transformer cards, so all three change
together — that is the shared component working as intended.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
```

---

### Task 2: `_state` row identity and freshness style rules

Adds semantic state identity to rows and generates `dash_table` styling from the enum.

**Files:**
- Modify: `callbacks/listings.py` — `build_plant_rows` (~line 68-92), `build_transformer_rows`, `build_device_rows`
- Modify: `components/entity_table.py` — new `freshness_style_rules`, wired into `entity_table`
- Test: `tests/test_entity_table.py` *(new)*

**Interfaces:**
- Consumes: `Freshness` from `services.monitoring_service`; rows carrying `_state`
- Produces: `freshness_style_rules(column_id: str) -> list[dict]` in `components/entity_table.py`; `entity_table(..., state_column_id: str | None = None)`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_entity_table.py — new file
"""Presentation contracts for the shared entity table."""
from components.entity_table import entity_table, freshness_style_rules
from services.monitoring_service import Freshness


def test_one_style_rule_per_freshness_state():
    """A fourth state must never ship unstyled.

    Asserting the count against the enum rather than against 3 means adding a
    state breaks this test instead of silently rendering in default black.
    """
    rules = freshness_style_rules("freshness")
    assert len(rules) == len(Freshness)


def test_style_rules_join_on_state_identity_not_display_text():
    """Guards the contract: _state identifies, rendered text presents.

    "Stale" is a label that may be reworded; `stale` is the enum's value.
    """
    queries = [r["if"]["filter_query"] for r in freshness_style_rules("freshness")]
    assert '{_state} eq "stale"' in queries
    assert not any("Stale" in q for q in queries)
    assert not any("_severity" in q for q in queries)


def test_style_rules_are_scoped_to_the_named_column():
    rules = freshness_style_rules("freshness")
    assert {r["if"]["column_id"] for r in rules} == {"freshness"}


def test_entity_table_applies_state_rules_when_a_state_column_is_named():
    table = entity_table(
        table_id="t",
        columns=[{"name": "Data", "id": "freshness"}],
        rows=[],
        state_column_id="freshness",
    )
    conditional = table.children[0].style_data_conditional
    assert any("_state" in str(r.get("if", {})) for r in conditional)


def test_entity_table_without_a_state_column_adds_no_state_rules():
    table = entity_table(table_id="t", columns=[], rows=[])
    conditional = table.children[0].style_data_conditional
    assert not any("_state" in str(r.get("if", {})) for r in conditional)
```

```python
# tests/test_fleet_overview.py — append
def test_plant_rows_carry_state_identity_alongside_severity(...):
    """_severity orders, _state identifies. Both, and they must agree.

    Reuse this module's existing plant/counts/health fixtures for the
    arguments — check the file's current fixture names before writing.
    """
    rows = build_plant_rows(plants, counts, health)
    assert rows, "fixture produced no rows"
    for row in rows:
        assert row["_state"] in {s.value for s in Freshness}
        assert row["_severity"] == severity_rank(Freshness(row["_state"]))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_entity_table.py -v`
Expected: FAIL with `ImportError: cannot import name 'freshness_style_rules'`

- [ ] **Step 3: Add `freshness_style_rules` to `components/entity_table.py`**

Insert after the imports:

```python
from services.monitoring_service import Freshness

#: State -> the app.css text-colour token for that state. One named mapping,
#: beside the enum. Note NO_DATA maps to the neutral `none` token: the enum
#: value and the token name differ, which is exactly why this table exists
#: rather than an f-string built from the value.
_STATE_TEXT_TOKEN = {
    Freshness.FRESH: "--state-fresh-text",
    Freshness.STALE: "--state-stale-text",
    Freshness.NO_DATA: "--state-none-text",
}


def freshness_style_rules(column_id: str) -> list[dict]:
    """Colour a freshness column by semantic state, never by its label.

    Joins on the hidden `_state` key, whose values come from the `Freshness`
    enum. Two things this deliberately avoids: matching the rendered text
    ("Stale"), which would break the moment wording changes; and matching
    `_severity`, whose numbers exist to order rows and carry no visual meaning.

    Generated by iterating the enum, so a new state cannot ship unstyled.

    Text colour only — no background fill. Thirty tinted cells would put more
    colour on this screen than the whole Device page, and colour marks
    exceptions rather than filling a column.
    """
    return [
        {
            "if": {"filter_query": f'{{_state}} eq "{state.value}"',
                   "column_id": column_id},
            "color": f"var({_STATE_TEXT_TOKEN[state]})",
        }
        for state in Freshness
    ]
```

- [ ] **Step 4: Accept `state_column_id` in `entity_table`**

Change the signature and the `style_data_conditional` argument:

```python
def entity_table(
    table_id: str,
    columns: list[dict],
    rows: list[dict],
    sort_by: str | None = None,
    link_column_id: str | None = None,
    state_column_id: str | None = None,
) -> html.Div:
```

Add to the docstring:

```
    state_column_id: column coloured by each row's hidden `_state` key.
        Rows must carry `_state`; see freshness_style_rules.
```

Replace the `style_data_conditional` argument with:

```python
                style_data_conditional=[
                    {"if": {"row_index": "odd"}, "backgroundColor": "#f9fafb"},
                    *(freshness_style_rules(state_column_id)
                      if state_column_id else []),
                ],
```

- [ ] **Step 5: Carry `_state` on every row**

In `callbacks/listings.py`, in `build_plant_rows`, add beside the existing `_severity` line:

```python
            # Sort key only. Carried on the row like `id`, absent from
            # PLANT_COLUMNS, so it orders rows without being rendered.
            "_severity": severity_rank(rollup.state),
            # Semantic identity for styling. `_severity` orders, `_state`
            # identifies, the label presents — three jobs, three keys.
            "_state": rollup.state.value,
```

Make the identical addition in `build_transformer_rows` and `build_device_rows`.

- [ ] **Step 6: Name the state column on the three listing tables**

In `pages/plants_overview.py`, `pages/plant_detail.py` and `pages/transformer_detail.py`, add `state_column_id="freshness"` to each `entity_table(...)` call.

- [ ] **Step 7: Run the tests**

Run: `.venv/Scripts/python.exe -m pytest tests/test_entity_table.py tests/test_fleet_overview.py -v`
Expected: PASS

- [ ] **Step 8: Run the full non-db suite and commit**

Run: `.venv/Scripts/python.exe -m pytest -m "not db" -q`

```bash
git add components/entity_table.py callbacks/listings.py pages/ tests/test_entity_table.py tests/test_fleet_overview.py
git commit -F - <<'EOF'
feat(table): colour freshness cells from state identity, not label text

Rows already carried `_severity` for ordering. They now also carry
`_state`, the Freshness enum's own value, and dash_table styling joins on
that. Three keys, three jobs: `_severity` orders, `_state` identifies, the
rendered label presents.

Styling from the label would have broken on any rewording, and styling
from `_severity` would have given 0/1/2 a visual meaning they were never
supposed to carry.

The rules are generated by iterating Freshness, so a fourth state cannot
ship unstyled — asserted against len(Freshness) rather than against 3.

Text colour only, no background fill: thirty tinted cells would put more
colour on the Fleet screen than the entire Device page.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
```

---

### Task 3: Right-align numeric columns from the column spec

**Files:**
- Modify: `components/entity_table.py` — `style_cell_conditional` construction
- Test: `tests/test_entity_table.py`

**Interfaces:**
- Consumes: the `columns` list already passed to `entity_table`
- Produces: no new public names

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_entity_table.py — append
def test_numeric_columns_are_right_aligned_from_their_own_type():
    """Alignment is derived, not listed.

    A per-page list of "which columns are numbers" is a second source of
    truth that drifts the first time a column is added.
    """
    table = entity_table(
        table_id="t",
        columns=[
            {"name": "Plant", "id": "plant"},
            {"name": "Devices", "id": "devices", "type": "numeric"},
        ],
        rows=[],
    )
    conditional = table.children[0].style_cell_conditional
    aligned = {
        r["if"]["column_id"]: r["textAlign"]
        for r in conditional if "textAlign" in r
    }
    assert aligned["devices"] == "right"
    assert "plant" not in aligned


def test_numeric_headers_are_right_aligned_too():
    table = entity_table(
        table_id="t",
        columns=[{"name": "Devices", "id": "devices", "type": "numeric"}],
        rows=[],
    )
    header = table.children[0].style_header_conditional
    assert {"if": {"column_id": "devices"}, "textAlign": "right"} in header
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/Scripts/python.exe -m pytest tests/test_entity_table.py -k align -v`
Expected: FAIL — `style_header_conditional` is not set, and no `textAlign` rule exists.

- [ ] **Step 3: Derive alignment inside `entity_table`**

Immediately before the existing `style_cell_conditional` assignment:

```python
    # Derived from the column spec rather than a per-page list: 900 < 1,000 <
    # 12,000 only reads correctly right-aligned, and the columns that need it
    # already declare `type: "numeric"` so native sorting works. One
    # declaration, two behaviours.
    numeric_ids = [c["id"] for c in columns if c.get("type") == "numeric"]
    numeric_alignment = [
        {"if": {"column_id": cid}, "textAlign": "right"} for cid in numeric_ids
    ]
```

Change the `style_cell_conditional` assignment to append it:

```python
    style_cell_conditional = numeric_alignment + (
        [
            ...existing link-column dict unchanged...
        ]
        if link_column_id
        else []
    )
```

Add to the `DataTable(...)` arguments:

```python
                style_header_conditional=[
                    {"if": {"column_id": cid}, "textAlign": "right"}
                    for cid in numeric_ids
                ],
```

- [ ] **Step 4: Run the tests**

Run: `.venv/Scripts/python.exe -m pytest tests/test_entity_table.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add components/entity_table.py tests/test_entity_table.py
git commit -m "feat(table): right-align numeric columns from their declared type" -m "Derived from the column spec's existing type: numeric declaration rather than a per-page list of column ids, so one declaration drives both native sorting and alignment and there is no second list to drift." -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 4: Fleet Overview naming

**Files:**
- Modify: `pages/plants_overview.py:16-22`, `pages/plant_detail.py:18`, `pages/transformer_detail.py:20`, `pages/device_dashboard.py:55`
- Test: `tests/test_fleet_naming.py` *(new)*

**Interfaces:**
- Consumes: `breadcrumb(items)` — unchanged
- Produces: no new names

**Do not touch** `components/fleet_summary.py:68`, `kpi_card("Plants", ...)`. That label counts plants and stays "Plants".

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_fleet_naming.py — new file
"""The Fleet vocabulary.

The route stays /plants and every domain identifier is unchanged — this is a
presentation rename only. These tests pin the boundary so a future edit cannot
quietly turn a label change into a routing change.
"""
import pages.device_dashboard as device_dashboard
import pages.plant_detail as plant_detail
import pages.plants_overview as plants_overview
import pages.transformer_detail as transformer_detail
from tests.dash_tree import find_by_class, walk


def _breadcrumb_labels(layout):
    return [
        n.children
        for n in walk(layout)
        if isinstance(getattr(n, "className", None), str)
        and n.className in {"breadcrumb__link", "breadcrumb__current"}
    ]


def test_fleet_page_title_and_subtitle():
    layout = plants_overview.layout()
    headings = [n for n in walk(layout) if type(n).__name__ == "H1"]
    assert headings[0].children == "Fleet Overview"
    subtitle = find_by_class(layout, "page__subtitle")[0]
    assert "monitored plants" in subtitle.children


def test_breadcrumb_root_reads_fleet_on_the_fleet_page():
    assert _breadcrumb_labels(plants_overview.layout())[0] == "Fleet"


def test_breadcrumb_root_reads_fleet_on_plant_detail():
    labels = _breadcrumb_labels(plant_detail.layout("plant-01"))
    assert labels[0] == "Fleet"


def test_breadcrumb_root_reads_fleet_on_transformer_detail():
    labels = _breadcrumb_labels(
        transformer_detail.layout("plant-01-t1", plant_id="plant-01")
    )
    assert labels[0] == "Fleet"


def test_the_route_is_still_plants():
    """The rename is vocabulary only. /plants and every id are untouched."""
    links = [
        n.href for n in walk(plants_overview.layout())
        if getattr(n, "href", None)
    ] + [
        n.href for n in walk(plant_detail.layout("plant-01"))
        if getattr(n, "href", None)
    ]
    assert any(h == "/plants" for h in links)
    assert not any("/fleet" in h for h in links)


def test_the_plants_kpi_card_still_counts_plants():
    """The card label is a domain noun, not the page name. It does not change."""
    import components.fleet_summary as fleet_summary
    source = open(fleet_summary.__file__, encoding="utf-8").read()
    assert 'kpi_card("Plants"' in source
```

Check `plant_detail.layout` and `transformer_detail.layout` signatures before running; adjust the call arguments above to match.

- [ ] **Step 2: Run to verify failure**

Run: `.venv/Scripts/python.exe -m pytest tests/test_fleet_naming.py -v`
Expected: FAIL — labels read `"Plants"`, H1 reads `"Plants"`.

- [ ] **Step 3: Rename the Fleet page header**

`pages/plants_overview.py` lines 15-22:

```python
            app_header(
                breadcrumb_children=breadcrumb([("Fleet", None)]),
            ),
            html.H1("Fleet Overview"),
            # Filled by the listing callback so the count comes from the same
            # hierarchy query as the Plants card, never a literal.
            html.P(id="fleet-subtitle", className="page__subtitle"),
```

- [ ] **Step 4: Rename the breadcrumb root at the three child pages**

In `pages/plant_detail.py:18`, `pages/transformer_detail.py:20` and `pages/device_dashboard.py:55`, change:

```python
                    ("Plants", "/plants"),
```

to:

```python
                    # Label only — the route stays /plants (spec §3.1).
                    ("Fleet", "/plants"),
```

- [ ] **Step 5: Run the tests**

Run: `.venv/Scripts/python.exe -m pytest tests/test_fleet_naming.py -v`
Expected: the subtitle test still FAILS (the slot is empty until Task 5 fills it). Mark it `@pytest.mark.xfail(reason="subtitle filled by the callback in Task 5", strict=True)` and remove the marker in Task 5. All other tests PASS.

- [ ] **Step 6: Commit**

```bash
git add pages/ tests/test_fleet_naming.py
git commit -F - <<'EOF'
feat(fleet): rename the page to Fleet Overview, breadcrumb root to Fleet

Presentation vocabulary only. The route stays /plants, and every plant id,
table name and domain identifier is untouched — asserted, so a later edit
cannot quietly turn a label change into a routing change.

The breadcrumb root moves with the page title. Leaving it as "Plants"
would have given the page one name in its heading and another in every
breadcrumb pointing at it.

The Plants KPI card keeps its label: that word counts plants, it does not
name the page.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
```

---

### Task 5: One render instant

Threads a single `now` through the fleet render so the header stamp and every row's freshness are evaluated at the same moment, and fills the subtitle and refresh line.

**Files:**
- Modify: `services/monitoring_service.py:342-356` (`get_fleet_health`)
- Modify: `callbacks/listings.py` — `populate_overview`
- Modify: `pages/plants_overview.py` — add the refresh slot
- Test: `tests/test_fleet_overview.py`

**Interfaces:**
- Consumes: `fleet_health_from_rows(rows, now=None)` — already accepts `now`
- Produces: `get_fleet_health(now: datetime | None = None) -> FleetHealth`; `format_render_stamp(now: datetime) -> str` in `components/fleet_summary.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_fleet_overview.py — append
from datetime import datetime, timezone

from components.fleet_summary import format_render_stamp


def test_render_stamp_is_absolute_utc_never_relative():
    """There is no dcc.Interval on this page.

    A relative "1 min ago" would freeze at render and quietly lie. An absolute
    stamp is honest about being a render time. "updated" is banned outright —
    it reads as sensor freshness, which is a different concept.
    """
    stamp = format_render_stamp(datetime(2026, 8, 9, 11, 24, tzinfo=timezone.utc))
    assert stamp == "Page refreshed 09 Aug 2026 11:24 UTC"
    assert "ago" not in stamp
    assert "updated" not in stamp.lower()


def test_get_fleet_health_accepts_an_injected_instant(monkeypatch):
    """The header stamp and the rows' freshness must share one instant.

    Without the pass-through, get_fleet_health called the clock itself, so the
    header could stamp T while the rows were evaluated at T minus a few
    hundred milliseconds. Asserting an injected value proves one instant is
    used, which comparing two generated times for proximity never could.
    """
    import services.monitoring_service as ms

    seen = {}

    def fake_from_rows(rows, now=None):
        seen["now"] = now
        return ms.fleet_health_from_rows([], now)

    monkeypatch.setattr(ms.repo, "latest_reading_times", lambda keys: [])
    monkeypatch.setattr(ms, "fleet_health_from_rows", fake_from_rows)

    frozen = datetime(2026, 8, 9, 11, 24, tzinfo=timezone.utc)
    ms.get_fleet_health(now=frozen)
    assert seen["now"] == frozen
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/Scripts/python.exe -m pytest tests/test_fleet_overview.py -k "render_stamp or injected_instant" -v`
Expected: FAIL — `format_render_stamp` does not exist; `get_fleet_health()` takes no arguments.

- [ ] **Step 3: Add the `now` pass-through**

`services/monitoring_service.py`, change the signature and the call:

```python
def get_fleet_health(now: datetime | None = None) -> FleetHealth:
```

Append to the docstring:

```
    `now` is threaded through so one render evaluates every device against a
    single instant. The Fleet header stamps that same instant, so the page
    cannot claim to have refreshed at a moment different from the one its
    freshness column was computed at.
```

Change the return to:

```python
    return fleet_health_from_rows(
        repo.latest_reading_times([m.key for m in ordered_metrics()]), now
    )
```

- [ ] **Step 4: Add `format_render_stamp`**

Append to `components/fleet_summary.py`:

```python
def format_render_stamp(now: datetime) -> str:
    """When this Fleet snapshot was rendered — absolute, never relative.

    There is no `dcc.Interval` on the Fleet page, so a relative label would
    freeze at first render and quietly become wrong. Absolute UTC is honest
    about what it is.

    "Page refreshed" is deliberately not "Last updated": updated reads as
    sensor freshness, which the Data column already reports and which this
    line has nothing to do with.
    """
    return f"Page refreshed {now.strftime('%d %b %Y %H:%M')} UTC"
```

Add `from datetime import datetime` to that module's imports.

- [ ] **Step 5: Add the header slots to the layout**

In `pages/plants_overview.py`, after the `fleet-subtitle` paragraph:

```python
            html.P(id="fleet-refreshed", className="page__meta"),
```

- [ ] **Step 6: Fill both slots from one instant in the callback**

In `callbacks/listings.py`, add two `Output`s to `populate_overview` — `Output("fleet-subtitle", "children")` and `Output("fleet-refreshed", "children")` — and inside it:

```python
        # One instant for the whole render. Taken once here and passed to both
        # the freshness computation and the header, so the stamp cannot name a
        # moment different from the one the rows were evaluated at.
        rendered_at = datetime.now(timezone.utc)
        subtitle = []
```

Inside `build()`, replace the `get_fleet_health()` call with `get_fleet_health(rendered_at)`, and after computing `plants` append:

```python
            subtitle.append(
                f"{len(plants)} monitored plants across the active fleet"
            )
```

Return the two new values, with the no-update branch and the error branch both extended:

```python
        return (rows, columns, error, (cards[0] if cards else None),
                (subtitle[0] if subtitle else ""),
                format_render_stamp(rendered_at))
```

Import `datetime`, `timezone`, and `format_render_stamp`.

- [ ] **Step 7: Remove the xfail from Task 4's subtitle test, run, commit**

Run: `.venv/Scripts/python.exe -m pytest -m "not db" -q`

```bash
git add services/monitoring_service.py components/fleet_summary.py callbacks/listings.py pages/plants_overview.py tests/
git commit -F - <<'EOF'
feat(fleet): render the whole Fleet snapshot from one instant

get_fleet_health now takes `now` and passes it to fleet_health_from_rows,
which already accepted one. Before this the function called the clock
itself, so a header stamp and the freshness column it sits above could
name instants a few hundred milliseconds apart.

The header carries an absolute UTC stamp rather than a relative age.
There is no dcc.Interval on this page, so "1 min ago" would freeze at
render and quietly lie; adding an interval is a callback-architecture
change and out of this slice. "Page refreshed" stays distinct from data
freshness — the word "updated" appears nowhere.

The plant count in the subtitle is read from the same hierarchy query
that feeds the Plants card, never a literal.

Tested by injecting a single frozen instant and asserting the exact value
reaches both consumers, rather than generating two timestamps and
checking they are close.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
```

---

### Task 6: Tokens, containers and the Fleet type scale

**Files:**
- Modify: `assets/app.css` — `:root` block (lines ~36-49), `.page` (line ~554), `.kpi-row--fleet`
- Modify: `pages/plants_overview.py` — container class
- Test: none. CSS is verified by computed style in the browser (Task 9), never by asserting stylesheet text — a source-text assertion passed while the browser computed something else twice in this project's history.

- [ ] **Step 1: Add the tokens**

In `assets/app.css`, after the existing type scale block:

```css
  /* Fleet-scoped additions (Fleet Overview v2 §4.1).
     Additive: every token Device consumes keeps its value, so the frozen
     Device reference is unchanged by construction rather than by
     re-validation. --fs-micro and --fs-table are deliberately absent — they
     would duplicate the values AND the roles of --fs-meta and --fs-body, and
     a second name for an existing role is the drift this layer prevents. */
  --w-monitoring:   1550px;   /* a maximum, never a target width */
  --w-reading:      1200px;
  --fs-fleet-title:   24px;   /* Device keeps --fs-page-title: 22px */
  --fs-fleet-kpi:     30px;   /* Device keeps --fs-kpi: 26px */
  --fs-fleet-body:    14px;
```

- [ ] **Step 2: Add the containers**

Replace the `.page` rule:

```css
/* .page stays the default reading-width container: Device, Plant and
   Transformer are unaffected by anything below. */
.page {
  max-width: var(--w-reading);
  margin: 0 auto;
  padding: 0 20px 40px 20px;
}

/* Monitoring width — dashboards, summaries and hierarchy content.
   max-width, never width: at 1366 the page fills the viewport minus gutters
   (~1318 px), at 1920 it caps at 1550 and the remainder becomes whitespace.
   Gutters are restated rather than inherited so widening the container can
   never leave content glued to the viewport edge. */
.page--monitoring {
  max-width: var(--w-monitoring);
  padding: 0 24px 40px 24px;
}

/* Scoped title override. The global .page h1 keeps its 22 px so the other
   three pages are untouched; specificity does the work, not !important. */
.page--monitoring h1 { font-size: var(--fs-fleet-title); }

.page__subtitle { font-size: var(--fs-fleet-body); color: var(--color-muted); margin: 0 0 4px 0; }
.page__meta     { font-size: var(--fs-meta);       color: var(--color-muted); margin: 0 0 20px 0; }
```

- [ ] **Step 3: Add the Fleet KPI row rules**

After the `.kpi-row` block:

```css
/* Data Health carries more information than the three structural counts, so
   it gets more room. Device's .kpi-row is untouched. */
.kpi-row--fleet {
  grid-template-columns: repeat(3, minmax(0, 1fr)) 1.5fr;
}
.kpi-row--fleet .kpi-card__value { font-size: var(--fs-fleet-kpi); }
```

- [ ] **Step 4: Opt the Fleet page into monitoring width**

`pages/plants_overview.py`:

```python
        className="page page--monitoring page--plants-overview",
```

- [ ] **Step 5: Verify the suite is unaffected, then commit**

Run: `.venv/Scripts/python.exe -m pytest -m "not db" -q`

```bash
git add assets/app.css pages/plants_overview.py
git commit -F - <<'EOF'
style(fleet): add monitoring width and the Fleet-scoped type scale

Additive tokens and a modifier class rather than a global typography
migration. Every token Device consumes keeps its value, so the frozen
reference is unchanged by construction instead of by re-validation — which
is the whole reason this slice can stay Fleet-scoped.

--w-monitoring is a maximum, never a target: at 1366 the page fills the
viewport minus gutters, at 1920 it caps and the rest becomes whitespace.
Gutters are restated on the modifier rather than inherited, so widening
cannot glue content to the viewport edge.

--fs-micro and --fs-table from the phase sketch are deliberately omitted.
They duplicate the values and the roles of --fs-meta and --fs-body, and a
second name for an existing role is exactly the drift a token layer exists
to prevent.

No test: CSS is verified by computed style in the browser. Asserting
stylesheet source text has passed twice in this project while the browser
computed something else.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
```

---

### Task 7: Table density and OBS-2 overflow

**Files:**
- Modify: `components/entity_table.py` — `style_cell` padding
- Modify: `assets/app.css` — the reveal rule
- Test: `tests/test_entity_table.py` (configuration only; behaviour is verified in Task 9)

**Contract: never silently clip identity or metadata text.**

- [ ] **Step 1: Write the failing test**

```python
# tests/test_entity_table.py — append
def test_the_identity_column_wraps_and_never_truncates():
    """Half of "Itaipu Binacional Dam (Paraguay part)" is not an identity.

    It is also the cell the operator clicks to navigate, so it is the one
    column that must never hide characters.
    """
    table = entity_table(
        table_id="t",
        columns=[{"name": "Plant", "id": "plant"}],
        rows=[],
        link_column_id="plant",
    )
    rule = next(
        r for r in table.children[0].style_cell_conditional
        if r["if"].get("column_id") == "plant" and "whiteSpace" in r
    )
    assert rule["whiteSpace"] == "normal"


def test_every_other_column_ellipsises_rather_than_clipping():
    """Silent clipping is the failure mode OBS-2 exists to prevent."""
    table = entity_table(table_id="t", columns=[], rows=[])
    assert table.children[0].style_cell["textOverflow"] == "ellipsis"


def test_rows_are_denser_than_the_default():
    table = entity_table(table_id="t", columns=[], rows=[])
    assert table.children[0].style_cell["padding"] == "11px 12px"
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/Scripts/python.exe -m pytest tests/test_entity_table.py -k "wraps or ellipsises or denser" -v`
Expected: the padding test FAILS (currently `8px 12px`); the other two PASS — they pin behaviour that already exists so a later edit cannot remove it silently.

- [ ] **Step 3: Increase row density**

In `components/entity_table.py`, change `style_cell`'s padding to `"11px 12px"` and add a comment:

```python
                    # ~40 px rows against a 40-44 px target. A target, not a
                    # guarantee: rows whose plant name wraps are taller by
                    # design, which is the correct trade for never hiding an
                    # identity.
                    "padding": "11px 12px",
```

- [ ] **Step 4: Add the column-scoped reveal**

Replace the OBS-2 comment block in `assets/app.css` with:

```css
/* OBS-2 — never silently clip identity or metadata text.
   The ellipsis itself is set on the `td` through style_cell in
   components/entity_table.py: dash_table sets `text-overflow: inherit` on
   td div.dash-cell-value with a 4-class selector, so a rule here targeting
   that div loses the cascade and does nothing.

   The reveal must be CSS because inline style_cell_conditional cannot carry
   pseudo-classes. It is scoped to the three text columns by name — a generic
   .dash-cell rule would let numeric and status cells change height on focus
   and make the whole table jump.

   Keyboard as well as pointer: dash_table stamps tabindex on every cell, so
   :focus-within fires on Tab. */
.entity-table-wrapper td[data-dash-column="country"]:hover,
.entity-table-wrapper td[data-dash-column="country"]:focus-within,
.entity-table-wrapper td[data-dash-column="fuel"]:hover,
.entity-table-wrapper td[data-dash-column="fuel"]:focus-within,
.entity-table-wrapper td[data-dash-column="freshness"]:hover,
.entity-table-wrapper td[data-dash-column="freshness"]:focus-within {
  white-space: normal;
  overflow: visible;
}
```

- [ ] **Step 5: Verify the attribute exists, in the browser**

Start the app, open `/plants`, and in the console run:

```js
document.querySelector('#plants-table td').attributes
```

- If `data-dash-column` is present → keep the rule as written.
- If absent → fall back to `td.dash-cell.column-N`, and add a comment recording that the selector breaks silently if columns are reordered.
- If neither reveal works cleanly → **wrap those columns instead**. A rule that reads correctly in the stylesheet and computes to nothing is worse than a plainer mechanism that works; that was DEF-1's exact failure mode.

Record which branch was taken in the acceptance document.

- [ ] **Step 6: Run the suite and commit**

Run: `.venv/Scripts/python.exe -m pytest -m "not db" -q`

```bash
git add components/entity_table.py assets/app.css tests/test_entity_table.py
git commit -F - <<'EOF'
feat(table): denser rows and an accessible reveal for truncated text

Rows go to ~40 px. The contract OBS-2 exists to enforce is that text is
never silently clipped: the Plant identity column wraps and never
truncates, and the three secondary text columns ellipsise with the full
value revealed on hover and on keyboard focus.

The reveal is column-scoped rather than applied to every .dash-cell. A
generic rule would let numeric and status cells change height on focus
and make the table jump under the operator's cursor.

It has to be CSS at all because inline style_cell_conditional cannot
carry pseudo-classes, and it targets cells by column name rather than
index so reordering columns cannot silently restyle the wrong one.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
```

---

### Task 8: Correct the stale column spec in the layout

**Files:**
- Modify: `pages/plants_overview.py:29-42`
- Test: `tests/test_fleet_overview.py`

**Do not** import `PLANT_COLUMNS` from `callbacks.listings`, even if no cycle occurs. Pages define layout; callbacks consume it.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_fleet_overview.py — append
def test_the_layout_column_spec_matches_the_callback_that_replaces_it():
    """Two definitions, deliberately, but they must agree.

    The layout's spec is what renders for the first paint; the callback
    replaces it on first fire. They drifted once — the layout still said
    `plant_id` and "Primary Fuel" long after the callback said `plant` and
    "Fuel" — so the first thing a reader found was the wrong one.

    Importing PLANT_COLUMNS here would fix the duplication by inverting the
    dependency: pages would depend on their own callback module. This test is
    the cheaper guard.
    """
    from callbacks.listings import PLANT_COLUMNS
    from tests.dash_tree import walk

    import pages.plants_overview as plants_overview

    table = next(
        n for n in walk(plants_overview.layout())
        if getattr(n, "id", None) == "plants-table"
    )
    assert table.columns == PLANT_COLUMNS
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/Scripts/python.exe -m pytest tests/test_fleet_overview.py -k column_spec -v`
Expected: FAIL — the layout uses `plant_id`, `"Primary Fuel"`, `capacity_mw` with a different name, and declares no `type` on `country`/`fuel`.

- [ ] **Step 3: Correct the literal in place**

Replace the `columns=[...]` list in `pages/plants_overview.py` with a copy of `PLANT_COLUMNS` and a comment explaining why it is duplicated rather than imported:

```python
                # Deliberately duplicated from callbacks.listings.PLANT_COLUMNS
                # rather than imported: pages define layout, callbacks consume
                # it, and a page importing its own callback module inverts that.
                # The callback replaces these on first fire; this spec is what
                # renders for the first paint, so it must agree. A test asserts
                # the two stay identical.
                columns=[
                    {"name": "Plant", "id": "plant"},
                    {"name": "Country", "id": "country"},
                    {"name": "Fuel", "id": "fuel"},
                    {"name": "Capacity (MW)", "id": "capacity_mw", "type": "numeric"},
                    {"name": "Transformers", "id": "transformers", "type": "numeric"},
                    {"name": "Devices", "id": "devices", "type": "numeric"},
                    {"name": "Data", "id": "freshness"},
                ],
```

- [ ] **Step 4: Run and commit**

Run: `.venv/Scripts/python.exe -m pytest -m "not db" -q`

```bash
git add pages/plants_overview.py tests/test_fleet_overview.py
git commit -F - <<'EOF'
fix(fleet): correct the stale column spec in the Fleet layout

The layout declared plant_id / "Primary Fuel" while the callback that
replaces it on first fire declared plant / "Fuel". Dead, contradictory,
and the first thing a reader of the page finds.

Corrected in place rather than imported from callbacks.listings.
Importing would have removed the duplication by inverting the dependency
direction — pages would depend on their own callback module — and the
absence of a circular import is not evidence that a dependency is
correct. Two definitions that agree, guarded by a test, is the cheaper
smell.

Relocating the constant into a shared module is deliberately deferred: it
is a structural change and does not belong in a visual slice.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
```

---

### Task 9: Browser acceptance

Measured verification. **No opportunistic fixes** — anything found outside this slice is logged.

**Files:**
- Create: `docs/UX_ACCEPTANCE_FLEET.md`
- Create: `docs/ux-baseline/acceptance-fleet-1366.png`, `acceptance-fleet-1920.png`
- Modify: `docs/UX_DEBT.md` — correct the stale 390 px figure

- [ ] **Step 1: Capture before-screenshots**

`git stash`, start the app, capture `/plants` at 1366×768 and 1920×1080, `git stash pop`.

- [ ] **Step 2: Measure the Fleet layout at both widths**

Record actual numbers for: page content width and gutters; the four KPI card widths; KPI row height; KPI value font-size; table row height.

Confirm: 1550 caps at 1920 and fills at 1366; the three structural cards do not read as empty slabs at ~1318 px. **If they do, that is a card-layout problem to log — never a reason to restore the 1200 px cap.**

- [ ] **Step 3: Verify overflow by computed style, not by stylesheet**

For a Plant cell and a Country/Fuel/Data cell, at rest and under focus:

```js
const s = getComputedStyle(cell);
[s.whiteSpace, s.overflow, s.textOverflow]
```

Then: Tab to a truncated cell and confirm the reveal fires and the focus ring is still DEF-1's single tight ring, not a doubled one; confirm revealed text does not overlap the neighbouring cell. Record which of Task 7 Step 5's three branches was taken.

- [ ] **Step 4: Test unusual data**

`Itaipu Binacional Dam (Paraguay part)`, `MONTALTO (Alessandro Volta)`, `Niederaussem power station`, `Bełchatów`; sorting and filtering; keyboard-only navigation; the database-error path.

- [ ] **Step 5: Cross-page regression**

- **Device** — measure chart top and KPI row height. This settles the 390-vs-406 disagreement: the measured value is the baseline.
- **Plant** and **Transformer** — Data Health is exception-led and unaccented on both.

- [ ] **Step 6: Correct the stale figure in `docs/UX_DEBT.md`**

UXD-1's closing line cites a 390 px chart-top budget. Replace it with the measured value and a note that it was re-measured during this slice, so the ambiguity is not carried forward again.

- [ ] **Step 7: Write `docs/UX_ACCEPTANCE_FLEET.md`**

Sections: measurements at both widths; computed-style results; the reveal branch taken; unusual-data results; cross-page regression including the settled Device baseline; observations logged but **not** fixed.

- [ ] **Step 8: Run the full suite**

Run: `.venv/Scripts/python.exe -m pytest -m "not db" -q`, then `.venv/Scripts/python.exe -m pytest -q` with Docker up. **If Docker is not running, say so plainly rather than report a partial run as green.** Report both counts against the 526 baseline.

- [ ] **Step 9: Commit**

```bash
git add docs/
git commit -F - <<'EOF'
test(ux): Fleet Overview v2 acceptance pass

Measured verification at 1366x768 and 1920x1080. Overflow behaviour
checked with getComputedStyle at rest and under keyboard focus rather
than by reading the stylesheet — source text has passed twice in this
project while the browser computed something else.

Settles the Device chart-top baseline by measurement. UX_DEBT.md cited
390 px and the device-analytics acceptance pass left 406 px; the browser
value is now recorded in one place and the stale figure corrected, so the
ambiguity is not carried forward a third time.

Observations outside this slice are logged, not fixed.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
```

---

## Self-review

**Spec coverage.** §3.1 naming → Task 4. §3.2 Data Health → Task 1. §3.3 width → Task 6. §3.4 overflow → Task 7. §3.5 tokens and `_state` → Tasks 6, 2. §4 tokens/containers → Task 6. §5 header → Tasks 4, 5. §6 KPI cards → Tasks 1, 6. §7.1 column spec → Task 8. §7.2 alignment → Task 3. §7.3 density → Task 7. §7.4 `_state` join → Task 2. §7.5 OBS-2 → Tasks 7, 9. §9.1 unit tests → Tasks 1-5, 7, 8. §9.2-9.5 browser → Task 9. §10 output → Task 9. No gaps.

**Known ordering dependency.** Task 4's subtitle test is `xfail(strict=True)` until Task 5 fills the slot. Task 5 Step 7 removes the marker. Executing Task 5 without Task 4 will fail on the missing `fleet-subtitle` id.

**Type consistency.** `_health_summary(counts) -> tuple[str, str]` unchanged across Tasks 1 and 5. `freshness_style_rules(column_id)` defined in Task 2, consumed in Task 2 only. `entity_table(..., state_column_id=...)` defined in Task 2, used unchanged in Tasks 3 and 7. `get_fleet_health(now=None)` defined in Task 5, called in Task 5. `format_render_stamp(now)` defined and consumed in Task 5. `_state` written in Task 2, read in Task 2. No name appears in two spellings.

**Fixture caveat.** Tasks 2 and 8 reuse existing fixtures in `tests/test_fleet_overview.py`; check the current fixture names before writing, and check `plant_detail.layout` / `transformer_detail.layout` signatures before writing Task 4's tests.
