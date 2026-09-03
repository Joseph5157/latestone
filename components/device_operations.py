"""Device page operational surface — the entry point to the manage drawer.

ROLE-4B. The three actions a technician holds on an assigned RTL were only ever
rendered by `device_manage_drawer()` on `/admin/devices`, a route reserved for
administrators, so the permission had no reachable path. This section is the
missing entry point; the drawer itself is reused unchanged.

**Markup only — no policy.** Whether this section appears at all is decided by
`callbacks.device_manage.device_operations_children` asking
`action_guard.may_action`. A component that compared roles would be a second
permission table beside `ACTION_POLICY`, and no test of that table would catch
it drifting.

One button rather than three: the drawer already owns the choice between the
actions, and reproducing its menu here would be a second copy of that workflow
to keep in step.

`assign_device_drawer()` is deliberately not reachable from here. Assignment is
what grants technician authority, so it stays with fleet administration.
"""
from __future__ import annotations

from dash import html

#: The device page's entry point into the manage drawer.
OPEN_OPERATIONS_BTN = "device-operations-open-btn"

#: Filled by `callbacks.device_manage.render_device_operations`; empty for a
#: persona with no authorized action on the routed RTL.
OPERATIONS_ID = "device-operations"


def device_operations_panel(device_id: str) -> html.Section:
    """The operational section for `device_id`.

    Built in the same card shape as the page's other sections so it reads as
    part of this device's page rather than a panel bolted onto it.
    """
    return html.Section(
        className="device-section device-operations",
        children=[
            html.Div(
                className="device-section__heading device-section__heading--inline",
                children=[
                    html.Div(
                        children=[
                            html.Div(
                                "Operations",
                                className="device-section__eyebrow",
                            ),
                            html.H2("Operational controls"),
                        ]
                    ),
                    html.P(
                        "Program this RTL, set message forwarding for your "
                        "account, or remove it from the active monitoring list."
                    ),
                ],
            ),
            html.Div(
                className="device-operations__bar",
                children=[
                    # Named here, not only inside the drawer: the operator
                    # decides to open the surface from this line, so this is
                    # where "which RTL am I about to act on" belongs.
                    html.Div(
                        className="device-operations__target",
                        children=[
                            html.Span(
                                "Selected RTL",
                                className="device-operations__target-label",
                            ),
                            html.Span(
                                device_id,
                                className="device-operations__target-value",
                            ),
                        ],
                    ),
                    html.Button(
                        "Manage RTL",
                        id=OPEN_OPERATIONS_BTN,
                        className="device-operations__open",
                        n_clicks=0,
                    ),
                ],
            ),
            # Deactivate is destructive and lives one click inside the drawer,
            # so the warning belongs where the drawer is opened — not only
            # beside the button that finally performs it.
            html.P(
                "Deactivating an RTL removes it from active monitoring.",
                className="device-operations__danger-note",
            ),
        ],
    )
