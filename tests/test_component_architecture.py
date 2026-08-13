"""Guards the layering rule: Pages compose, Components render, Callbacks
coordinate, Services decide, Repositories fetch.

`components/` must stay presentation-only — no database access, direct or
via the repository layer. `pages/` must not reach past callbacks/services
into the repository layer either. Written as an AST import scan rather than
a text search so a module doc-comment mentioning "repositories" cannot
trip a false positive, and rewritten import styles (`import repositories.x`,
`from repositories import x`) are all still caught.
"""
from __future__ import annotations

import ast
import pathlib

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
FORBIDDEN_ROOTS = {"repositories", "db"}


def _imported_top_level_modules(path: pathlib.Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            # `from . import x` / `from .x import y` (level > 0) is an
            # intra-package relative import, never a route to another
            # top-level package, so only absolute imports are checked.
            if node.module and node.level == 0:
                modules.add(node.module.split(".")[0])
    return modules


def _violations(directory: str, forbidden: set[str]) -> dict[str, set[str]]:
    found = {}
    for path in sorted((REPO_ROOT / directory).glob("*.py")):
        hit = _imported_top_level_modules(path) & forbidden
        if hit:
            found[path.name] = hit
    return found


def test_components_do_not_import_repositories_or_db():
    violations = _violations("components", FORBIDDEN_ROOTS)
    assert not violations, (
        f"components/ must stay presentation-only, but found: {violations}. "
        "Route data access through a service or callback instead."
    )


def test_pages_do_not_import_repositories():
    violations = _violations("pages", {"repositories"})
    assert not violations, (
        f"pages/ must compose components only, but found: {violations}. "
        "Fetch data in a callback and pass it in, not from a page module."
    )
