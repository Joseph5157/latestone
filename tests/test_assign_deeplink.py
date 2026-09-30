"""The Fleet Overview -> Device Management assignment handoff (ADMIN-3).

The Unassigned RTLs panel does not own an assignment workflow. It links to the
one that already exists, naming a device in the URL, and Device Management
opens its existing drawer on that device. These tests cover the two halves of
that contract: the link format (`routes`) and the resolution step
(`callbacks.device_assign`), including the guarantee that a device_id arriving
from the browser is matched against rows already on the page rather than
trusted.
"""
from __future__ import annotations

from callbacks import device_assign
from callbacks.device_assign import (
    assign_drawer_open_state,
    find_device_row,
)
from routes import device_assign_href, parse_assign_request, parse_pathname

DEVICE_ID = "plant-01-t1-d1"


def table_row(device_id: str = DEVICE_ID, actions: str = "[View](#) [Assign](#) [Manage](#)"):
    return {
        "id": device_id,
        "device": "29017",
        "plant": "Plant 1",
        "transformer": "t1",
        "status": "Active",
        "actions": actions,
    }


def _no_technicians(monkeypatch):
    monkeypatch.setattr(device_assign, "get_technician_options", lambda: [])
    monkeypatch.setattr(
        device_assign.prototype_assignments,
        "get_assigned_technician",
        lambda device_id: None,
    )


def _one_technician(monkeypatch, current=None):
    monkeypatch.setattr(
        device_assign,
        "get_technician_options",
        lambda: [{"label": "demo.tech01", "value": "demo.tech01"}],
    )
    monkeypatch.setattr(
        device_assign.prototype_assignments,
        "get_assigned_technician",
        lambda device_id: current,
    )


class TestAssignHref:
    def test_points_at_the_existing_device_management_route(self):
        assert device_assign_href(DEVICE_ID).startswith("/admin/devices?")

    def test_names_the_device(self):
        assert device_assign_href(DEVICE_ID) == f"/admin/devices?assign={DEVICE_ID}"

    def test_the_handoff_destination_is_now_retired(self):
        """LEGACY-SYNTHETIC-UX-CLEANUP-01: the synthetic Device Management
        destination (`/admin/devices`) is retired, so this deep link now lands
        on the legacy/not-found panel. The `device_assign` callback code and its
        link format are kept isolated until the POSTGRESQL-RETIREMENT gate, so
        the rest of this file still exercises the handoff logic; only the route
        it points at changed."""
        assert parse_pathname("/admin/devices").name == "legacy_retired"

    def test_no_new_assignments_route_is_introduced(self):
        assert "/admin/assignments" not in device_assign_href(DEVICE_ID)

    def test_identifier_is_percent_encoded(self):
        """A device_id is validated downstream, but it must not be able to
        smuggle extra query parameters into the link on the way there."""
        href = device_assign_href("weird id&period=30d")
        assert "&period=30d" not in href
        assert "%26period" in href


class TestParseAssignRequest:
    def test_round_trips_the_device_id(self):
        href = device_assign_href(DEVICE_ID)
        assert parse_assign_request(href.split("?", 1)[1]) == DEVICE_ID

    def test_accepts_a_leading_question_mark(self):
        assert parse_assign_request(f"?assign={DEVICE_ID}") == DEVICE_ID

    def test_none_without_a_query_string(self):
        assert parse_assign_request(None) is None
        assert parse_assign_request("") is None

    def test_none_for_an_unrelated_query_string(self):
        assert parse_assign_request("?metric=voltage&period=7d") is None

    def test_none_for_a_blank_value(self):
        assert parse_assign_request("?assign=") is None

    def test_ignores_the_other_parameters(self):
        assert parse_assign_request(f"?period=7d&assign={DEVICE_ID}") == DEVICE_ID

    def test_decodes_a_percent_encoded_identifier(self):
        href = device_assign_href("plant 01")
        assert parse_assign_request(href.split("?", 1)[1]) == "plant 01"


class TestFindDeviceRow:
    def test_finds_the_row_for_the_requested_device(self):
        rows = [table_row("other"), table_row(DEVICE_ID)]
        assert find_device_row(rows, DEVICE_ID)["id"] == DEVICE_ID

    def test_unknown_device_resolves_to_nothing(self):
        """Strict validation of a browser-supplied identifier: the only device
        that can open the drawer is one already rendered on this page."""
        assert find_device_row([table_row("other")], DEVICE_ID) is None

    def test_missing_device_id_resolves_to_nothing(self):
        assert find_device_row([table_row()], None) is None

    def test_empty_table_resolves_to_nothing(self):
        assert find_device_row(None, DEVICE_ID) is None
        assert find_device_row([], DEVICE_ID) is None


class TestAssignDrawerOpenState:
    """The shared helper both the click path and the deep link go through."""

    def test_nothing_to_open_without_a_row(self, monkeypatch):
        _no_technicians(monkeypatch)
        assert assign_drawer_open_state(None) is None

    def test_a_device_not_in_the_table_opens_nothing(self, monkeypatch):
        """Replaces the old markdown check (FIX-1C).

        This used to assert that a row whose actions text lacked "Assign"
        opened nothing. That check never fired — every row carried the same
        literal markdown — and which action was clicked is now answered by
        `column_id` upstream. The guarantee that actually protected this
        path survives and is asserted instead: an `?assign=` value naming
        something not on the page resolves to no row, so a hand-edited URL
        cannot address a device the table is not showing.
        """
        _no_technicians(monkeypatch)
        assert find_device_row([table_row()], "not-on-this-page") is None
        assert assign_drawer_open_state(None) is None

    def test_opens_the_drawer(self, monkeypatch):
        _one_technician(monkeypatch)
        state = assign_drawer_open_state(table_row())
        assert state[0] == {"display": "block"}

    def test_carries_the_device_context_the_drawer_needs(self, monkeypatch):
        _one_technician(monkeypatch)
        state = assign_drawer_open_state(table_row())
        assert state[1] == DEVICE_ID
        assert state[2] == "29017"
        assert state[3] == "t1"
        assert state[4] == "Plant 1"

    def test_offers_the_existing_technician_options(self, monkeypatch):
        _one_technician(monkeypatch)
        state = assign_drawer_open_state(table_row())
        assert state[5] == [{"label": "demo.tech01", "value": "demo.tech01"}]

    def test_preselects_the_current_technician(self, monkeypatch):
        _one_technician(monkeypatch, current="demo.tech01")
        assert assign_drawer_open_state(table_row())[6] == "demo.tech01"

    def test_shows_the_honest_empty_state_without_technicians(self, monkeypatch):
        _no_technicians(monkeypatch)
        state = assign_drawer_open_state(table_row())
        assert "No technicians available" in state[7]
        assert state[8]["display"] == "block"

    def test_returns_one_value_per_drawer_output(self, monkeypatch):
        _one_technician(monkeypatch)
        assert len(assign_drawer_open_state(table_row())) == 9


class TestEndToEndHandoff:
    """A row rendered on the Fleet Overview reaches the drawer intact."""

    def test_the_panel_link_opens_the_drawer_on_that_device(self, monkeypatch):
        _one_technician(monkeypatch)
        href = device_assign_href(DEVICE_ID)
        requested = parse_assign_request(href.split("?", 1)[1])
        row = find_device_row([table_row("other"), table_row(DEVICE_ID)], requested)
        state = assign_drawer_open_state(row)
        assert state[0] == {"display": "block"}
        assert state[1] == DEVICE_ID

    def test_a_device_not_on_the_page_opens_nothing(self, monkeypatch):
        _one_technician(monkeypatch)
        requested = parse_assign_request("?assign=not-a-device")
        assert assign_drawer_open_state(find_device_row([table_row()], requested)) is None
