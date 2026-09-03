# Active Gate

Status: Complete — committed, pushed and remote-verified
Date: 2026-09-03
Gate: CLIENT-SYNC-1 — carry the accepted CC-2 presentation repair to the
client Command Center progress branch
Branches: `main` records the gate; `cc-1-command-center-progress` is the
curated client delivery branch and matches
`client/cc-1-command-center-progress` at `3d4897c`.
Commit/push permission: GRANTED by the operator on 2026-09-03 and exercised
only for the two explicitly authorized branch targets.

## Purpose

The client progress branch contains the accepted Command Center feature but
still carries the rank-bar CSS from before CC-2. Three read-only collaborators
can see that branch. Carry the two presentation-only repairs implemented by
ADR-012 into that branch without merging either repository history or exposing
internal engineering material.

This gate follows the completed INT-1/CTX-PACK-1 gate. The operator requested
continuation from the `PCB-8-CLOSE` handoff on 2026-09-03; no repository file
uses that label, so this gate is grounded in the first queued successor named
by the prior gate and in a fresh remote/branch audit.

## Evidence at gate open

- `git fetch client` completed with the remote branch still at `34d5d73`.
- `main` and the client repository have intentionally separate histories; they
  have no merge base. The client branch must be curated, not merged.
- The client branch's relevant CSS is the exact pre-CC-2 form: the rank row is
  `minmax(0, 10rem) 1fr auto`, the fill uses the light-only freshness token,
  the full locations page restores a `1fr` bar, and the generic scrolling card
  body has no overlay-scrollbar clearance.
- `main` carries the accepted repair in `e33d0e1` and `59f92a9`, recorded by
  ADR-012.
- `python scripts/check_client_release.py
  client/cc-1-command-center-progress` reports 263 files and no internal
  material.

## In scope

Apply only the `assets/app.css` hunks from `e33d0e1` and `59f92a9` to the
client progress branch, preserving their final combined behaviour:

- cap the rank-bar track while allowing it to shrink in narrow panels;
- keep name, bar and count adjacent instead of letting a track absorb surplus;
- use the route-scoped Command Center colour token with the established
  fallback;
- remove the full-page override that puts the bar back on `1fr`;
- reserve padding for an overlay scrollbar in the generic Command Center card
  body.

The final relevant CSS must be byte-for-byte equivalent to `main` for the
selectors changed by the two implementation commits. No Python, schema, seed,
test or dependency change is needed.

## Explicitly out of scope

- Merging or rebasing the unrelated `main` and client-repository histories.
- Copying all of `assets/app.css`; the client branch has intentionally curated
  baseline differences outside the Command Center repair.
- Updating `client/main`, `client-release`, or any other client-visible branch.
- Copying `docs/context/`, `docs/decisions/`, `command center/`, or any other
  internal planning/engineering material into the client repository.
- Pulling FIX-1 callback changes or any other queued follow-up into this gate.

## Relevant files

- `docs/context/ACTIVE_GATE.md`
- `docs/context/CURRENT_STATE.md` (generated only)
- `docs/decisions/ADR-012-rank-bars-are-capped-and-route-themed.md`
- `docs/CLIENT_DELIVERY.md`
- `scripts/check_client_release.py`
- `assets/app.css` in the curated client progress worktree

## Required verification

Before this gate can close:

1. Run the client branch's non-DB suite:
   `python -m pytest -m "not db" -v`.
2. Run `git diff --check` in the client progress worktree.
3. Prove that the final CSS declarations affected by `e33d0e1` and `59f92a9`
   match `main`, without asserting equivalence for unrelated CSS.
4. Re-run the client-release guard against the prepared client commit/tree.
5. Run `python scripts/build_context_pack.py` on `main` after the gate record
   is written and again before closure.

`docs/CLIENT_DELIVERY.md` requires the full suite before a push to the client
remote. A push therefore also requires `python -m pytest -v` to pass in the
client worktree, including its DB-marked tests.

## Outcome

CLIENT-SYNC-1 is complete. The existing client worktree at
`../powerplant-dashboard-client-progress` committed the one approved
modification, `assets/app.css` (71 insertions, 18 deletions), as:

```text
3d4897cdd903d6012fca94620caedc73e081f517
fix(client): synchronize accepted Command Center progress
```

The push used the explicit refspec
`cc-1-command-center-progress:cc-1-command-center-progress`. A subsequent
`git ls-remote client refs/heads/cc-1-command-center-progress` returned the
same full SHA, so local and remote are a verified match.

Verification on 2026-09-03:

- `python -m pytest -m "not db" -v` — **2,015 passed, 389 deselected**.
- The first configured full-suite run — **2,403 passed, 1 failed** — reproduced
  the already-recorded order-sensitive DB timing check:
  `test_batched_latest_returns_all_eight_metrics` took 91 ms against its 80 ms
  budget. It passed alone immediately afterwards.
- A second full-suite run against the warm database — **2,404 passed** in
  63.56 seconds.
- Canonicalized patch-body comparison against the combined
  `23d3743..59f92a9` `assets/app.css` diff — **exact match**, 140/140 lines.
- `git diff --check` — clean.
- `python scripts/check_client_release.py cc-1-command-center-progress` —
  **clean after commit**, 263 tracked files and no internal material.
- Client worktree after commit — clean.
- Local client progress SHA —
  `3d4897cdd903d6012fca94620caedc73e081f517`.
- Remote client progress SHA —
  `3d4897cdd903d6012fca94620caedc73e081f517` (**MATCH**).
- `python scripts/build_context_pack.py` at gate close — **CLEAN**; the
  immediate `--check` validation was also **CLEAN** and wrote nothing.

No visual re-acceptance was repeated here. The patch is byte-equivalent to the
two presentation changes already measured and accepted under CC-2/ADR-012;
this gate curates that result without altering it.

## Boundaries observed

- Client `main` was not pushed or modified.
- No merge, rebase, force push, branch deletion or tag creation occurred.
- No internal engineering material or unrelated file entered the client
  commit.
- The authoritative repository's untracked `debug.log` was not staged,
  edited, committed or pushed.

## Commit/push permission

GRANTED by the operator on 2026-09-03 for the client progress commit/push and
the separate authoritative `main` context-close commit/push. The client
authorization was exercised at `3d4897c`; the authoritative push is the final
action of this close gate and must be remote-verified after the close commit.

## Next queued gate — do not start

**DB-ORDER-1 — DB test-order/timing sensitivity.** The full-suite first pass
again reproduced the already-recorded `test_batched_latest_returns_all_eight_metrics`
timing failure, while the test passed alone and the immediate full-suite rerun
passed all 2,404 tests. This is the next queued Power application concern from
the prior authoritative gate. It is outside CLIENT-SYNC-1 and remains unstarted
pending a separate gate and operator instruction.
