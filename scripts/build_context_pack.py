"""Build the per-gate context pack and the project-wide current-state snapshot.

Two outputs, regenerated on every run, neither ever hand-edited:

    .agent-context/START_HERE.md   Hot: this gate only. Gitignored, always
                                    regenerate rather than trust a stale copy.
    docs/context/CURRENT_STATE.md  Warm: project-wide git/test snapshot.
                                    Tracked, so its own history shows how the
                                    baseline moved.

Both are fully derivable from git, the test suite, docs/context/ACTIVE_GATE.md
and docs/decisions/*.md. A fact that needs judgment (why something is frozen,
what's out of scope) belongs in one of those source files, not in generated
output — this script only ever reads them.

Run before starting any task:

    python scripts/build_context_pack.py

    --check        run every validation and report, but write NOTHING.
    --skip-tests   skip the test baseline (the slow check); composable
                   with --check.

`--check` exists for read-only work — an audit or review whose charter
forbids modifying the repository. Without it, Step 0 of AGENTS.md and a
no-write charter are in direct conflict, because `CURRENT_STATE.md` is
TRACKED and this script stamps a timestamp into it, so an ordinary run
dirties the working tree even when nothing has drifted. `--check` still
renders both documents and throws them away, so it cannot report CLEAN on a
pack that would fail to build.

Exits non-zero, and says exactly why, if: an ADR referenced by the active
gate doesn't exist; an ADR's `Implemented-by` commit isn't reachable in this
repo; a `Relevant files` citation doesn't resolve; a frozen pack's own
SHA-256 manifest doesn't verify; or the test baseline is red. A context pack
that reports success while carrying a broken citation is worse than no pack —
this is the automated form of the citation sweep done by hand while writing
the ADRs in docs/decisions/.
"""
from __future__ import annotations

import hashlib
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ACTIVE_GATE = ROOT / "docs" / "context" / "ACTIVE_GATE.md"
DECISIONS_DIR = ROOT / "docs" / "decisions"
AGENT_CONTEXT_DIR = ROOT / ".agent-context"
START_HERE = AGENT_CONTEXT_DIR / "START_HERE.md"
CURRENT_STATE = ROOT / "docs" / "context" / "CURRENT_STATE.md"

#: Untracked, frozen-by-hash planning packs this repo currently has (see
#: docs/CLIENT_DELIVERY.md for why they're untracked rather than gitignored-
#: and-forgotten). Add an entry the day a second one exists.
KNOWN_MANIFESTS = [ROOT / "command center" / "MANIFEST.txt"]

ADR_REF_RE = re.compile(r"ADR-\d{3}[-\w]*\.md")
FIELD_RE = re.compile(r"^([A-Z][\w /-]*):\s*(.*)$")
HASH_LINE_RE = re.compile(r"^([0-9a-fA-F]{64})\s+(.+?)\s*$")


def run(cmd: list[str]) -> str:
    result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return result.stdout.strip()


# ---------------------------------------------------------------------------
# Git facts
# ---------------------------------------------------------------------------

@dataclass
class GitSnapshot:
    branch: str
    head_sha: str
    head_subject: str
    working_tree: list[str]
    recent_commits: list[str]
    merged_branches: list[str]
    unmerged_branches: list[tuple[str, int, int]]  # name, unique-to-branch, behind-main


def git_snapshot() -> GitSnapshot:
    branch = run(["git", "branch", "--show-current"])
    head_sha = run(["git", "rev-parse", "--short", "HEAD"])
    head_subject = run(["git", "log", "-1", "--format=%s"])
    working_tree = [l for l in run(["git", "status", "--short"]).splitlines() if l]
    recent_commits = [l for l in run(["git", "log", "--oneline", "-10"]).splitlines() if l]

    branches = [
        b for b in run(
            ["git", "for-each-ref", "--format=%(refname:short)", "refs/heads/"]
        ).splitlines()
        if b and b != "main"
    ]
    merged: list[str] = []
    unmerged: list[tuple[str, int, int]] = []
    for b in branches:
        counts = run(["git", "rev-list", "--left-right", "--count", f"main...{b}"])
        parts = counts.split()
        if len(parts) != 2:
            continue
        behind_main, unique_to_branch = int(parts[0]), int(parts[1])
        if unique_to_branch == 0:
            merged.append(b)
        else:
            unmerged.append((b, unique_to_branch, behind_main))

    return GitSnapshot(
        branch, head_sha, head_subject, working_tree, recent_commits, merged, unmerged
    )


def commit_reachable(sha: str) -> bool:
    result = subprocess.run(
        ["git", "cat-file", "-e", sha], cwd=ROOT, capture_output=True
    )
    return result.returncode == 0


# ---------------------------------------------------------------------------
# Markdown parsing (shared convention across ACTIVE_GATE.md and every ADR)
# ---------------------------------------------------------------------------

def parse_fields(text: str) -> dict[str, str]:
    """Header `Key: value` pairs, folding soft-wrapped continuation lines.

    A value continues onto following lines until a blank line, a new `Key:`
    line, or a markdown heading. This is what lets ACTIVE_GATE.md and the
    ADRs wrap prose naturally instead of forcing every field onto one long
    line.
    """
    fields: dict[str, str] = {}
    current_key: str | None = None
    lines = text.splitlines()
    if lines and lines[0].startswith("# "):
        lines = lines[1:]  # skip the H1 title; every ADR and ACTIVE_GATE.md opens with one
    for line in lines:
        if line.startswith("#"):
            break
        if not line.strip():
            current_key = None
            continue
        m = FIELD_RE.match(line)
        if m:
            current_key = m.group(1).strip()
            fields[current_key] = m.group(2).strip()
        elif current_key:
            fields[current_key] += " " + line.strip()
    return fields


def section(text: str, heading: str) -> str:
    """Body under a `## heading` up to the next `##` (or end of file)."""
    pattern = re.compile(
        rf"^##\s+{re.escape(heading)}\s*$(.*?)(?=^##\s|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    m = pattern.search(text)
    return m.group(1).strip() if m else ""


def backtick_paths(text: str) -> list[str]:
    """The leading backtick-quoted path on each `- ` bullet line only.

    Deliberately not every backtick span in the section: a bullet like
    ``- `routes.py` — see `ROUTE_POLICY` `` has a path first and an inline
    code reference after the dash, and only the former is a file citation.
    """
    paths = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("-"):
            continue
        m = re.match(r"-\s*`([^`]+)`", stripped)
        if m:
            paths.append(m.group(1))
    return paths


# ---------------------------------------------------------------------------
# ADR metadata
# ---------------------------------------------------------------------------

@dataclass
class AdrInfo:
    name: str
    exists: bool
    status: str | None = None
    implemented_by_raw: str | None = None
    implemented_by_sha: str | None = None
    implemented_by_ok: bool = True


def load_adr(name: str) -> AdrInfo:
    path = DECISIONS_DIR / name
    if not path.exists():
        return AdrInfo(name, exists=False)
    fields = parse_fields(path.read_text(encoding="utf-8"))
    status = fields.get("Status")
    raw = fields.get("Implemented-by", "")
    sha = None
    ok = True
    if raw and not raw.lower().startswith("not yet"):
        # `;` belongs in the strip set for the same reason `,` does: both are
        # used to separate multiple shas in an Implemented-by field. Without
        # it, `` `abc1234`; more prose `` yielded the sha "abc1234`;" and
        # reported a correctly-recorded ADR as unreachable.
        sha = raw.split()[0].strip("`,;()")
        ok = commit_reachable(sha)
    return AdrInfo(name, True, status, raw or None, sha, ok)


def all_adrs() -> list[AdrInfo]:
    return [load_adr(p.name) for p in sorted(DECISIONS_DIR.glob("ADR-*.md"))]


# ---------------------------------------------------------------------------
# Frozen-pack manifest verification (git can't see drift in untracked files)
# ---------------------------------------------------------------------------

@dataclass
class ManifestResult:
    path: Path
    ok: bool
    checked: int
    failed: list[str] = field(default_factory=list)


def verify_manifest(manifest_path: Path) -> ManifestResult:
    if not manifest_path.exists():
        return ManifestResult(manifest_path, False, 0, ["manifest file not found"])
    text = manifest_path.read_text(encoding="utf-8")
    failed: list[str] = []
    checked = 0
    for line in text.splitlines():
        m = HASH_LINE_RE.match(line)
        if not m:
            continue
        expected, relpath = m.groups()
        target = manifest_path.parent / relpath
        checked += 1
        if not target.exists():
            failed.append(f"{relpath}: MISSING")
            continue
        actual = hashlib.sha256(target.read_bytes()).hexdigest()
        if actual != expected.lower():
            failed.append(f"{relpath}: HASH MISMATCH")
    return ManifestResult(manifest_path, checked > 0 and not failed, checked, failed)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def run_tests() -> tuple[bool, str]:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-m", "not db"],
        cwd=ROOT, capture_output=True, text=True,
    )
    lines = [l for l in result.stdout.strip().splitlines() if l]
    if lines:
        summary = lines[-1]
    else:
        # pytest never got as far as producing a summary line - the useful
        # information is on stderr (e.g. "No module named pytest").
        stderr = result.stderr.strip().splitlines()
        summary = f"(no pytest output; stderr: {stderr[-1]})" if stderr else "(no pytest output, no stderr)"
    return result.returncode == 0, summary


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str]) -> int:
    skip_tests = "--skip-tests" in argv
    check_only = "--check" in argv
    problems: list[str] = []
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    if not ACTIVE_GATE.exists():
        print(f"FATAL: {ACTIVE_GATE} does not exist.", file=sys.stderr)
        return 2

    git = git_snapshot()
    gate_text = ACTIVE_GATE.read_text(encoding="utf-8")
    gate_fields = parse_fields(gate_text)

    gate_adr_names = sorted(set(ADR_REF_RE.findall(gate_text)))
    gate_adrs = [load_adr(name) for name in gate_adr_names]
    for adr in gate_adrs:
        if not adr.exists:
            problems.append(
                f"ACTIVE_GATE.md references {adr.name}, which does not exist in docs/decisions/"
            )
        elif not adr.implemented_by_ok:
            problems.append(
                f"{adr.name}: Implemented-by cites {adr.implemented_by_sha!r}, "
                f"not reachable in this repo's git history"
            )

    relevant_files = backtick_paths(section(gate_text, "Relevant files"))
    for rf in relevant_files:
        if rf.startswith("http"):
            continue
        if not (ROOT / rf).exists():
            problems.append(f"ACTIVE_GATE.md Relevant files cites a path that does not exist: {rf}")

    manifest_results = [verify_manifest(m) for m in KNOWN_MANIFESTS]
    for mr in manifest_results:
        if not mr.ok:
            problems.append(
                f"Manifest {mr.path.relative_to(ROOT).as_posix()} did not verify: {'; '.join(mr.failed) or 'no payload lines found'}"
            )

    test_ok, test_summary = (True, "(skipped)") if skip_tests else run_tests()
    if not test_ok:
        problems.append(f"Test baseline is red: {test_summary}")

    non_goals = section(gate_text, "Non-goals (explicit)")
    ambiguities = section(gate_text, "Known ambiguities")
    task = section(gate_text, "Task")

    # Rendered even under --check, and then discarded. A dry run that skipped
    # rendering could report CLEAN on a pack that cannot actually be built,
    # which is the one answer this script must never give.
    start_here_text = render_start_here(
        now, git, gate_fields, task, gate_adrs, relevant_files,
        manifest_results, test_ok, test_summary, non_goals, ambiguities, problems,
    )
    current_state_text = render_current_state(
        now, git, all_adrs(), test_ok, test_summary, gate_fields
    )

    if not check_only:
        AGENT_CONTEXT_DIR.mkdir(exist_ok=True)
        START_HERE.write_text(start_here_text, encoding="utf-8", newline="\n")
        CURRENT_STATE.write_text(current_state_text, encoding="utf-8", newline="\n")

    status = "CLEAN" if not problems else f"{len(problems)} PROBLEM(S)"
    print(f"build_context_pack: {status}")
    verb = "would write" if check_only else "wrote"
    print(f"  {verb} {START_HERE.relative_to(ROOT)}")
    print(f"  {verb} {CURRENT_STATE.relative_to(ROOT)}")
    if check_only:
        print("  --check: nothing written, working tree untouched")
    for p in problems:
        print(f"  PROBLEM: {p}")
    return 1 if problems else 0


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def render_start_here(
    now, git, gate_fields, task, gate_adrs, relevant_files,
    manifest_results, test_ok, test_summary, non_goals, ambiguities, problems,
) -> str:
    lines = [
        "# Start Here",
        "",
        f"Generated {now} from `main` context on branch `{git.branch}` "
        f"(HEAD `{git.head_sha}` \"{git.head_subject}\").",
        "Regenerate with `python scripts/build_context_pack.py` — this file is",
        "overwritten every run and must never be hand-edited.",
        "",
        "**Read `docs/context/ACTIVE_GATE.md` for the full task. This file is",
        "the verification layer on top of it, not a replacement for it.**",
        "",
    ]

    if problems:
        lines += ["## STOP — verification found problems", ""]
        lines += [f"- {p}" for p in problems]
        lines += [
            "",
            "Per AGENTS.md: stop if any authority conflict or stale baseline is",
            "found. Resolve the problems above before treating anything below as",
            "trustworthy.",
            "",
        ]
    else:
        lines += ["## Verification: all clear", "", "Every citation below resolved and the test baseline is green.", ""]

    lines += [
        "## Active gate",
        "",
        f"- Gate: {gate_fields.get('Gate', '(missing)')}",
        f"- Status: {gate_fields.get('Status', '(missing)')}",
        f"- Commit/push permission: {gate_fields.get('Commit/push permission', '(missing — treat as NOT GRANTED)')}",
        "",
    ]
    if task:
        lines += ["### Task", "", task, ""]

    lines += ["## Decisions this gate depends on", ""]
    if gate_adrs:
        lines += ["| ADR | Status | Implemented-by | OK |", "|---|---|---|---|"]
        for adr in gate_adrs:
            if not adr.exists:
                lines.append(f"| {adr.name} | — | — | MISSING |")
            else:
                mark = "yes" if adr.implemented_by_ok else "STALE CITATION"
                short = re.match(r"ADR-\d{3}", adr.name)
                label = short.group(0) if short else adr.name
                lines.append(
                    f"| [{label}](../decisions/{adr.name}) | {adr.status or '—'} "
                    f"| {adr.implemented_by_raw or '—'} | {mark} |"
                )
    else:
        lines.append("(none referenced by ACTIVE_GATE.md)")
    lines.append("")

    lines += ["## Relevant files", ""]
    lines += [f"- `{rf}`" for rf in relevant_files] or ["(none listed)"]
    lines.append("")

    lines += [
        "## Test baseline",
        "",
        f"- `python -m pytest -m \"not db\"` → {test_summary}"
        + (" (not re-run this pass — use --skip-tests deliberately, otherwise trust this)" if not test_ok and test_summary == "(skipped)" else ""),
        "",
    ]

    lines += ["## Frozen-pack verification", ""]
    for mr in manifest_results:
        rel = mr.path.relative_to(ROOT).as_posix()
        lines.append(f"- `{rel}`: {'OK' if mr.ok else 'FAILED'} ({mr.checked} files checked)")
        for f in mr.failed:
            lines.append(f"  - {f}")
    if not manifest_results:
        lines.append("(no known manifests)")
    lines.append("")

    if non_goals:
        lines += ["## Non-goals", "", non_goals, ""]
    if ambiguities:
        lines += ["## Known ambiguities", "", ambiguities, ""]

    lines += ["## Working tree right now", ""]
    lines += ["```"] + (git.working_tree or ["(clean)"]) + ["```", ""]

    lines += ["## Recent commits", "", "```"] + git.recent_commits + ["```", ""]

    return "\n".join(lines) + "\n"


def render_current_state(now, git, adrs, test_ok, test_summary, gate_fields) -> str:
    lines = [
        "# Current State",
        "",
        "Status: generated",
        f"Date: {now}",
        "",
        "Regenerate with `python scripts/build_context_pack.py`. Never hand-edit —",
        "every fact here is derived from git, the test suite, and docs/decisions/.",
        "For judgment calls (why something is frozen, what's in scope right now),",
        "see docs/context/ACTIVE_GATE.md and the ADRs, not this file.",
        "",
        "## Baseline",
        "",
        f"- `main` = `{git.head_sha}` \"{git.head_subject}\"" if git.branch == "main"
        else f"- current branch `{git.branch}` = `{git.head_sha}` \"{git.head_subject}\" (not `main`)",
        f"- Working tree: {'clean' if not git.working_tree else f'{len(git.working_tree)} entries — see below'}",
        "",
        "## Test baseline",
        "",
        f"- `python -m pytest -m \"not db\"` → {test_summary}",
        "",
        "## Branches",
        "",
        "Fully merged into `main` — stale pointers, safe to delete, not pending work:",
        "",
    ]
    lines += [f"- `{b}`" for b in git.merged_branches] or ["(none)"]
    lines += ["", "Diverged from `main` (has commits `main` doesn't):", ""]
    if git.unmerged_branches:
        lines += ["| Branch | Unique commits | Behind main | Note |", "|---|---|---|---|"]
        for name, unique, behind in git.unmerged_branches:
            if name == git.branch:
                note = "current branch — this session's in-progress work, not a stale fork"
            elif name in ("client-demo-1", "client-release"):
                note = "expected — delivery branch, see docs/CLIENT_DELIVERY.md"
            else:
                note = "REVIEW — unexpected divergence"
            lines.append(f"| `{name}` | {unique} | {behind} | {note} |")
    else:
        lines.append("(none)")
    lines.append("")

    lines += ["## Decisions", "", f"{len(adrs)} ADR(s) in `docs/decisions/`. See `docs/context/DECISION_INDEX.md` for the full index.", ""]
    if adrs:
        lines += ["| ADR | Status | Implemented-by |", "|---|---|---|"]
        for adr in adrs:
            lines.append(f"| {adr.name} | {adr.status or '—'} | {adr.implemented_by_raw or '—'} |")
    lines.append("")

    lines += [
        "## Active gate",
        "",
        f"{gate_fields.get('Gate', '(see docs/context/ACTIVE_GATE.md)')} — full detail in `docs/context/ACTIVE_GATE.md`.",
        "",
    ]

    if git.working_tree:
        lines += ["## Working tree", "", "```"] + git.working_tree + ["```", ""]

    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
