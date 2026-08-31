# Active Gate

Status: Complete — INT-1 integrated, CTX-PACK-1 closed
Date: 2026-08-31
Gate: INT-1 Command Center integration, with CTX-PACK-1 folded in
Branch: `main`, fast-forwarded to `5901945` and carrying `bc711e9` on top.

Two gates are recorded together because the second existed only to unblock
the first. FIX-1's record, which this replaces, is
`docs/decisions/ADR-013-export-data-is-a-capability.md` plus the commits
`723dd0b` and `5901945`.

## INT-1 — integrate the accepted Command Center history into `main`

**Done, by fast-forward. No history rewritten, nothing squashed.**

The premise needed correcting first. The seven commits described as
"local-only on `main`" were local-only relative to **`origin/main`**, not
relative to the feature branch — all seven were already ancestors of
`cc-1-command-center-foundation`, which had been cut from `d34090f`:

```
git rev-list --left-right --count main...cc-1-command-center-foundation
0    34
git merge-base main cc-1-command-center-foundation
d34090f   (= local main HEAD before integration)
```

So overlap analysis returned **NONE**, structurally rather than by
inspection: shell, Fleet Overview, Command Center, CSS, context docs and the
authorization/callback fixes could not conflict, because the branch already
contained every one of those commits unmodified. The seven are one coherent
tranche — the CTX-1 context architecture (`SOURCE_AUTHORITY`, the archived
planning prompts, the ADR-005..007 backfill, `build_context_pack.py` itself,
the `project-context` skill) plus the CC-1 execution-plan review that
recorded ADR-008. Nothing unrelated or unexplained, so the stop condition
never triggered.

| ref | before | after |
|---|---|---|
| `main` | `d34090f` | `5901945`, then `bc711e9` |
| `origin/main` | `1d7c414` | unchanged until pushed |
| `cc-1-command-center-foundation` | `5901945` | `5901945` (pushed, untouched) |

FIX-1 provenance verified reachable from `main`: `723dd0b` and `5901945`.
The seven retain their original shas.

## CTX-PACK-1 — restore the frozen pack's byte identity

Implemented-by: `bc711e9`

**INT-1 was blocked by this and nothing else.** The integration itself was
sound and green — 2,504 non-DB and 487 DB-marked passed on the integrated
`main` — but `build_context_pack.py` reported the frozen Command Center
manifest failing on eight files, so the "pack green at gate close" rule
could not be satisfied and `main` was not pushed.

**Root cause: byte normalization, not content drift.** `.gitattributes`'
`* text=auto eol=lf` normalized eight CRLF-authored files to LF when the
pack was staged in `23d3743`, while `MANIFEST.txt` hashes the pack as
delivered. It was invisible until INT-1's `git checkout` materialised those
files from the index as LF — the working copy had simply never been
rewritten. Every clone of `origin` already had the fault.

Proved rather than assumed: for the eight mismatching files, reconstructing
CRLF reproduced the manifest SHA-256 **exactly**; for the other fifteen the
worktree, the blob and the manifest already agreed. The restore recomputes
each candidate and refuses to write unless it already equals the frozen
value, so the manifest was evidence throughout and never output. No hash was
regenerated. LF-normalised content is identical to `HEAD` for all eight.

Two failures were reproduced while fixing it, both of which would have
shipped a repair that did nothing:

- `command center/** -text` is **invalid** — the space splits the pattern and
  git reports `center/** is not a valid attribute name`, leaving the rule
  inert. The eight files then show as unmodified and a commit stores LF
  again. The pattern must be quoted.
- `-text` makes `git diff --check` flag every preserved CR as trailing
  whitespace — 104KB of false positives on a check this repo runs at every
  gate. `whitespace=-trailing-space` is scoped to the same paths.

The rule is `"command center/**" -text whitespace=-trailing-space`, scoped to
exactly the unit the manifest covers. `git check-attr` confirms
`callbacks/user_admin.py` still resolves `text: auto`.

## Verification

- Context pack **CLEAN**.
- All 23 manifest entries verify — in the worktree **and** in the staged
  blobs a fresh clone receives, which is the check that was actually failing.
- `git diff --check` clean.
- Application code untouched by CTX-PACK-1: the commit contains
  `.gitattributes` and eight pack files, nothing else.
- The full suites were run on the integrated `main` before CTX-PACK-1 —
  2,504 non-DB, 487 DB-marked — and were not re-run for a line-ending
  storage change that touches no application code.

## Known consequence, deliberately not chased

`cc-1-command-center-foundation` is pushed and still at `5901945`, so it does
**not** carry `bc711e9`: a checkout of that branch still reports the broken
manifest. Left alone rather than force-advancing the feature branch to regain
equality. If anything continues working from that branch, it should move to
`main` or take the fix.

## Queued follow-ups — outside both gates

- **CLIENT-SYNC-1** — `client/cc-1-command-center-progress` still carries the
  pre-CC-2 CSS, and the client repo now has three read-only collaborators.
- **DB test-order sensitivity** — a green DB suite is currently
  order-dependent; investigated during FIX-1B and recorded there.
- **Device Administration duplicated column spec** — the page and the
  callback each declare the column list.
- **Discoverability of View** — the explicit link is gone; the device name
  navigates.

## Required tests

`python -m pytest -m "not db" -v`, plus `-m db` for the authorization and
report suites.

## Commit/push permission

GRANTED by the user on 2026-08-31 for both gates. `main` is pushed to
`origin/main` as the final action of INT-1, and the remote is verified
explicitly afterwards rather than inferred from the push succeeding.
