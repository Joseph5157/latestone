"""Layer 1 width contracts; computed geometry is verified in Chromium.

Keep these guards local to the shell: Fleet components, page width tokens,
login markup, and selector callbacks must not need layout-specific changes.
"""
from pathlib import Path
import re

import pytest

import app as app_module
from callbacks import navigation as nav
from components.app_shell import (
    CONTENT_ID, UTILITY_ID, UTILITY_BODY_ID, UTILITY_STORE_ID, UTILITY_TOGGLE_ID,
    app_shell,
)
from dash import html
from components.equipment_selector import DEVICE_ID, PLANT_ID, SHELL_ID, TRANSFORMER_ID
from tests.dash_tree import find_by_id


@pytest.fixture(scope="module")
def css():
    text = (Path(__file__).resolve().parents[1] / "assets" / "app.css").read_text(
        encoding="utf-8"
    )
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


def rule(css, selector):
    match = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", css)
    assert match, f"Missing shell rule: {selector}"
    return match.group(1)


def test_login_collapses_utility_allocation_not_only_its_child(css):
    assert "display: none" in rule(
        css, ".app-shell:has(.login-page) .app-shell__utility"
    )


def test_utility_reserves_card_and_only_one_outer_gutter(css):
    utility = rule(css, ".app-shell__utility")
    assert "flex: 0 0 auto" in utility
    assert "width: calc(200px + var(--sp-4))" in utility
    assert "padding: var(--sp-2) var(--sp-4) var(--sp-5) 0" in utility


def test_content_takes_remaining_space_and_can_shrink(css):
    content = rule(css, ".app-shell__content")
    assert "flex: 1 1 auto" in content
    assert "min-width: 0" in content
    for selector in (".app-root", ".app-shell", ".app-shell__content"):
        assert not re.search(r"(?<![-\w])(?:max-)?width\s*:", rule(css, selector))


def test_monitoring_pages_fill_the_shell_rather_than_centring_in_it(css):
    """Reverses the ENT-6 rule that freed Fleet Overview alone.

    The reasoning recorded there — "a workspace, not a capped reading
    column", whose 1550px cap "produced large auto margins between both
    shell rails" — is true of every table page, not just Fleet. Nine pages
    carry `page--monitoring`; one override per page is the wrong shape, so
    workspace width becomes the default inside the shell and the pages that
    genuinely read as prose opt back in below.
    """
    workspace = rule(css, ".app-shell__content .page--monitoring")
    assert "max-width: none" in workspace
    assert "padding" not in workspace


def test_a_registration_form_still_reads_at_a_column_width(css):
    """Device registration is four inputs. A form stretched across 2,000px
    puts its labels a screen away from its fields."""
    assert "max-width: var(--w-reading)" in rule(
        css, ".app-shell__content .page--device-register"
    )


def base_rule(css, selector):
    """A rule whose selector starts a line, so `.page--monitoring` finds the
    base rule and not the `.app-shell__content .page--monitoring` override
    that now precedes it in the file."""
    match = re.search(r"^" + re.escape(selector) + r"\s*\{([^}]*)\}", css, re.M)
    assert match, f"Missing base rule: {selector}"
    return match.group(1)


def test_base_caps_survive_for_anything_outside_the_shell(css):
    assert "max-width: var(--w-monitoring)" in base_rule(css, ".page--monitoring")
    assert "max-width: var(--w-reading)" in base_rule(css, ".page")


def test_utility_remains_content_height_and_transparent(css):
    assert "align-items: flex-start" in rule(css, ".app-shell")
    utility = rule(css, ".app-shell__utility")
    assert not re.search(r"(?:height|background|align-self)\s*:", utility)
    assert "position: sticky" in utility and "top: 0" in utility
    navigator = rule(css, ".asset-navigator")
    assert "flex-direction: column" in navigator
    assert not re.search(r"(?<![-\w])(?:min-)?height\s*:", navigator)


def test_selector_callback_targets_remain_global_siblings_of_page_content():
    layout = app_module.app.layout
    utility = find_by_id(layout, UTILITY_ID)
    content = find_by_id(layout, CONTENT_ID)
    assert utility is not None and content is not None
    assert find_by_id(content, "page-content") is not None
    for component_id in (SHELL_ID, PLANT_ID, TRANSFORMER_ID, DEVICE_ID):
        assert find_by_id(utility, component_id) is not None
        assert find_by_id(content, component_id) is None


def test_utility_toggle_is_accessible_and_expanded_by_default():
    layout = app_module.app.layout
    toggle = find_by_id(layout, UTILITY_TOGGLE_ID)
    assert toggle.type == "button"
    assert getattr(toggle, "aria-expanded") == "true"
    assert getattr(toggle, "aria-label") == "Collapse Asset Navigator"
    assert getattr(toggle, "aria-controls") == UTILITY_BODY_ID
    assert toggle.title == "Collapse Asset Navigator"
    assert find_by_id(layout, UTILITY_BODY_ID).hidden is False


def test_utility_preference_is_global_and_session_scoped():
    store = find_by_id(app_module.app.layout, UTILITY_STORE_ID)
    assert store.data == {"collapsed": False}
    assert store.storage_type == "session"
    assert UTILITY_STORE_ID != nav.COLLAPSE_STORE_ID


@pytest.mark.parametrize("state", [None, {}, {"collapsed": False}, {"collapsed": True}])
def test_utility_state_drives_width_visibility_and_accessible_name_together(state):
    # A monitoring route, so this stays a test of the collapse state alone;
    # route policy is covered in tests/test_utility_route_visibility.py.
    class_name, hidden, expanded, label, title = nav.utility_presentation(state, "/plants")
    collapsed = bool(state and state.get("collapsed"))
    assert ("app-shell__utility--collapsed" in class_name.split()) == collapsed
    assert hidden is collapsed
    assert expanded == ("false" if collapsed else "true")
    assert label == ("Expand Asset Navigator" if collapsed else "Collapse Asset Navigator")
    assert title == label


def test_collapsed_rail_is_48px_and_does_not_hide_the_toggle(css):
    assert "width: 48px" in rule(css, ".app-shell__utility--collapsed")
    body = find_by_id(app_module.app.layout, UTILITY_BODY_ID)
    assert find_by_id(body, UTILITY_TOGGLE_ID) is None
    for component_id in (SHELL_ID, PLANT_ID, TRANSFORMER_ID, DEVICE_ID):
        assert find_by_id(body, component_id) is not None


def test_utility_callbacks_do_not_reset_values_or_rerender_content():
    callbacks = app_module.app._callback_list
    toggle = next(c for c in callbacks if c["output"] == f"{UTILITY_STORE_ID}.data")
    assert toggle["inputs"] == [{"id": UTILITY_TOGGLE_ID, "property": "n_clicks"}]
    assert toggle["state"] == [{"id": UTILITY_STORE_ID, "property": "data"}]
    assert toggle["prevent_initial_call"] is True
    presentation = next(c for c in callbacks if f"{UTILITY_BODY_ID}.hidden" in c["output"])
    # Collapse state, the route, and the session — and nothing else. The
    # guarantee being pinned is that this callback never reads or writes the
    # selector values and never re-renders page content, not that its input
    # count is frozen. `auth-store` joined in ASSET-NAV-ROUTE-1 because `/`
    # renders a different page per role (ADR-024), so the route alone cannot
    # say whether this column belongs on screen.
    assert presentation["inputs"] == [
        {"id": UTILITY_STORE_ID, "property": "data"},
        {"id": "url", "property": "pathname"},
        {"id": "auth-store", "property": "data"},
    ]
    assert presentation["state"] == []
    # The thing the exact list above is really defending.
    read_ids = {i["id"] for i in presentation["inputs"]}
    assert read_ids.isdisjoint({SHELL_ID, PLANT_ID, TRANSFORMER_ID, DEVICE_ID, "page-content"})
    outputs = set(presentation["output"].strip(".").split("..."))
    assert outputs == {
        f"{UTILITY_ID}.className", f"{UTILITY_BODY_ID}.hidden",
        f"{UTILITY_TOGGLE_ID}.aria-expanded", f"{UTILITY_TOGGLE_ID}.aria-label",
        f"{UTILITY_TOGGLE_ID}.title",
    }


def test_optional_utility_still_renders_nothing_when_omitted():
    shell = app_shell(html.Div(), html.Div())
    for component_id in (UTILITY_ID, UTILITY_STORE_ID, UTILITY_TOGGLE_ID, UTILITY_BODY_ID):
        assert find_by_id(shell, component_id) is None
