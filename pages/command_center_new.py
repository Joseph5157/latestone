"""The redesigned Command Center (CC-NEW-1) — layout only, no queries.

Filled in by callbacks/command_center_new.py.
"""
from __future__ import annotations

from dash import html


def layout() -> html.Div:
    return html.Div(className="page page--monitoring", children=[html.H1("Command Center")])
