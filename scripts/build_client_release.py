"""Deterministic filtered client-release export (ADR-034).

Builds a client-release tree from the *tracked Git content* of one exact
commit, applying the release exclusion contract. It never reads the working
directory, so untracked / .gitignore'd material (.env, RTL.bak, .test-tmp,
scratch, agent tooling) is structurally impossible to include.

    python scripts/build_client_release.py <ref> --out <dir> [--force]

`<ref>` is a commit SHA (preferred), tag, or branch. The same SHA always
produces the same tree. The exclusion rules are imported from
`check_client_release.py` so the build and the pre-push validation can never
drift. After writing, it re-validates the produced file list and refuses to
leave an export containing any forbidden path.

Exit 0 = clean export written; 1 = a forbidden path survived (bug) or inputs
invalid; 2 = git could not read the ref.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

# Single source of truth for the exclusion contract.
from check_client_release import violations  # noqa: E402  (same directory)


def _git(args: list[str], *, binary: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        capture_output=True,
        text=not binary,
    )


def tracked_paths(ref: str) -> list[str]:
    result = _git(["ls-tree", "-r", "--name-only", ref])
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"cannot read ref {ref!r}")
    return [line for line in result.stdout.splitlines() if line]


def resolve_sha(ref: str) -> str:
    result = _git(["rev-parse", ref])
    return result.stdout.strip() if result.returncode == 0 else ref


def file_bytes(ref: str, path: str) -> bytes:
    result = _git(["show", f"{ref}:{path}"], binary=True)
    if result.returncode != 0:
        raise RuntimeError(f"cannot read {ref}:{path}")
    return result.stdout


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("ref", help="commit SHA (preferred), tag, or branch to release from")
    parser.add_argument("--out", required=True, help="output directory for the release tree")
    parser.add_argument("--force", action="store_true", help="allow writing into a non-empty directory")
    args = parser.parse_args(argv)

    try:
        all_paths = tracked_paths(args.ref)
    except RuntimeError as exc:
        print(f"Could not read {args.ref!r}: {exc}", file=sys.stderr)
        return 2

    excluded = set(violations(all_paths))
    included = [p for p in all_paths if p not in excluded]

    # Safety: the included set must itself be clean. If this ever trips, the
    # exclusion rules and this filter have diverged — refuse rather than ship.
    leaked = violations(included)
    if leaked:
        print("BUG: forbidden paths survived filtering - NOT writing:", file=sys.stderr)
        for path in leaked:
            print(f"  {path}", file=sys.stderr)
        return 1

    out = Path(args.out)
    if out.exists() and any(out.iterdir()) and not args.force:
        print(f"Output directory {out} is not empty (use --force).", file=sys.stderr)
        return 1
    out.mkdir(parents=True, exist_ok=True)

    for path in included:
        dest = out / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(file_bytes(args.ref, path))

    sha = resolve_sha(args.ref)
    print(f"Release export written to {out}")
    print(f"  ref            : {args.ref}")
    print(f"  resolved SHA   : {sha}")
    print(f"  tracked files  : {len(all_paths)}")
    print(f"  included       : {len(included)}")
    print(f"  excluded       : {len(excluded)}")
    # A few explicit guarantees worth printing for the operator.
    for canary in (".env", "RTL.bak"):
        print(f"  {canary!r} present: {(out / canary).exists()}")
    print(f"  docs/audit/ present: {(out / 'docs' / 'audit').exists()}")
    print(f"  docs/context/ present: {(out / 'docs' / 'context').exists()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
