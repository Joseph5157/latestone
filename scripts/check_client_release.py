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
    # --- added after CLIENT-SYNC-2A, which found these tracked on `main`
    # --- and reachable by a careless copy while this guard stayed silent.
    #
    # Our open questions about the client's own vibration sensor. Publishing
    # it hands the client a list of things we do not know, presented as
    # project material.
    "docs/VIBRATION_METRIC_CONTRACT_TBD.md",
    # Internal decision/review gate record, same class as docs/context/.
    "docs/RTL_CLIENT_REVIEW_GATE.md",
    # The client's own specification PDF and the text extracted from it.
    # Theirs, not ours to redistribute back to them as our deliverable.
    "DEM-2788838 Digital Incubator - RTL PAD  v0.7.pdf",
    "pdf_content.txt",
    "pdf_content_up_to_3.4.txt",
    # Internal working scripts: a database inspection scratch script and the
    # generators for our own internal workflow documents.
    "check_databases.py",
    "scripts/generate_workflow_pdf.py",
    "scripts/generate_workflow_deep_dive_pdf.py",
    # Our deployment infrastructure, not part of the delivered application.
    "railway.json",
    # --- added after CLIENT-SYNC-5, which found 33 files that
    # --- docs/CLIENT_DELIVERY.md forbids by name and this guard allowed.
    # --- They never leaked only because hand-curation happened to be
    # --- conservative, which is not a control.
    #
    # Our audit of the client's own PAD, and our audit of how far their
    # feedback has been implemented. Both are internal assessments.
    "docs/PAD_SECTIONS_1_TO_3_4_AUDIT.md",
    "docs/CLIENT_FEEDBACK_IMPLEMENTATION_AUDIT.md",
    # Tests of tooling that is itself never delivered: they would fail on a
    # clean client clone because the script under test is absent. See
    # "A delivered test may not depend on undelivered material" in
    # docs/CLIENT_DELIVERY.md.
    "tests/test_build_context_pack_check.py",
    "tests/test_context_pack_gate_guard.py",
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
    # Internal design and acceptance artefacts. Named in
    # docs/CLIENT_DELIVERY.md since CLIENT-DEMO-1; only enforced here from
    # CLIENT-SYNC-5.
    "docs/ux-baseline/",
    "docs/wireframes/",
)

#: Prefixes that are internal regardless of the case they are written in.
#: `docs/RTL_FUNCTIONAL_SPEC_EXTRACT.md` and
#: `docs/rtl_current_route_inventory.md` both exist on `main`, so a
#: case-sensitive rule would catch one and miss the other.
FORBIDDEN_PREFIXES_CASE_INSENSITIVE = (
    # Our working notes ON the client's specification — extracts from their
    # PAD, trackers of what it still requires, and the list of technical
    # input we are waiting on them for. Handing these back reads as project
    # material and exposes what we do not know.
    "docs/rtl_",
    # Internal UX acceptance records for gates we ran.
    "docs/ux_acceptance_",
)

#: Filename patterns that are internal wherever they sit.
FORBIDDEN_SUFFIXES = (
    "_PLANNING_PROMPT.md",
    "_IMPLEMENTATION_SPEC.md",
    # Session/debug artefacts and database backups. Named by SHAPE rather
    # than by filename because the exact list above is the part that rots —
    # `PURGE_ORDER` and this file's own sibling checks both went stale
    # exactly that way. A pattern keeps catching tomorrow's `debug2.log`.
    ".log",
    ".dump",
    ".bak",
    ".sql.gz",
    ".pyc",
)

#: The only dotenv file that may ship. Everything else matching `.env*`
#: is a real environment file and therefore real credentials.
ALLOWED_ENV_FILE = ".env.example"


def _is_secret_env_file(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    return name.startswith(".env") and name != ALLOWED_ENV_FILE


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
        or path.lower().startswith(FORBIDDEN_PREFIXES_CASE_INSENSITIVE)
        or path.endswith(FORBIDDEN_SUFFIXES)
        or _is_secret_env_file(path)
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
