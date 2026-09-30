"""Tests for the cross-plant equipment selector and callback<->layout wiring.

Two things are covered here, and the second matters more than the first.

The feature tests exercise the cascade and the navigation guard. The *wiring*
tests assert that every id a callback references actually exists in some
layout. That is the guard the codebase was missing: `hierarchy_selector()` had
four callbacks driving three dropdowns that no layout ever rendered, so every
navigation raised a nonexistent-Output `ReferenceError` in the browser while
the Python suite stayed green (docs/CODE_AUDIT.md finding 2).
"""
from __future__ import annotations

import pytest
from dash import no_update
from dash.development.base_component import Component

import app as app_module
from callbacks import equipment_selector as sel
from components.assign_device_drawer import assign_device_drawer
from components.user_form_drawer import user_form_drawer
from components.device_manage_drawer import device_manage_drawer
from components.device_operations import device_operations_panel
from components.freshness_threshold_panel import freshness_threshold_panel
from components.temperature_threshold_panel import temperature_threshold_panel
from components.vibration_contract_panel import vibration_contract_panel
from pages import admin_settings, audit_log, device_dashboard, device_admin, device_register, technician_devices, admin_assignments, login, plant_detail, plants_overview, transformer_detail, user_admin, report_center, notifications, command_center, rtl_detail, rtl_network, rtl_dashboard, historical_events, rtl_assignments
from services.device_scope import UNRESTRICTED
from tests.auth_test_support import trusted_session


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def collect_ids(node) -> set[str]:
    """Recursively collect every component `id` in a Dash layout tree."""
    found: set[str] = set()

    def walk(n):
        if isinstance(n, (list, tuple)):
            for item in n:
                walk(item)
            return
        if not isinstance(n, Component):
            return
        node_id = getattr(n, "id", None)
        if isinstance(node_id, str):
            found.add(node_id)
        walk(getattr(n, "children", None))

    walk(node)
    return found


def parse_output_ids(output_spec: str) -> set[str]:
    """Pull component ids out of a Dash callback `output` string.

    Single output is "my-id.prop"; multi-output is "..a.prop...b.prop..".
    """
    spec = output_spec.strip(".")
    return {chunk.rsplit(".", 1)[0] for chunk in spec.split("...") if chunk}


def callback_reference_ids(dash_app) -> set[str]:
    """Every component id referenced by any registered callback."""
    referenced: set[str] = set()
    for entry in dash_app._callback_list:
        referenced |= parse_output_ids(entry["output"])
        for dep in list(entry["inputs"]) + list(entry["state"]):
            if isinstance(dep.get("id"), str):
                referenced.add(dep["id"])
    return referenced


GLOBAL_LAYOUT_IDS = collect_ids(app_module.app.layout)

PAGE_LAYOUT_IDS = (
    collect_ids(login.login_layout())
    | collect_ids(plants_overview.layout())
    | collect_ids(plant_detail.layout("Plant"))
    | collect_ids(transformer_detail.layout("Plant", "T1", "p1"))
    | collect_ids(device_dashboard.layout("Plant", "T1", "D1"))
    | collect_ids(device_admin.layout())
    | collect_ids(technician_devices.layout())
    | collect_ids(admin_assignments.layout())
    | collect_ids(device_register.layout())
    | collect_ids(assign_device_drawer())
    | collect_ids(device_manage_drawer())
    # ROLE-4B: rendered into the device page's operations slot by a callback,
    # so it is mountable even though no static layout contains it.
    | collect_ids(device_operations_panel("plant-01-t1-d1"))
    # THRESH-CONFIG-1: same reasoning — rendered into the Fleet Overview's
    # temperature-threshold-panel slot by callbacks/temperature_threshold.py.
    | collect_ids(temperature_threshold_panel(None))
    # FRESHNESS-CONFIG-1: rendered into the freshness-threshold-panel slot
    # by callbacks/freshness_threshold.py.
    | collect_ids(freshness_threshold_panel(None, default_minutes=1440))
    # VIB-CONFIG-1: same reasoning — rendered into the Fleet Overview's
    # vibration-contract-panel slot by callbacks/vibration_contract.py.
    | collect_ids(vibration_contract_panel({}))
    | collect_ids(user_admin.layout())
    | collect_ids(audit_log.layout())
    | collect_ids(admin_settings.layout())
    | collect_ids(user_form_drawer())
    | collect_ids(report_center.layout())
    | collect_ids(notifications.layout())
    | collect_ids(command_center.layout())
    # RTL-UID-DETAIL-01: the canonical client RTL detail page, reached at
    # /rtls/<uid>. Its layout takes the UID, so a representative one is
    # supplied here exactly as the device/plant pages above do.
    | collect_ids(rtl_detail.layout(29006))
    # LATEST-NETWORK-CONTEXT-01: the current Network view, at /rtls/network.
    | collect_ids(rtl_network.layout())
    # FACTUAL-DASHBOARD-01: the factual dashboard, served at /command-center.
    | collect_ids(rtl_dashboard.layout())
    # HISTORICAL-EVENTS-01: Historical Events, at /events.
    | collect_ids(historical_events.layout())
    | collect_ids(rtl_assignments.layout())
)

MOUNTABLE_IDS = GLOBAL_LAYOUT_IDS | PAGE_LAYOUT_IDS


# --------------------------------------------------------------------------
# Wiring integrity — the guard the previous rounds lacked
# --------------------------------------------------------------------------

class TestCallbackLayoutWiring:
    def test_every_callback_id_exists_in_some_layout(self):
        """No callback may reference a component no layout ever renders."""
        # Wildcard pattern-matching ids (`ALL`/`MATCH`, CC-ACTIONS-1's per-row
        # buttons) are rendered per data row at runtime, and Dash accepts an
        # ALL pattern that matches zero components, so they cannot raise the
        # ReferenceError this guards. Their rendering is pinned instead by
        # tests/test_attention_components.py::TestProblemActions.
        orphans = {
            ref for ref in callback_reference_ids(app_module.app) - MOUNTABLE_IDS
            if '["ALL"]' not in ref and '["MATCH"]' not in ref
        }
        assert not orphans, (
            "Callbacks reference ids that exist in no layout: "
            f"{sorted(orphans)}. Every navigation would raise a Dash "
            "ReferenceError for these."
        )

    def test_selector_ids_live_in_the_global_layout(self):
        """The selector's callbacks fire on every route, so it must be global.

        If these ids only existed inside a page layout, the callbacks would
        throw on every route that does not render that page.
        """
        for component_id in (
            sel.SHELL_ID,
            sel.PLANT_ID,
            sel.TRANSFORMER_ID,
            sel.DEVICE_ID,
        ):
            assert component_id in GLOBAL_LAYOUT_IDS

    def test_selector_is_present_on_the_login_route_too(self):
        """Mounted-but-hidden, not unmounted — that is what keeps callbacks safe."""
        assert sel.SHELL_ID in GLOBAL_LAYOUT_IDS
        assert sel.SHELL_ID not in collect_ids(login.login_layout())


# --------------------------------------------------------------------------
# Visibility
# --------------------------------------------------------------------------

class TestSelectorVisibility:
    def test_hidden_when_auth_store_is_empty(self):
        assert sel.selector_visibility(None) == {"display": "none"}
        assert sel.selector_visibility({}) == {"display": "none"}

    def test_hidden_when_not_authenticated(self):
        assert sel.selector_visibility({"authenticated": False}) == {"display": "none"}

    def test_shown_when_authenticated(self):
        assert sel.selector_visibility({"authenticated": True}) != {"display": "none"}

    def test_default_shell_style_is_hidden(self):
        """First paint is the login page, so the shell must start hidden."""
        from components.equipment_selector import equipment_selector_shell

        assert equipment_selector_shell().style == {"display": "none"}


# --------------------------------------------------------------------------
# Plant options are gated on authentication
# --------------------------------------------------------------------------

class TestPlantOptionsAuthGate:
    def test_no_query_runs_before_authentication(self, monkeypatch):
        """An unauthenticated visitor must not trigger a hierarchy query."""
        def explode(*_args, **_kwargs):
            raise AssertionError("hierarchy_service was queried before login")

        monkeypatch.setattr(sel.hierarchy_service, "list_plants", explode)
        assert sel.plant_options({"authenticated": False}) == []
        assert sel.plant_options(None) == []

    def test_plants_are_listed_once_authenticated(self, monkeypatch):
        """AUTH-HARDEN-1: scope now comes from the trusted server session, so
        this test signs in as a real (fake-backed) Administrator rather than
        relying on the `auth_data` dict's `authenticated` flag for anything
        beyond the pre-login gate."""
        monkeypatch.setattr(
            sel.hierarchy_service,
            "list_plants",
            lambda *, scope: [_plant("p1", "Alpha"), _plant("p2", "Beta")],
        )
        with trusted_session(monkeypatch, user_id=1, role="administrator"):
            assert sel.plant_options({"authenticated": True}) == [
                {"label": "Alpha", "value": "p1"},
                {"label": "Beta", "value": "p2"},
            ]


# --------------------------------------------------------------------------
# Cascade
# --------------------------------------------------------------------------

class TestCascade:
    def test_transformers_disabled_until_a_plant_is_chosen(self):
        options, disabled, value = sel.transformer_options(None, UNRESTRICTED)
        assert (options, disabled, value) == ([], True, None)

    def test_transformers_listed_for_a_plant(self, monkeypatch):
        monkeypatch.setattr(
            sel.hierarchy_service,
            "list_transformers",
            lambda plant_id, *, scope: [_transformer("p1-t1", "T1")],
        )
        options, disabled, value = sel.transformer_options("p1", UNRESTRICTED)
        assert options == [{"label": "T1", "value": "p1-t1"}]
        assert disabled is False
        assert value is None, "changing plant must clear the stale transformer"

    def test_devices_disabled_until_a_transformer_is_chosen(self):
        options, disabled, value = sel.device_options(None, UNRESTRICTED)
        assert (options, disabled, value) == ([], True, None)

    def test_devices_listed_for_a_transformer(self, monkeypatch):
        monkeypatch.setattr(
            sel.hierarchy_service,
            "list_devices",
            lambda transformer_id, *, scope: [_device("p1-t1-d1", "D1")],
        )
        options, disabled, value = sel.device_options("p1-t1", UNRESTRICTED)
        assert options == [{"label": "D1", "value": "p1-t1-d1"}]
        assert disabled is False
        assert value is None, "changing transformer must clear the stale device"

    def test_clearing_the_plant_collapses_the_whole_cascade(self, monkeypatch):
        """plant -> None must not leave a selectable device behind."""
        _, _, transformer_value = sel.transformer_options(None, UNRESTRICTED)
        _, device_disabled, device_value = sel.device_options(transformer_value, UNRESTRICTED)
        assert device_disabled is True
        assert device_value is None


# --------------------------------------------------------------------------
# Navigation, including the feedback-loop guard
# --------------------------------------------------------------------------

class TestDeviceNavigation:
    def test_no_navigation_without_a_device(self):
        assert sel.device_navigation_target(None, {}) is no_update

    def test_navigates_to_the_selected_device(self):
        assert sel.device_navigation_target("p1-t1-d1", {}) == "/devices/p1-t1-d1"

    def test_jumps_across_plants(self):
        """Phase 16 Step 3: reach a device under a different plant directly."""
        context = {"route": "device", "device_id": "p1-t1-d1"}
        assert sel.device_navigation_target("p9-t2-d4", context) == "/devices/p9-t2-d4"

    def test_does_not_renavigate_to_the_current_device(self):
        """Guards the cascade against a navigate -> re-render -> navigate loop."""
        context = {"route": "device", "device_id": "p1-t1-d1"}
        assert sel.device_navigation_target("p1-t1-d1", context) is no_update


# --------------------------------------------------------------------------
# Minimal record stand-ins (avoids importing repository dataclasses)
# --------------------------------------------------------------------------

class _Rec:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def _plant(plant_id, name):
    return _Rec(plant_id=plant_id, name=name)


def _transformer(transformer_id, code):
    return _Rec(transformer_id=transformer_id, transformer_code=code)


def _device(device_id, code):
    return _Rec(device_id=device_id, device_code=code)


class TestSelectorFieldSizing:
    """The selector bar's dropdowns must actually be sized by the stylesheet.

    dcc.Dropdown applies `className` to the inner `.Select` div, while the flex
    child is the outer `.dash-dropdown` wrapper. Sizing written against the
    field class therefore lands on an element whose parent is not a flex
    container and silently does nothing: the three dropdowns collapsed to their
    120 px min-width with ~790 px of the bar unused, and "Transformer..." was
    clipped while the two shorter placeholders were not.

    Source assertions only — they cannot prove the cascade was won. Computed
    widths were verified in a browser per spec section 6.9.
    """

    import pathlib as _pathlib
    import re as _re

    CSS_TEXT = (
        _pathlib.Path(__file__).resolve().parent.parent / "assets" / "app.css"
    ).read_text(encoding="utf-8")

    def test_flex_sizing_targets_the_wrapper_dash_dropdown(self):
        assert self._re.search(
            r"\.hierarchy-selector\s+\.dash-dropdown\s*\{[^}]*flex:",
            self.CSS_TEXT, self._re.S,
        ), "the flex child is .dash-dropdown, not .hierarchy-selector__field"

    def test_max_width_is_not_set_on_the_inner_field_class(self):
        """Putting it back on the field class would look like sizing and do nothing."""
        match = self._re.search(
            r"\.hierarchy-selector__field\s*\{([^}]*)\}", self.CSS_TEXT, self._re.S
        )
        assert match and "max-width" not in match.group(1)

    def test_min_width_clears_the_longest_placeholder(self):
        """"Transformer..." needed 126 px and had 118."""
        match = self._re.search(
            r"\.hierarchy-selector\s+\.dash-dropdown\s*\{([^}]*)\}",
            self.CSS_TEXT, self._re.S,
        )
        min_width = int(self._re.search(r"min-width:\s*(\d+)px", match.group(1)).group(1))
        assert min_width >= 140


class TestDropdownSearchInputPadding:
    """react-select's search input ships `padding: 8px 0 12px` on a content-box
    element: 37 px inside a 36 px control, growing to 54 px once text is typed,
    with the caret below the text centre because top and bottom differ.

    `!important` is required here rather than lazy. react-select injects
    `.Select-input > input` at runtime twice, and the second copy lands after
    app.css in sheet order, so an identical selector can win neither on
    specificity nor on order. Verified by walking document.styleSheets.

    Source guards only. The proof is the computed measurement: 34 px input,
    inside a 36 px control, text centred at 18 px — the same centre as the
    placeholder and the selected value.
    """

    import pathlib as _pathlib
    import re as _re

    CSS_TEXT = (
        _pathlib.Path(__file__).resolve().parent.parent / "assets" / "app.css"
    ).read_text(encoding="utf-8")

    def _block(self):
        match = self._re.search(
            r"\.Select-input\s*>\s*input\s*\{([^}]*)\}", self.CSS_TEXT, self._re.S
        )
        assert match, "the dropdown search input override is missing"
        return match.group(1)

    def test_padding_is_zeroed(self):
        assert self._re.search(r"padding:\s*0\s*!important", self._block())

    def test_height_is_restored_with_the_padding(self):
        """Zeroing padding alone collapses the input to 17 px and puts the text
        6 px above centre — measured. The height must go with it."""
        block = self._block()
        assert "height: 34px" in block and "line-height: 34px" in block

    def test_override_is_marked_important(self):
        """Without it the vendor rule injected after app.css wins every time."""
        for prop in ("padding", "height", "line-height"):
            assert self._re.search(rf"{prop}:[^;]*!important", self._block()), prop

    def test_login_inputs_are_not_zeroed(self):
        """The login fields use a symmetric 10px 12px on a border-box element and
        are correct; a blanket input reset would put their text on the border."""
        assert not self._re.search(
            r"(^|\})\s*input\s*\{[^}]*padding:\s*0", self.CSS_TEXT, self._re.S
        )


class TestDropdownValuePresentation:
    """Two artefacts inside the dropdown control, both from styles reaching
    react-select internals that were never meant to be styled.

    Reported as stray vertical lines before the selected value and as the
    clear/arrow buttons colliding with the value text. Both reproduced and
    measured in a browser before fixing; see the comments in app.css.
    """

    import pathlib as _pathlib
    import re as _re

    CSS_TEXT = (
        _pathlib.Path(__file__).resolve().parent.parent / "assets" / "app.css"
    ).read_text(encoding="utf-8")

    def test_hidden_search_input_draws_no_focus_ring(self):
        """A 5 px input parked at the value's text origin, ringed at
        offset 2px, reads as two vertical bars before the value."""
        match = self._re.search(
            r"\.Select-input\s*>\s*input:focus-visible\s*\{([^}]*)\}",
            self.CSS_TEXT, self._re.S,
        )
        assert match, "the stray-line suppression is missing"
        block = match.group(1)
        assert self._re.search(r"outline:\s*none\s*!important", block)
        assert self._re.search(r"box-shadow:\s*none\s*!important", block)

    def test_the_visible_control_keeps_its_focus_ring(self):
        """Suppressing the inner ring is only safe because the control itself
        lights up. If this selector ever leaves the focus rule, the dropdown
        becomes unfocusable to the eye."""
        match = self._re.search(
            r"([^{]*):focus-within\s*\{[^}]*outline:[^;]*var\(--color-accent\)",
            self.CSS_TEXT, self._re.S,
        )
        assert match and ".Select-control" in match.group(0)

    def test_value_label_is_clipped_before_the_buttons(self):
        """The parent reserves 42px and sets ellipsis, but the label span
        overflows it; the constraint must be on the label."""
        match = self._re.search(
            r"\.Select-value-label\s*\{([^}]*)\}", self.CSS_TEXT, self._re.S
        )
        assert match, "the value-label clipping rule is missing"
        block = match.group(1)
        for prop in ("overflow: hidden", "text-overflow: ellipsis",
                     "white-space: nowrap", "display: block"):
            assert prop in block, prop


class TestMenuGeometry:
    """ASSET-NAV-DEFECTS-1 — D1 and D2.

    dcc.Dropdown's two size defaults are not multiples of each other:
    `maxHeight` 200 against `optionHeight` 35 is 5.71 rows, so the browser
    slices the sixth option through its glyphs. And nothing stops an option
    wrapping inside its fixed-height row, so a long plant name
    (`MONTALTO (Alessandro Volta)`) takes three lines in a 35px slot and
    paints its third line over the option below it.

    The defect in D2 is the *relationship* between the two numbers, so both
    have to be pinned together — asserting either one alone passes while the
    bug is still there.
    """

    import pathlib as _pathlib
    import re as _re

    #: Comments stripped: they quote the selectors under test by name.
    CSS_TEXT = _re.sub(r"/\*.*?\*/", "", (
        _pathlib.Path(__file__).resolve().parent.parent / "assets" / "app.css"
    ).read_text(encoding="utf-8"), flags=_re.S)

    def _dropdowns(self):
        from components.equipment_selector import equipment_selector
        found = []

        def walk(node):
            if isinstance(node, Component):
                if getattr(node, "id", None) in (sel.PLANT_ID, sel.TRANSFORMER_ID, sel.DEVICE_ID):
                    found.append(node)
                for child in (getattr(node, "children", None) or []) if isinstance(
                    getattr(node, "children", None), (list, tuple)
                ) else [getattr(node, "children", None)]:
                    walk(child)

        walk(equipment_selector())
        return found

    def test_all_three_fields_declare_both_sizes(self):
        fields = self._dropdowns()
        assert len(fields) == 3
        for field in fields:
            assert getattr(field, "optionHeight", None), field.id
            assert getattr(field, "maxHeight", None), field.id

    def test_the_menu_holds_a_whole_number_of_options(self):
        """No sliced last row: every field's menu height divides by its row
        height exactly. This is what the vendor defaults (200 / 35) fail."""
        for field in self._dropdowns():
            assert field.maxHeight % field.optionHeight == 0, (
                f"{field.id}: maxHeight {field.maxHeight} is "
                f"{field.maxHeight / field.optionHeight:.2f} rows"
            )

    def test_the_menu_is_deep_enough_to_be_worth_opening(self):
        """30 plants behind a 5-row window is a scroll tube, not a list."""
        for field in self._dropdowns():
            assert field.maxHeight // field.optionHeight >= 8, field.id

    def test_an_option_can_never_wrap_onto_the_row_below(self):
        """The rows are fixed-height and absolutely positioned, so a wrap is
        not a taller row — it is text painted over the next option."""
        blocks = [
            body for selectors, body in self._re.findall(
                r"([^{}]+)\{([^}]*)\}", self.CSS_TEXT
            )
            if ".hierarchy-selector .VirtualizedSelectOption" in selectors
        ]
        assert blocks, "no rule constrains the navigator's menu options"
        declared = " ".join(blocks)
        for prop in ("white-space: nowrap", "overflow: hidden",
                     "text-overflow: ellipsis"):
            assert prop in declared, prop


class TestPanelReadability:
    """ASSET-NAV-DEFECTS-1 — D3, D4 and D5."""

    import pathlib as _pathlib
    import re as _re

    #: Comments stripped: they quote the selectors under test by name.
    CSS_TEXT = _re.sub(r"/\*.*?\*/", "", (
        _pathlib.Path(__file__).resolve().parent.parent / "assets" / "app.css"
    ).read_text(encoding="utf-8"), flags=_re.S)

    def _block(self, selector):
        """Every declaration in every rule whose selector list names this
        selector. A grouped rule is still a rule, and the stylesheet groups
        these freely, so matching only `selector {` would fail on where the
        property actually lives rather than on whether it is set."""
        declared = " ".join(
            body for selectors, body in self._re.findall(
                r"([^{}]+)\{([^}]*)\}", self.CSS_TEXT
            )
            if selector in selectors
        )
        assert declared.strip(), f"missing rule: {selector}"
        return declared

    def test_the_dock_does_not_clip_an_open_menu(self):
        """D3. `overflow` on this box makes it a clipping container for the
        absolutely-positioned `.Select-menu-outer` inside it, and since the
        box shrink-wraps the 247px card, opening a menu grows a second
        scrollbar beside the menu's own."""
        block = self._block(".app-shell__utility-inner")
        assert "overflow-y: auto" not in block
        assert "max-height" not in block

    def test_the_control_is_sized_for_its_panel(self):
        """D4. The control inherits the 16px body size into a card whose own
        title is 12px and whose field labels are 11px — three steps of
        mismatch, and 62px of `Niederaussem power station` lost to it."""
        block = self._block(".hierarchy-selector .Select-control")
        size = int(self._re.search(r"font-size:\s*(\d+)px", block).group(1))
        assert 13 <= size <= 14

    def test_the_value_cannot_paint_over_the_clear_and_arrow_buttons(self):
        """The `.Select-value-label` comment claims the vendor reserves 42px
        on `.Select-value`. The served stylesheet computes 10px, so the
        label's box always ran under both buttons — invisible only while the
        card was narrow enough for the ellipsis to fall short of them.

        The rule must also out-specify the vendor's own
        `.Select--single > .Select-control .Select-value` (0,3,0), which a
        plain `.hierarchy-selector .Select-value` (0,2,0) loses to wherever
        it sits in the sheet. That loss is invisible to a source assertion —
        the first version of this test passed against a browser that still
        rendered the overlap — so the ancestry is pinned, not just the
        value.
        """
        block = self._block(
            ".hierarchy-selector .Select--single > .Select-control .Select-value"
        )
        reserve = int(self._re.search(r"padding-right:\s*(\d+)px", block).group(1))
        assert reserve >= 42

    def test_the_card_is_wide_enough_for_a_real_plant_name(self):
        """D4. 200px gave `.Select-value-label` a 144px box for a 206px
        string."""
        utility = self._block(".app-shell__utility")
        width = int(self._re.search(r"width:\s*calc\((\d+)px", utility).group(1))
        assert width >= 260

    def test_the_card_is_visible_against_its_column_in_dark_mode(self):
        """D5. Both painted `var(--color-surface)` — the same token, the same
        computed `rgb(30, 40, 53)` — so the card read as nothing at all."""
        column = self._re.search(
            r"\.app-root\.theme--dark[^{]*\.app-shell__utility\s*\{([^}]*)\}",
            self.CSS_TEXT, self._re.S,
        )
        card = self._re.search(
            r"\.app-root\.theme--dark[^{]*\.asset-navigator\s*\{([^}]*)\}",
            self.CSS_TEXT, self._re.S,
        )
        assert card, "dark mode gives the card no ground of its own"
        column_bg = self._re.search(r"background:\s*([^;]+);", column.group(1)).group(1)
        card_bg = self._re.search(r"background:\s*([^;]+);", card.group(1)).group(1)
        assert column_bg.strip() != card_bg.strip()
