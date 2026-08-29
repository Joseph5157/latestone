"""Guard: fail if internal engineering material is present in `client-release`.

`client-release` is an orphan branch curated by hand (docs/CLIENT_DELIVERY.md),
so exclusion relies on a human not copying a file. This turns the manual
`git ls-tree` sanity check that doc already recommends into something runnable.

Run before every push to the client remote:

    python scripts/check_client_release.py [branch]

Exit status 0 = clean, 1 = internal material found, 2 = could not check.
"""
from __future__ import annotations

import subprocess
import sys

DEFAULT_BRANCH = "client-release"

#: Exact paths that must never appear in the delivered tree.
FORBIDDEN_FILES = {
    "AGENTS.md",
    "CLAUDE.md",
    "IMPLEMENTATION_PLAN.md",
    "PROJECT_CONTEXT.md",
    "HMI_UI_UX_SPEC.md",
    "SQL_QUERIES.sql",
    "Power_RTL_Enterprise_UX_Execution_Roadmap.md",
    "REQ-1A_Client_Requirement_Inventory.md",
    "REQ-1B_Implementation_Gap_Matrix.md",
    "REQ-3I_Clarification_Register.md",
    "docs/CLIENT_DELIVERY.md",
    "docs/CODE_AUDIT.md",
    "docs/CODE_AUDIT_SECOND_PASS.md",
    "docs/UX_DEBT.md",
    "docs/DEMO_RUNSHEET.md",
    "scripts/check_client_release.py",
    "scripts/build_context_pack.py",
}

#: Any path under one of these directories is internal.
FORBIDDEN_PREFIXES = (
    "docs/context/",
    "docs/decisions/",
    "docs/archive/",
    "docs/superpowers/",
    "docs/planning/",
    "command center/",
    "scratch/",
    ".superpowers/",
    ".claude/",
)

#: Filename patterns that are internal wherever they sit.
FORBIDDEN_SUFFIXES = ("_PLANNING_PROMPT.md", "_IMPLEMENTATION_SPEC.md")


def tree_paths(branch: str) -> list[str]:
    result = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", branch],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"cannot read branch {branch!r}")
    return [line for line in result.stdout.splitlines() if line]


def violations(paths: list[str]) -> list[str]:
    found = [
        path
        for path in paths
        if path in FORBIDDEN_FILES
        or path.startswith(FORBIDDEN_PREFIXES)
        or path.endswith(FORBIDDEN_SUFFIXES)
    ]
    return sorted(found)


def main(argv: list[str]) -> int:
    branch = argv[1] if len(argv) > 1 else DEFAULT_BRANCH
    try:
        paths = tree_paths(branch)
    except RuntimeError as exc:
        print(f"Could not check {branch!r}: {exc}", file=sys.stderr)
        return 2

    found = violations(paths)
    if found:
        print(f"Internal material present in {branch!r} - DO NOT PUSH:\n")
        for path in found:
            print(f"  {path}")
        print(f"\n{len(found)} file(s). See docs/CLIENT_DELIVERY.md.")
        return 1

    print(f"{branch!r} is clean: {len(paths)} files, no internal material.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
