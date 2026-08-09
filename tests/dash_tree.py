"""Helpers for asserting on Dash component trees without a browser.

Layout functions are pure, so the rendered tree can be walked directly. These
helpers exist because several defects were about the *shape* of the tree — a
badge nested inside another badge, a component present in no layout — which
value-level assertions cannot see.
"""
from __future__ import annotations

from dash.development.base_component import Component


def walk(node):
    """Yield every Component in the tree, depth-first."""
    if isinstance(node, (list, tuple)):
        for item in node:
            yield from walk(item)
        return
    if not isinstance(node, Component):
        return
    yield node
    yield from walk(getattr(node, "children", None))


def find_by_class(node, class_fragment: str) -> list:
    """Every component whose className contains `class_fragment`."""
    return [
        n for n in walk(node)
        if isinstance(getattr(n, "className", None), str)
        and class_fragment in n.className
    ]


def find_by_exact_class(node, class_name: str) -> list:
    """Components carrying `class_name` as a whole class token.

    `find_by_class` matches substrings, so "kpi-card" also hits
    "kpi-card__label" and "kpi-card__secondary". Use this when you mean the
    element itself and not its BEM children.
    """
    return [
        n for n in walk(node)
        if isinstance(getattr(n, "className", None), str)
        and class_name in n.className.split()
    ]


def find_by_id(node, component_id: str):
    """The single component with this id, or None."""
    for n in walk(node):
        if getattr(n, "id", None) == component_id:
            return n
    return None


def text_of(node) -> str:
    """Flatten all string children in the tree into one string."""
    parts = []

    def collect(n):
        if isinstance(n, str):
            parts.append(n)
            return
        if isinstance(n, (list, tuple)):
            for item in n:
                collect(item)
            return
        if isinstance(n, Component):
            collect(getattr(n, "children", None))

    collect(node)
    return " ".join(parts)


def links(node) -> list[tuple[str, str]]:
    """Every (label, href) pair rendered as a dcc.Link/html.A in the tree."""
    found = []
    for n in walk(node):
        href = getattr(n, "href", None)
        if href is not None:
            found.append((text_of(n).strip(), href))
    return found
