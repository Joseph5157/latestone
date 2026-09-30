"""Technician Assignments callbacks (ADR-032).

Administrator only, and enforced three times: the route policy, this module's
own capability check on every callback (a callback is independently invokable),
and the assignment service, which refuses a non-Administrator actor itself.

``load`` reads the registered RTLs and their open assignments once per page
load (and after a change) into a store; ``render`` filters that snapshot with no
further reads. The client SQL Server is only read; nothing here writes to it.
"""
from __future__ import annotations

import logging

from dash import ALL, Input, Output, State, ctx, no_update

from components import rtl_assignments as ui
from components.status_panels import error_panel
from pages import rtl_assignments as page
from services import rtl_assignment_service as svc
from services.auth_service import current_identity
from services.authorization import MANAGE_RTL_ASSIGNMENTS, may_perform_capability

logger = logging.getLogger(__name__)

ROUTE = "rtl_assignments"


def _is_admin(user) -> bool:
    return user is not None and may_perform_capability(user.role, MANAGE_RTL_ASSIGNMENTS)


def load(context, _version, *, fetch=svc.get_assignment_overview, identity=current_identity):
    """(store payload, stats, error). Nothing is read for a non-Administrator."""
    if not context or context.get("route") != ROUTE:
        return no_update, no_update, no_update
    try:
        if not _is_admin(identity()):
            return None, None, error_panel("Only an Administrator can manage assignments.")
        overview = fetch()
    except Exception:
        logger.exception("Failed to load Technician Assignments")
        return None, None, error_panel()
    if not overview.available:
        return None, None, ui.unavailable_panel()
    return svc.to_payload(overview.rows), ui.stats(overview.rows), None


def render(payload, view, technician_id, uid_text):
    """(list, technician filter options) over the stored snapshot."""
    rows = svc.from_payload(payload)
    shown = svc.filter_rows(rows, view=view or "all", technician_user_id=technician_id,
                            uid_text=uid_text)
    return ui.assignment_table(shown), ui.technician_filter_options(rows)


def select(triggered, clicks_value):
    """The store value for a clicked row action, or no_update for a spurious trigger.

    Pattern-matched buttons fire once when they are (re)created, with a click
    count of 0; only a real click selects.
    """
    if not isinstance(triggered, dict) or not clicks_value:
        return no_update
    return {"uid": triggered["uid"], "mode": triggered["mode"]}


def open_panel(selected, payload, *, technicians=svc.list_technician_options,
               history=svc.get_assignment_history, identity=current_identity):
    """(style, title, note, target options, target value, history, message)."""
    hidden = (page.HIDDEN_STYLE, None, None, [], None, None, None)
    if not selected or not _is_admin(identity()):
        return hidden
    uid, mode = selected["uid"], selected["mode"]
    row = next((r for r in svc.from_payload(payload) if r.device_uid == uid), None)
    history_children = ui.history_table(history(uid))
    if mode == "history":
        return (page.VISIBLE_STYLE, f"History for RTL {uid}", None, [], None,
                history_children, None)
    options = [{"label": name, "value": tid} for tid, name in technicians()]
    if mode == "reassign" and row is not None and row.is_assigned:
        options = [o for o in options if o["value"] != row.technician_user_id]
        return (page.VISIBLE_STYLE, f"Reassign RTL {uid}",
                f"Currently assigned to {row.technician_name}. The current assignment is kept "
                "in the history.", options, None, history_children, None)
    return (page.VISIBLE_STYLE, f"Assign RTL {uid}",
            "This RTL is unassigned. Choose the Technician who will hold it.",
            options, None, history_children, None)


def confirm(selected, payload, target, version, *, identity=current_identity,
            assign=svc.assign, reassign=svc.reassign):
    """(message, new version). The service decides; this only reports."""
    if not selected or selected.get("mode") not in ("assign", "reassign"):
        return no_update, no_update
    if target is None:
        return "Choose a Technician first.", no_update
    actor = identity()
    uid = selected["uid"]
    try:
        if selected["mode"] == "assign":
            assign(uid, int(target), actor=actor)
            done = f"RTL {uid} assigned."
        else:
            row = next((r for r in svc.from_payload(payload) if r.device_uid == uid), None)
            if row is None or row.assignment_id is None:
                return "This RTL is no longer assigned. Refresh the page.", no_update
            reassign(uid, int(target), expected_assignment_id=row.assignment_id, actor=actor)
            done = f"RTL {uid} reassigned."
    except svc.AssignmentError as exc:
        return exc.message, (version or 0) + 1  # reload so the list shows current truth
    except Exception:
        logger.exception("Assignment change failed")
        return "The assignment could not be saved.", no_update
    return done, (version or 0) + 1


def register(app) -> None:
    @app.callback(
        Output(page.STORE_ID, "data"),
        Output(page.STATS_ID, "children"),
        Output(page.ERROR_ID, "children"),
        Input("page-context", "data"),
        Input(page.VERSION_ID, "data"),
    )
    def load_rtl_assignments(context, version):
        return load(context, version)

    @app.callback(
        Output(page.LIST_ID, "children"),
        Output(page.TECH_FILTER_ID, "options"),
        Input(page.STORE_ID, "data"),
        Input(page.VIEW_ID, "value"),
        Input(page.TECH_FILTER_ID, "value"),
        Input(page.UID_SEARCH_ID, "value"),
    )
    def render_rtl_assignments(payload, view, technician_id, uid_text):
        return render(payload, view, technician_id, uid_text)

    @app.callback(
        Output(page.SELECTED_ID, "data"),
        Input({"type": page.PICK_TYPE, "uid": ALL, "mode": ALL}, "n_clicks"),
        prevent_initial_call=True,
    )
    def pick_rtl_assignment(clicks):
        triggered = ctx.triggered_id
        value = ctx.triggered[0]["value"] if ctx.triggered else None
        return select(triggered, value)

    @app.callback(
        Output(page.PANEL_ID, "style"),
        Output(page.PANEL_TITLE_ID, "children"),
        Output(page.PANEL_NOTE_ID, "children"),
        Output(page.TARGET_ID, "options"),
        Output(page.TARGET_ID, "value"),
        Output(page.HISTORY_ID, "children"),
        Output(page.MESSAGE_ID, "children"),
        Input(page.SELECTED_ID, "data"),
        Input(page.CANCEL_ID, "n_clicks"),
        State(page.STORE_ID, "data"),
    )
    def open_rtl_assignment_panel(selected, cancel_clicks, payload):
        if ctx.triggered_id == page.CANCEL_ID:
            return open_panel(None, payload)
        return open_panel(selected, payload)

    @app.callback(
        Output(page.MESSAGE_ID, "children", allow_duplicate=True),
        Output(page.VERSION_ID, "data"),
        Input(page.CONFIRM_ID, "n_clicks"),
        State(page.SELECTED_ID, "data"),
        State(page.STORE_ID, "data"),
        State(page.TARGET_ID, "value"),
        State(page.VERSION_ID, "data"),
        prevent_initial_call=True,
    )
    def confirm_rtl_assignment(n_clicks, selected, payload, target, version):
        if not n_clicks:
            return no_update, no_update
        return confirm(selected, payload, target, version)
