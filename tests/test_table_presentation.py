"""Table and toolbar presentation contracts.

The DataTable ships its own stylesheet, and one of its rules sets the whole
table in `monospace` with a three-class selector that beats `body`. Every
table in the application inherited it, so plant names rendered as code. The
override lives here rather than per page for the same reason: it is one
defect, not six.
"""
from pathlib import Path
import re

import pytest


@pytest.fixture(scope="module")
def css():
    text = (Path(__file__).resolve().parents[1] / "assets" / "app.css").read_text(
        encoding="utf-8"
    )
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


def rule(css, selector):
    match = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", css)
    assert match, f"Missing rule: {selector}"
    return match.group(1)


#: dash_table's own rule, the one that puts every table in monospace.
DASH_MONOSPACE_RULE = (
    ".dash-table-container .dash-spreadsheet-container "
    ".dash-spreadsheet-inner table"
)

#: Ours. It must out-specify the rule above, not merely exist.
OVERRIDE_RULE = ".entity-table-wrapper " + DASH_MONOSPACE_RULE


class TestTableTypography:
    def test_tables_do_not_render_in_the_dash_default_monospace(self, css):
        assert "font-family: inherit" in rule(css, OVERRIDE_RULE)

    def test_override_outweighs_the_dash_rule_it_replaces(self, css):
        """Both selectors end in the same type, so class count decides. An
        override that merely exists loses silently: no error, no warning, and
        a table still rendering plant names as code. Counting classes is what
        this test is for — an earlier version asserted only that the selector
        had "at least two" and passed against a losing rule."""
        assert OVERRIDE_RULE.count(".") > DASH_MONOSPACE_RULE.count(".")
        assert css.count(OVERRIDE_RULE) == 1

    def test_digits_stay_aligned_down_a_column(self, css):
        """Device codes and capacities are read as columns of figures; a
        proportional face without tabular figures makes them ragged."""
        assert "font-variant-numeric: tabular-nums" in rule(css, OVERRIDE_RULE)


class TestToolbar:
    def test_search_does_not_consume_the_whole_bar(self, css):
        """It rendered at 1175px of a 1502px toolbar — 78% of the row for one
        field."""
        search = rule(css, ".device-admin-toolbar__search")
        assert "max-width" in search

    def test_register_is_pushed_away_from_the_filters(self, css):
        """Filtering and creating are different intents; they should not read
        as one row of equal controls."""
        assert "margin-left: auto" in rule(css, ".device-admin-toolbar__register-btn")

    def test_register_reads_as_the_pages_primary_action(self, css):
        """It was white-on-white with a hairline border — the only creating
        action on the page, styled as a label."""
        button = rule(css, ".device-admin-toolbar__register-btn")
        assert "background: var(--color-brand)" in button
        assert "color: #fff" in button


class TestStateAxesStayDistinct:
    def test_administrative_status_remains_a_neutral_outlined_label(self, css):
        """Guards the recorded decision at the administrative-axis rule: the
        two state axes must not collapse into one traffic-light system."""
        status = rule(
            css,
            '.entity-table-wrapper--administrative-axis td[data-dash-column="status"] .dash-cell-value',
        )
        assert "text-transform: uppercase" in status
        assert "border: 1px solid" in status
        assert "var(--state-" not in status

    def test_freshness_gains_a_dot_without_becoming_a_chip(self, css):
        marker = rule(
            css,
            '.entity-table-wrapper--freshness-axis td[data-dash-column="freshness"] .dash-cell-value::before',
        )
        assert "border-radius: 50%" in marker
        assert "background: currentColor" in marker

    def test_the_dot_inherits_the_semantic_colour_already_generated(self, css):
        """`entity_table.freshness_style_rules` colours the cell per state.
        `currentColor` means the dot can never disagree with the label beside
        it, and no state colour is restated here."""
        marker = rule(
            css,
            '.entity-table-wrapper--freshness-axis td[data-dash-column="freshness"] .dash-cell-value::before',
        )
        assert "#" not in marker

class TestTableStructure:
    """The header was `{"fontWeight": "600", "backgroundColor": "#f9fafb"}` and
    the odd-row stripe was the same `#f9fafb`, so the header carried the same
    fill as every other row. With `style_as_list_view=True` removing vertical
    borders as well, nothing separated column names from data.

    The guard against those two colours matching is gone with the stripe
    itself — there is no second fill left to collide with. What replaces it:
    `test_header_is_separated_by_a_rule_rather_than_a_fill` below, and
    `TestOneSeparationSystem`, which keeps the striping from coming back.
    """

    def header(self):
        from components.entity_table import entity_table
        from dash import dash_table

        from tests.dash_tree import walk

        table = next(
            n for n in walk(entity_table("t", [{"name": "A", "id": "a"}], []))
            if isinstance(n, dash_table.DataTable)
        )
        return table.style_header, table.style_data_conditional

    def test_header_reads_as_the_tables_heading(self):
        """First pass made it an 11px muted label, which disappeared against
        the data. It is the heading of the table, so it carries the body text
        colour and sits above the cells in size, not below them."""
        style_header, _ = self.header()
        assert style_header["fontSize"] == "13px"
        assert style_header["textTransform"] == "uppercase"
        assert style_header["letterSpacing"] == "0.05em"
        assert style_header["color"] == "var(--color-text)"

    def test_header_is_separated_by_a_rule_rather_than_a_fill(self):
        style_header, _ = self.header()
        assert "2px" in style_header["borderBottom"]

    def test_sort_affordance_is_not_flush_against_the_label(self):
        """It rendered as "⇅Device", which reads as a typo rather than a
        control."""
        style_header, _ = self.header()
        assert style_header["paddingRight"] != style_header.get("paddingLeft")

class TestColumnWidths:
    """Uncapping the page handed the table ~2,100px, and dash_table spreads
    slack across every column: Plant took 749px for names that draw at ~150,
    Transformer 320px for "ku01". Constraining the short columns and leaving
    the identity column unconstrained makes the name absorb the slack
    instead.
    """

    def conditional(self, **kwargs):
        from components.entity_table import entity_table
        from dash import dash_table

        from tests.dash_tree import walk

        columns = [
            {"name": "Device", "id": "device"},
            {"name": "Plant", "id": "plant"},
        ]
        table = next(
            n for n in walk(entity_table("t", columns, [], **kwargs))
            if isinstance(n, dash_table.DataTable)
        )
        return table.style_cell_conditional

    def rules_for(self, column_id, **kwargs):
        return [
            r for r in self.conditional(**kwargs)
            if r["if"].get("column_id") == column_id and "width" in r
        ]

    def test_a_constrained_column_is_pinned_not_merely_suggested(self):
        """width alone is a suggestion to dash_table; without min and max it
        still grows when there is slack to hand out."""
        rule = self.rules_for("device", column_widths={"device": "120px"})[0]
        assert rule["width"] == "120px"
        assert rule["minWidth"] == "120px"
        assert rule["maxWidth"] == "120px"

    def test_columns_left_out_stay_free_to_absorb_the_slack(self):
        assert self.rules_for("plant", column_widths={"device": "120px"}) == []

    def test_no_widths_declared_leaves_every_column_as_it_was(self):
        assert not any("width" in r for r in self.conditional())


class TestDeviceManagementColumns:
    """Leaving one column unconstrained to "absorb the slack" was wrong at
    this width: Plant took 1,320px for 143px of text, and the row read as a
    name followed by a void. Every column now takes a proportional share, so
    slack becomes even breathing room instead of one gap.
    """

    def widths(self):
        from pages.device_admin import DEVICE_ADMIN_COLUMN_WIDTHS

        return DEVICE_ADMIN_COLUMN_WIDTHS

    def test_every_column_takes_a_share(self):
        from callbacks.device_admin import DEVICE_ADMIN_COLUMNS

        assert set(self.widths()) == {c["id"] for c in DEVICE_ADMIN_COLUMNS}

    def test_the_shares_account_for_the_whole_table(self):
        """Short of 100% and dash_table hands the remainder back to one
        column, which is the void this replaced."""
        assert sum(float(w.rstrip("%")) for w in self.widths().values()) == 100

    def test_the_plant_name_still_gets_the_largest_share(self):
        """It carries the longest values in the fleet — "Itaipu Binacional
        Dam (Paraguay part)" — so it should be widest, just not unbounded."""
        assert max(self.widths(), key=lambda c: float(self.widths()[c].rstrip("%"))) == "plant"

class TestOneSeparationSystem:
    """`style_as_list_view=True` already draws a rule between rows. Striping
    on top of it is a second separation system doing the same job, and the
    denser the table the more it reads as noise.
    """

    def style_data(self):
        from components.entity_table import entity_table
        from dash import dash_table

        from tests.dash_tree import walk

        table = next(
            n for n in walk(entity_table("t", [{"name": "A", "id": "a"}], []))
            if isinstance(n, dash_table.DataTable)
        )
        return table.style_data_conditional

    def test_rows_are_separated_by_rules_not_stripes(self):
        assert not any(r["if"].get("row_index") == "odd" for r in self.style_data())

    def test_state_colouring_survives_the_removal(self):
        """Only the stripe goes; the freshness rules are the whole point of
        style_data_conditional."""
        from components.entity_table import entity_table
        from dash import dash_table

        from tests.dash_tree import walk

        table = next(
            n for n in walk(
                entity_table("t", [{"name": "A", "id": "a"}], [], state_column_id="a")
            )
            if isinstance(n, dash_table.DataTable)
        )
        assert any("_state" in str(r["if"]) for r in table.style_data_conditional)


class TestEmptyState:
    """dash_table renders ONLY the header table when a table has no rows —
    there is no empty `<tbody>` to hang a `::after` on. A CSS-only empty state
    was written against a hand-built DOM, passed its test, and rendered
    nothing in the application. The message is therefore a real element the
    callback fills.
    """

    def test_the_page_reserves_a_slot_for_it(self):
        from pages.device_admin import EMPTY_ID, layout
        from tests.dash_tree import find_by_id

        assert find_by_id(layout(), EMPTY_ID) is not None

    def test_the_slot_sits_directly_under_the_table(self):
        """It stands in for the rows, so it belongs where they would be —
        not below a summary or an unrelated panel."""
        from dash import dash_table

        from pages.device_admin import EMPTY_ID, layout
        from tests.dash_tree import walk

        nodes = list(walk(layout()))
        table_at = next(i for i, n in enumerate(nodes) if isinstance(n, dash_table.DataTable))
        empty_at = next(i for i, n in enumerate(nodes) if getattr(n, "id", None) == EMPTY_ID)
        assert empty_at > table_at

    def test_a_filter_that_matches_nothing_fills_it(self):
        from callbacks.device_admin import empty_state

        assert empty_state(0) is not None

    def test_rows_present_means_no_message(self):
        from callbacks.device_admin import empty_state

        assert empty_state(7) is None

    def test_it_reads_as_an_answer_not_a_failure(self, css):
        """The error panel already covers "we could not load this"; this one
        means "we looked, and there are none"."""
        from callbacks.device_admin import empty_state
        from tests.dash_tree import text_of

        assert "No results" in text_of(empty_state(0))
        assert "text-align: center" in rule(css, ".entity-table-empty")


class TestPagination:
    """120 devices at 30 a page is four pages, and the pager was styled
    nowhere — so dash_table's own rule still rendered the page number in
    monospace. The table font fix targeted the table element only.
    """

    def test_the_pager_is_not_left_in_the_dash_default_monospace(self, css):
        assert "font-family: inherit" in rule(
            css, ".entity-table-wrapper .previous-next-container"
        )

    def test_the_page_number_matches_the_application_face(self, css):
        assert "font-family: inherit" in rule(
            css, ".entity-table-wrapper .previous-next-container .page-number"
        )

    def test_the_pager_sits_below_right_of_the_table(self, css):
        body = rule(css, ".entity-table-wrapper .previous-next-container")
        assert "justify-content: flex-end" in body


class TestSortAffordance:
    def test_the_sort_arrow_is_visible_without_competing_with_the_label(self, css):
        """It was flush against the header text at full strength, reading as
        part of the word rather than as a control."""
        body = rule(css, ".entity-table-wrapper .column-header--sort")
        assert "opacity" in body
        assert "margin-left" in body

    def test_the_arrow_follows_the_label_and_stays_beside_it(self, css):
        """ASSIGN-TOOLBAR-1: dash_table renders the arrow first and grows the
        name to fill the cell, so a right-aligned header's arrow sat ~800px
        from its label."""
        inner = ".entity-table-wrapper .dash-table-container .dash-spreadsheet-container .dash-spreadsheet-inner"
        assert "display: inline-flex" in rule(css, inner + " .dash-header > div")
        name = rule(css, inner + " .column-header-name")
        assert "flex-grow: 0" in name
        assert "order: 1" in name
        assert "order: 2" in rule(css, inner + " .dash-header .column-actions")

    def test_the_action_columns_carry_no_sort_arrow(self, css):
        assert "display: none" in rule(
            css,
            '.entity-table-wrapper th.dash-header[data-dash-column="manage"] .column-header--sort',
        )
        assert '.entity-table-wrapper th.dash-header[data-dash-column="assign"] .column-header--sort' in css

    def test_the_arrow_strengthens_on_hover(self, css):
        assert "opacity: 1" in rule(
            css, ".entity-table-wrapper th:hover .column-header--sort"
        )
