"""CLIENT-TERMINOLOGY-NAV-01 — the client-facing words on real-RTL surfaces.

The application's visible language must describe the client's RTL environment,
not the legacy synthetic `plant_monitoring` model. The client hierarchy is
Operating Unit -> Zone -> Sector -> CNC -> Feeder -> Transformer -> RTL;
"Plant" is not a level in it (docs/database/CLIENT_RTL_SQLSERVER_KNOWLEDGE_BASE.md
section 3).

These tests guard *wording that reaches a client*, on the routes that already
show real client data. They deliberately do NOT assert on internal identifiers
(`plant_id`, route paths, PostgreSQL column names, the `overview` nav key) —
renaming those is a later gate's work and ADR-029 keeps the source read-only
either way.

Three separate failures are covered:

1. The real Fleet page presenting itself with synthetic-hierarchy wording.
2. Navigation advertising that page under a name that is not what it shows.
3. Registration being restated as activity ("339 active RTLs"), which the
   knowledge base names explicitly as the wrong wording.
"""
from __future__ import annotations

import pytest

from components import rtl_fleet
from components.app_sidebar import SIDEBAR_SECTIONS, sidebar_nav
from components.status_panels import forbidden_panel, not_found_panel
from pages import plants_overview
from routes import FLEET_OVERVIEW_PATH, NAV_KEY_BY_ROUTE
from services.authorization import ADMINISTRATOR, GENERAL, TECHNICIAN, visible_nav_keys
from tests.dash_tree import find_by_class, links, text_of

#: The page title the realignment plan approved for the real Fleet
#: (docs/plans/CLIENT_APP_REALIGNMENT_PLAN_01.md section 4, "NOW").
REGISTERED_RTLS = "Registered RTLs"

#: Wording that describes the synthetic model. None of it may appear on a
#: surface that renders client RTL facts. "Plant" is matched case-sensitively
#: and as a whole word by the helper below so `plant_monitoring` in a class
#: name or an id cannot trip it.
SYNTHETIC_HIERARCHY_WORDS = ("Plant", "Plants", "Plant Overview", "Asset Navigator")

#: State the client RTL source cannot presently support (ADR-029: the
#: offline threshold is UNRESOLVED and no threshold is implemented).
UNSUPPORTED_STATE_WORDS = ("Online", "Offline", "Healthy", "Unhealthy")


def _words(text: str) -> set[str]:
    """Whole words in `text`, so `plant_monitoring` is not a "Plant" hit."""
    import re

    return set(re.findall(r"[A-Za-z]+", text))


def _fleet_page_text() -> str:
    return text_of(plants_overview.layout())


# ---------------------------------------------------------------------------
# The real Fleet page
# ---------------------------------------------------------------------------


class TestRealFleetPageWording:
    """`/plants` renders the client's registered RTL directory."""

    def test_the_page_calls_itself_registered_rtls(self):
        assert REGISTERED_RTLS in _fleet_page_text()

    def test_it_no_longer_presents_itself_as_a_fleet_overview(self):
        """"Fleet Overview" is the synthetic page's name. The route still
        answers at /plants, but the operator must not be told they are
        looking at a plant fleet."""
        assert "Fleet Overview" not in _fleet_page_text()

    @pytest.mark.parametrize("word", SYNTHETIC_HIERARCHY_WORDS)
    def test_no_synthetic_hierarchy_label_appears(self, word):
        assert word not in _words(_fleet_page_text()), (
            f"{word!r} is legacy synthetic vocabulary, not client RTL vocabulary"
        )

    def test_the_breadcrumb_names_the_page_it_is_on(self):
        """A breadcrumb reading "Fleet" over a Registered RTLs heading is two
        names for one page; the trail is the first thing an operator reads.

        Asserted on the breadcrumb element itself, not on the page's flattened
        text — the subtitle and the scope note both contain the phrase, so a
        whole-page substring check would pass with the crumb still wrong.
        """
        from dash import html

        crumbs = find_by_class(plants_overview.layout(), "header__breadcrumb")
        assert len(crumbs) == 1
        assert text_of(crumbs[0]).strip() == REGISTERED_RTLS

    def test_the_heading_is_the_page_name(self):
        from dash import html

        from tests.dash_tree import walk

        headings = [n for n in walk(plants_overview.layout()) if isinstance(n, html.H1)]
        assert [text_of(h) for h in headings] == [REGISTERED_RTLS]


class TestRegistrationIsNotActivity:
    """339 is a registration count. Saying otherwise is the specific error the
    knowledge base calls out (section 4, "Avoid: 339 active RTLs")."""

    def test_the_scope_note_says_it_is_not_an_activity_count(self):
        note = rtl_fleet.SCOPE_NOTE
        assert "not a count of active or online RTLs" in note

    def test_the_scope_note_survives_onto_the_page(self):
        assert rtl_fleet.SCOPE_NOTE in _fleet_page_text()

    def test_the_registered_card_is_labelled_registered(self):
        assert "Registered RTLs" in rtl_fleet.FILTER_LABELS[rtl_fleet.FILTER_ALL] or (
            rtl_fleet.FILTER_LABELS[rtl_fleet.FILTER_ALL] == "All registered"
        )


class TestNoUnsupportedOperationalState:
    """No Online/Offline rule exists (ADR-029 decision 3: the hours are
    UNRESOLVED and no threshold is implemented). The page must not invent one."""

    @pytest.mark.parametrize("word", UNSUPPORTED_STATE_WORDS)
    def test_the_fleet_page_claims_no_communication_state(self, word):
        assert word not in _words(_fleet_page_text())

    @pytest.mark.parametrize("word", UNSUPPORTED_STATE_WORDS)
    def test_the_fleet_row_vocabulary_claims_no_communication_state(self, word):
        vocabulary = " ".join(
            [
                rtl_fleet.NO_TEMPERATURE,
                rtl_fleet.NO_MAPPING,
                rtl_fleet.NO_HIERARCHY,
                rtl_fleet.AMBIGUOUS,
                rtl_fleet.SCOPE_NOTE,
                *rtl_fleet.FILTER_LABELS.values(),
            ]
        )
        assert word not in _words(vocabulary)


# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------


def _all_sidebar_items():
    return [item for _title, items in SIDEBAR_SECTIONS for item in items]


class TestNavigationWording:
    def test_the_real_fleet_item_is_named_registered_rtls(self):
        labels = {href: label for _key, label, href, _icon in _all_sidebar_items()}
        assert labels[FLEET_OVERVIEW_PATH] == REGISTERED_RTLS

    def test_navigation_no_longer_says_overview(self):
        """"Overview" named the synthetic fleet page. It says nothing about
        what the route now shows."""
        labels = [label for _key, label, _href, _icon in _all_sidebar_items()]
        assert "Overview" not in labels

    @pytest.mark.parametrize("role", [ADMINISTRATOR, TECHNICIAN, GENERAL])
    def test_every_role_that_sees_the_item_sees_the_client_wording(self, role):
        rendered = dict(links(sidebar_nav(None, role)))
        if FLEET_OVERVIEW_PATH in rendered.values():
            # ADR-032: a Technician's list is named for what it holds.
            assert ("Assigned RTLs" if role == TECHNICIAN else REGISTERED_RTLS) in rendered

    @pytest.mark.parametrize("word", ("Plant", "Plants"))
    def test_no_navigation_item_is_named_for_the_synthetic_hierarchy(self, word):
        labels = [label for _key, label, _href, _icon in _all_sidebar_items()]
        assert word not in labels

    def test_every_navigation_item_still_has_a_destination(self):
        """Target-architecture names (Network, Historical Events, Technicians)
        are NOT added here: this gate must not advertise a page that does not
        exist yet."""
        for key, label, href, icon in _all_sidebar_items():
            assert key and label and href and icon
            assert href.startswith("/")


class TestWayBackLinksNameTheirDestination:
    """Both shared panels offer the same way back, to the same route. Neither
    may call it by the synthetic page's name."""

    def test_not_found_panel_points_at_registered_rtls(self):
        assert (f"Back to {REGISTERED_RTLS}", FLEET_OVERVIEW_PATH) in links(
            not_found_panel("device")
        )

    def test_forbidden_panel_points_at_registered_rtls(self):
        assert (f"Back to {REGISTERED_RTLS}", FLEET_OVERVIEW_PATH) in links(
            forbidden_panel()
        )

    @pytest.mark.parametrize("word", ("plants", "Plants", "Plant"))
    def test_neither_panel_names_the_synthetic_hierarchy(self, word):
        for panel in (not_found_panel("device"), forbidden_panel()):
            assert word not in _words(text_of(panel))


# ---------------------------------------------------------------------------
# What this gate must NOT have changed
# ---------------------------------------------------------------------------


class TestIdentityAndAuthorizationAreUnchanged:
    """Terminology only. These assertions fail if the rename leaked into
    routing identity or the role policy."""

    def test_the_route_path_is_the_canonical_list(self):
        """Was `/plants` when this gate closed. RTL-LIST-ROUTE-01 moved the
        directory to its canonical address; the route NAME and nav key below
        are what this gate pinned as identity, and they still hold."""
        assert FLEET_OVERVIEW_PATH == "/rtls"

    def test_the_route_name_and_nav_key_are_unchanged(self):
        """Internal identifiers stay `overview` — renaming them is a later
        gate (the canonical `/rtls` route), and changing them here would
        silently rewrite the authorization join."""
        assert NAV_KEY_BY_ROUTE["overview"] == "overview"
        keys = {key for key, _label, _href, _icon in _all_sidebar_items()}
        assert "overview" in keys

    @pytest.mark.parametrize(
        "role,expected",
        [
            # LATEST-NETWORK-CONTEXT-01 adds "network" for General only (Technician unchanged).
            (GENERAL, {"overview", "network", "events", "reports"}),
            (
                TECHNICIAN,
                {
                    "overview",
                    "notifications",
                    "reports",
                    "command_center",
                    "network",
                    "events",
                },
            ),
        ],
    )
    def test_visible_navigation_keys_are_unchanged(self, role, expected):
        assert visible_nav_keys(role) == expected

    def test_administrator_navigation_is_unchanged(self):
        keys = {key for key, _label, _href, _icon in _all_sidebar_items()}
        assert visible_nav_keys(ADMINISTRATOR) == keys

    def test_the_restricted_panel_still_refuses_unapproved_scopes(self):
        """Wording changed nowhere near this. The panel must still say the
        directory is not available, not show it."""
        text = text_of(rtl_fleet.restricted_panel())
        assert "not available for your account" in text
        assert "assigned to them" in text
