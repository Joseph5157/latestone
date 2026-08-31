"""Assign and Manage must be separately addressable (FIX-1C).

Both drawer callbacks listen to the SAME DataTable `active_cell` and both
accept it on the SAME condition, `column_id == "actions"`. A DataTable's
`active_cell` names a cell — `{"row": n, "column": n, "column_id": ..., "row_id": ...}` —
and carries nothing about which markdown link inside that cell was clicked.
So one click on the actions cell is delivered, identically, to both
callbacks.

Each callback tries to disambiguate by reading the cell's markdown text
(`"Assign" not in row["actions"]`, `"Manage" not in actions_text`). That
cannot work: every row's actions string is the same literal
`"[View](#) [Assign](#) [Manage](#)"`, so both checks pass on every row and
neither callback ever declines. `test_the_markdown_text_check_cannot_
disambiguate` pins that, because the code reads as though it were a real
guard.

These tests are written against the TARGET contract — one addressable column
per action — so they fail on the current markup and pass once the actions
cell is split. Device identity keeps coming from `active_cell["row_id"]`,
which is already correct and is not what is being changed.
"""
from __future__ import annotations

import pytest
from dash import no_update

from callbacks import device_admin, device_assign, device_manage

ROWS = [
    {
        "id": "d1",
        "device": "aa01",
        "plant": "Plant One",
        "transformer": "T1",
        "status": "Active",
        "actions": "[View](#) [Assign](#) [Manage](#)",
    },
    {
        "id": "d2",
        "device": "aa02",
        "plant": "Plant Two",
        "transformer": "T2",
        "status": "Active",
        "actions": "[View](#) [Assign](#) [Manage](#)",
    },
]


class _CapturingApp:
    def __init__(self):
        self.functions = {}

    def callback(self, *args, **kwargs):
        def decorator(fn):
            self.functions[fn.__name__] = fn
            return fn

        return decorator


def _handlers(module):
    app = _CapturingApp()
    module.register(app)
    return app.functions


@pytest.fixture(autouse=True)
def _no_database(monkeypatch):
    """The drawers read technician options and current assignment."""
    monkeypatch.setattr(device_assign, "get_technician_options", lambda: [])
    monkeypatch.setattr(
        device_assign.prototype_assignments, "get_assigned_technician",
        lambda device_id: None,
    )


def _cell(column_id, row_id="d1"):
    return {"row": 0, "column": 0, "column_id": column_id, "row_id": row_id}


def _opened(result) -> bool:
    """A drawer opened iff its style output is a real display:block."""
    style = result[0]
    return style is not no_update and style == {"display": "block"}


def _assign(cell):
    return _handlers(device_assign)["open_assign_drawer"](cell, ROWS)


def _manage(cell):
    return _handlers(device_manage)["open_manage_drawer"](cell, ROWS)


# --------------------------------------------------------------------------
# The mechanism
# --------------------------------------------------------------------------


def test_the_markdown_text_check_cannot_disambiguate():
    """Both callbacks 'check' the cell text; every row has the same text."""
    assert {row["actions"] for row in ROWS} == {"[View](#) [Assign](#) [Manage](#)"}
    for row in ROWS:
        assert "Assign" in row["actions"] and "Manage" in row["actions"], (
            "the text check each callback performs passes on every row, so "
            "neither ever declines a click meant for the other"
        )


# --------------------------------------------------------------------------
# The contract
# --------------------------------------------------------------------------


def test_assign_column_opens_only_the_assignment_drawer():
    cell = _cell("assign")

    assert _opened(_assign(cell)), "Assign must open the assignment drawer"
    assert not _opened(_manage(cell)), "Assign must not open the manage drawer"


def test_manage_column_opens_only_the_management_drawer():
    cell = _cell("manage")

    assert _opened(_manage(cell)), "Manage must open the management drawer"
    assert not _opened(_assign(cell)), "Manage must not open the assignment drawer"


@pytest.mark.parametrize(
    "column_id", ["actions", "assign", "manage", "device", "status"]
)
def test_no_single_click_ever_opens_both_drawers(column_id):
    """The invariant the shared cell violates.

    `"actions"` is in this list deliberately. It is the colliding column, and
    without it every case passes vacuously — the other ids are rejected by
    both callbacks today, so the parametrize would look green while proving
    nothing. After the split no column is named "actions" at all, and both
    callbacks decline it.
    """
    cell = _cell(column_id)

    assert not (_opened(_assign(cell)) and _opened(_manage(cell))), (
        f"clicking {column_id!r} opened both drawers; one click is one action"
    )


def test_assign_carries_the_clicked_rows_device_id():
    result = _assign(_cell("assign", row_id="d2"))

    assert result[1] == "d2", "the drawer must open on the row that was clicked"


def test_manage_carries_the_clicked_rows_device_id():
    result = _manage(_cell("manage", row_id="d2"))

    assert result[1] == "d2"


# --------------------------------------------------------------------------
# Regressions the split must not cause
# --------------------------------------------------------------------------


def test_a_non_action_column_opens_nothing():
    """Device-name navigation is a separate callback; clicking the name must
    not open a drawer as a side effect."""
    cell = _cell("device")

    assert not _opened(_assign(cell))
    assert not _opened(_manage(cell))


def test_device_name_navigation_is_unchanged():
    navigate = _handlers(device_admin)["navigate_from_device_admin_table"]

    assert navigate(_cell("device", row_id="d1")) not in (None, no_update)
    assert navigate(_cell("assign", row_id="d1")) is no_update, (
        "the new action columns must not navigate"
    )


def test_deep_link_still_opens_the_assignment_drawer():
    """ADMIN-3's `?assign=<device_id>` handoff from the Fleet Overview shares
    `assign_drawer_open_state` with the click path and must be unaffected."""
    from_url = _handlers(device_assign)["open_assign_drawer_from_url"]

    result = from_url(ROWS, "?assign=d2")

    assert _opened(result), "the deep link must still open the drawer"
    assert result[1] == "d2"


def test_manage_early_return_matches_its_declared_output_count():
    """`open_manage_drawer` declares 12 Outputs and every early return builds
    an 11-tuple, so Dash raises on output-count mismatch the moment a click
    is declined — which is exactly what the split makes reachable."""
    result = _manage(_cell("status"))

    assert len(result) == 12, (
        f"declined clicks returned {len(result)} values for 12 outputs"
    )
