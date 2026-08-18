"""Frozen UI contracts from the approved Device Monitoring vertical slice.

Approved 2026-08-09. The Device screen is the project's reference
implementation, not merely the first redesigned page, and these values are the
patterns Fleet / Plant / Transformer must reuse rather than reinterpret.

Every assertion here encodes a decision that was measured or argued for, and
several of them are things that failed silently once already. Changing one
should require a specific reason and a deliberate edit to the assertion — that
is the point of the file. It is not here to make the suite bigger.

Browser-measured values (390 px chart top, 80 px KPI card) cannot be asserted
without a running browser; the CSS inputs that produce them are locked instead,
and the rendered numbers live in docs/UX_ACCEPTANCE_DEVICE.md with screenshots
in docs/ux-baseline/.
"""
from __future__ import annotations

import pathlib
import re

import pytest

from components.metric_chart import CHART_CONFIG, CHART_HEIGHT, MODEBAR_REMOVED

CSS = pathlib.Path(__file__).resolve().parent.parent / "assets" / "app.css"
CSS_TEXT = CSS.read_text(encoding="utf-8")


class TestChartContract:
    def test_primary_chart_height_is_340(self):
        assert CHART_HEIGHT == 340

    def test_chart_fits_above_the_fold_at_the_budget(self):
        """390 px measured top + 340 px height must clear a 768 px viewport."""
        assert 390 + CHART_HEIGHT <= 768

    def test_toolbar_is_download_zoom_pan_reset(self):
        """Four buttons. Reset stays: zoom is supported, so recovery must be
        discoverable rather than relying on an undocumented double-click."""
        for kept in ("toImage", "zoom2d", "pan2d", "resetScale2d"):
            assert kept not in MODEBAR_REMOVED, f"{kept} must remain in the toolbar"
        for removed in ("select2d", "lasso2d", "zoomIn2d", "zoomOut2d", "autoScale2d"):
            assert removed in MODEBAR_REMOVED

    def test_plotly_branding_stays_off(self):
        assert CHART_CONFIG["displaylogo"] is False


class TestSnapshotStripContract:
    def test_auto_fill_grid_for_dynamic_metrics(self):
        """Auto-fill grid adapts to however many metrics the registry defines.
        Desktop: all tiles in one row. Tablet: wraps to 4. Mobile: wraps to 2."""
        assert re.search(
            r"\.metric-snapshot-strip\s*\{[^}]*grid-template-columns:\s*repeat\(auto-fill,",
            CSS_TEXT, re.S,
        ), "snapshot strip must use auto-fill for dynamic metric count"

    def test_steps_down_below_the_validated_width(self):
        """Auto-fill wraps based on available width."""
        assert re.search(r"@media \(max-width: 1199px\)\s*\{[^}]*repeat\(4,", CSS_TEXT, re.S)


class TestReservedHeights:
    """Loading and error states must not collapse the layout (§23)."""

    @pytest.mark.parametrize(
        "selector,min_height",
        [("#snapshot-strip", "89px"), ("#kpi-row-container", "80px")],
    )
    def test_container_reserves_height(self, selector, min_height):
        pattern = re.escape(selector) + r"\s*\{[^}]*min-height:\s*" + re.escape(min_height)
        assert re.search(pattern, CSS_TEXT, re.S), f"{selector} must reserve {min_height}"

    def test_chart_container_reserves_height(self):
        assert re.search(r"min-height:\s*340px", CSS_TEXT)


class TestFocusRingContract:
    """This one failed silently in production code and shipped. It is locked."""

    def test_focus_rule_is_not_wrapped_in_where(self):
        """`:where()` has zero specificity, so third-party `outline: none` wins
        and keyboard users get no focus indicator at all — while the element
        still matches :focus-visible, so it looks correct in the DOM."""
        assert ":where(" not in CSS_TEXT or ":where(a, button" not in CSS_TEXT

    def test_focus_visible_rule_exists(self):
        assert "a:focus-visible" in CSS_TEXT
        assert "button:focus-visible" in CSS_TEXT

    def test_focus_outline_defeats_third_party_resets(self):
        assert re.search(r"outline:\s*2px solid var\(--color-accent\)\s*!important", CSS_TEXT)


class TestTokenContract:
    @pytest.mark.parametrize(
        "token", ["--color-bg", "--color-surface", "--color-text", "--color-muted",
                  "--color-accent", "--focus-ring", "--state-fresh-bg", "--state-stale-bg",
                  "--state-none-bg", "--sp-2", "--fs-kpi", "--radius"],
    )
    def test_semantic_token_is_defined(self, token):
        assert f"{token}:" in CSS_TEXT, f"{token} is part of the frozen token set"

    def test_contrast_fixes_are_not_reverted(self):
        """#6b7280 was 4.8:1 and #92400e was 5.9:1 — both under AA at small
        sizes. They were raised to 6.4:1 and 8.1:1."""
        assert "--color-muted: #5b6472" in CSS_TEXT
        assert "--state-stale-text: #713f12" in CSS_TEXT


class TestTimestampContract:
    def test_readings_table_states_utc(self):
        from callbacks.device import TIMESTAMP_COLUMN_NAME

        assert "UTC" in TIMESTAMP_COLUMN_NAME

    def test_paired_freshness_carries_both_halves(self):
        from datetime import datetime, timedelta, timezone

        from components.freshness_badge import format_last_reading

        text = format_last_reading(
            datetime(2026, 8, 9, 5, 43, tzinfo=timezone.utc), timedelta(hours=2, minutes=17)
        )
        assert "ago" in text and "UTC" in text


class TestTableCellFocusRing:
    """dash_table stamps `tabindex="-1"` on every cell and every
    `.dash-cell-value` — 210 elements on the plants table — so all of them match
    the global `[tabindex]:focus-visible` rule written for form controls.

    On a 38 px input, `outline` plus `box-shadow` reads as one ring with a halo.
    On a compact table cell it reads as two concentric lines, and the positive
    outline-offset pushes the outer one outside the cell box, so a
    keyboard-focused cell showed a doubled vertical rule beside its text.

    The indicator must survive — keyboard cell navigation needs it exactly as
    much as a button does, which is what DEF-1 established. Only the doubling
    goes. Computed values verified in a browser: cells ring once at
    offset -2px, controls still ring twice.
    """

    def test_cells_draw_a_single_ring_inside_the_cell(self):
        match = re.search(
            r"td\.dash-cell:focus-visible,\s*\.dash-cell-value:focus-visible\s*\{([^}]*)\}",
            CSS_TEXT, re.S,
        )
        assert match, "the table-cell focus override is missing"
        block = match.group(1)
        assert "box-shadow: none" in block, "the halo must not double the outline"
        assert "outline-offset: -2px" in block, "the ring must not overlap the neighbour"

    def test_the_override_never_removes_the_outline(self):
        """Zeroing the outline here would silently undo DEF-1 for table users."""
        match = re.search(
            r"td\.dash-cell:focus-visible,\s*\.dash-cell-value:focus-visible\s*\{([^}]*)\}",
            CSS_TEXT, re.S,
        )
        block = match.group(1)
        assert not re.search(r"outline:\s*(none|0)", block)

    def test_form_controls_keep_the_halo(self):
        """The global rule keeps both layers; only cells opt out of the second."""
        match = re.search(
            r"\[tabindex\]:focus-visible,[^{]*\{([^}]*)\}", CSS_TEXT, re.S
        )
        assert match and "box-shadow: var(--focus-ring)" in match.group(1)
