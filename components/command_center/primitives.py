"""Command Center-local presentation primitives (CC12_PRIMITIVES.md).

`.command-center__` is this family's own CSS namespace, kept separate from
the shared `components/card.py` surface deliberately: Phase 11 gives Command
Center its own dark/light theming, and an isolated namespace means that work
never touches the CSS Fleet Overview's cards depend on
(command center/07_IMPLEMENTATION_PLAN.md gate principle - Fleet Overview is
frozen). Reuses shared design *tokens* (CC12_PRIMITIVES.md's shared-token
rule) via the same CSS custom properties every other surface already uses,
not shared component markup.

Primitives receive already-decided values only (CC12_PRIMITIVES.md's
semantic rule) - no battery thresholds, event classification, or
current-state inference lives here.
"""
from __future__ import annotations

from dash import html


#: CC-HEADER-TRIM-1 removed `scope_indicator_text`. Its count was
#: `snapshot.total_rtls`, which the Working severity card already renders as
#: its denominator ("0 of 120") for every role — `services/
#: attention_service.py` scopes that field, so a Technician saw their own
#: number twice as well. ADR-004 still governs any future indicator: it may
#: only ever be a read-only statement of `scope_for()`, never a selector.


def cc_card(title: str, children: list, *, subtitle: str | None = None) -> html.Section:
    header_children = [html.H2(title, className="command-center__card-title")]
    if subtitle:
        header_children.append(html.P(subtitle, className="command-center__card-subtitle"))
    return html.Section(
        className="command-center__card",
        children=[
            html.Header(className="command-center__card-header", children=header_children),
            html.Div(className="command-center__card-body", children=children),
        ],
    )


def panel_not_yet_built(title: str) -> html.Section:
    """An honest placeholder for a panel this gate does not build.

    Mirrors pages/placeholder.py's existing pattern (a title, a plain
    pending statement) for the same reason: a route/panel not built yet
    should say so, not render empty or invent content. Deliberately never
    says "no data" or "unavailable" - those are specific, evaluated states
    (ADR-001/ADR-002); this is "not built in this phase yet", a different
    fact that must not be confused with either.
    """
    return cc_card(
        title,
        [
            html.Div(
                className="status-panel status-panel--placeholder",
                children=[html.P("Not yet available in this build.")],
            ),
        ],
    )
