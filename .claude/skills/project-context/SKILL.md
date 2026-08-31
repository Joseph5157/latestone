---
name: project-context
description: Use before any planning, implementation, debugging, or code-review task in this repository (powerplant-dashboard) that will read or write application code. Verifies the repo baseline via scripts/build_context_pack.py, reads AGENTS.md and the active gate, resolves the ADRs and files it names, and requires reporting authority conflicts before any edit. Do not use for a quick question fully answered by reading one already-open file, or for actions outside the repo (Railway, browser automation, unrelated shell commands).
---

# Project Context

This repo went through three failure modes before this skill existed:
context-window pressure pushing earlier facts out, retrieval failure (the
answer existed somewhere but nothing said where), and authority confusion
(an old planning document retrieved and treated as current when it was only
ever proposed, or was already superseded). `docs/context/`,
`docs/decisions/`, and `scripts/build_context_pack.py` exist to fix the
second and third. This skill is the procedure that actually uses them,
instead of them sitting there unread while an agent explores from scratch.

If a request is fully answered by a file already open in the conversation,
skip this and just answer. This is for work that touches the codebase.

If another process skill also applies (`superpowers:brainstorming`,
`superpowers:systematic-debugging`), run this one first. It establishes
*what the task is and whether it's authorized*; they handle *how*.

## The procedure

**1. Verify repository and baseline.**

Run `python scripts/build_context_pack.py` — or `--check` if this task is
read-only and may not write (it runs every validation and writes nothing;
the plain command rewrites the tracked `CURRENT_STATE.md` and so dirties the
tree). If it exits non-zero, it printed specific `PROBLEM:` lines — a broken ADR citation, an unreachable
`Implemented-by` commit, a `Relevant files` path that no longer exists, a
frozen pack whose hash no longer verifies, or a red test baseline. **Stop.**
Show the user the problems. Do not work around a failed pack by reading
source files directly instead — a stale or broken baseline is exactly the
condition this step exists to catch before it wastes the rest of the task.

**2. Read `AGENTS.md` in full.**

Not skimmed, not recalled from a previous session. Mission, scope, stack,
architecture rules, testing expectations. It is short by design (under the
32 KiB Codex limit) specifically so this is cheap.

**3. Read `docs/context/ACTIVE_GATE.md` in full.**

This is the only task currently in scope. If the user's request doesn't
match what this file describes, don't silently reinterpret the gate to fit
the request or the request to fit the gate — tell the user which one is
stale: either `ACTIVE_GATE.md` needs rewriting for a new gate (finished work
moves to `docs/decisions/` or `docs/archive/`, never appended), or the
request falls outside the current gate's non-goals and needs its own.

**4. Resolve every ADR the gate links — read the ADR file itself, not just
its one-line row in the pack's summary table.**

The generated pack tells you an ADR exists and its citations resolve; it
does not tell you the ADR's actual reasoning, evidence, or open questions.
`docs/context/SOURCE_AUTHORITY.md` governs what outranks what if two sources
disagree: client DB evidence > this repo's source code > client documents >
our planning docs > our conversations. Notably, code outranks even an
Approved ADR's own prose if they've drifted — verify a load-bearing claim
against the file:line it cites, don't trust the ADR's paraphrase of it.

**5. Inspect only what the gate's `Relevant files` section names**, plus
whatever those files' own imports require to understand them. Resist
exploring the rest of the codebase because it looks related — that is how
Hot-level work quietly becomes a Cold-level read of project history.
`docs/archive/` is never a legitimate stop on this path: it is superseded
planning material, not evidence for current behaviour.

**6. Report conflicts before editing anything.**

Stop and surface it — don't silently resolve it by picking a side — if any
of these show up while reading:
- Source code contradicts what an ADR says it does.
- Two ADRs disagree, or an ADR contradicts `ACTIVE_GATE.md`.
- The gate's recorded baseline (branch/HEAD) no longer matches what
  `scripts/build_context_pack.py` just reported.
- A "Known ambiguity" the gate already flagged is directly relevant to the
  change about to be made.

**7. Implement and test.**

Follow `AGENTS.md`'s architecture rules and coding style — thin callbacks,
no raw SQL outside the repository layer, services never depend on
components. Run the tests `ACTIVE_GATE.md` names under "Required tests", or
at minimum `python -m pytest -m "not db" -v`. Fix red tests before moving on
to the next step; a gate that changes no application code should never turn
a passing suite red.

**8. Update context records as part of this same piece of work — not as a
follow-up someone else does later.**

- A decision made or changed during implementation gets written into an ADR
  (new file, or an existing one's `Status`/`Supersedes` field) — never only
  a memory note. Memory is a pointer cache to the ADR, not a substitute for
  one (`AGENTS.md`, Claude-specific notes).
- Re-run `scripts/build_context_pack.py` so `docs/context/CURRENT_STATE.md`
  reflects the new HEAD. It is generated and tracked specifically so this
  step is one command, not a rewrite.
- When the gate itself completes, rewrite `ACTIVE_GATE.md` for whatever
  gate opens next.

**9. Check `Commit/push permission` in `ACTIVE_GATE.md` before either.**

If it says `NOT GRANTED`, or names a precondition (a branch merge, an
external review) that hasn't happened yet, do not commit or push. Tell the
user exactly what's blocking it and stop there — that field exists so this
question has one answer instead of being re-litigated per task.
