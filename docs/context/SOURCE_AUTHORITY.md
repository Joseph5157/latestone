# Source Authority

Status: Approved
Date: 2026-08-29
Applies to: every agent and human working in this repository

This file resolves conflicts. When two sources disagree about what is true,
the higher rung wins and the lower rung is corrected — not averaged, not
"considered alongside".

## The ladder

1. **Client database evidence** — pgAdmin screenshots, real DDL, observed row
   shapes. This is the only rung describing a system we do not control.
2. **This repository's source code** — the running behaviour. Code beats every
   document about this application, including documents that were approved.
3. **Client documents** — the PAD, written client requirements, emailed
   clarifications.
4. **Our planning documents** — planning prompts, spec packs, roadmaps,
   `docs/planning/`, `command center/`.
5. **Our conversations** — chat history, agent memory, prior sessions.

Rung 5 never overrides rung 2. A decision that "we discussed" does not
survive contact with a source file that says otherwise.

## RTL functional requirements authority

For RTL functionality, the sole client requirements authority is `Remote
Temperature Logger Functional Specification RTL v0.3` (Unique Identifier
`240-137264801`, Revision `1`, 18 pages), recorded in
`docs/RTL_FUNCTIONAL_SPEC_COMPLETION_TRACKER.md`. Older PADs, planning packs,
historical audits, architecture material and internal assumptions are
historical/reference material only; they cannot supply, amend, or override an
RTL client requirement. This specific rule governs the broad client-document
rung above wherever the two could otherwise be read together.

## Why code outranks our own approved prose

This is not a style preference. Three CC-1 planning decisions were approved in
prose and were factually impossible against the code:

| Approved in prose | Killed by | What the code actually says |
|---|---|---|
| `<3.61V` / `<3.75V` numeric Critical/Warning thresholds | `services/event_semantics.py:11-15` | EVT-D4 forbids consumers holding numeric thresholds; an incoming `battery_low` row is *already a classified fact*, and `battery_voltage` is display payload only |
| Requires Attention includes a third bucket | `components/fleet_condition.py:3-4` | "Attention remains Stale + No Data" |
| Location has Zone / Feeder / GIS levels | `plants` table | plants carry country / lat / long only |

All three read as reasonable in the document. None was discoverable without
opening the source. That is the failure mode this ladder exists to prevent.

## Rules that follow from the ladder

- **Cite, don't assert.** A claim about application behaviour must carry a
  `path:line` or it is a proposal, not a fact.
- **Conflicts are reported before they are resolved.** If a rung-3 client
  document contradicts rung-2 code, stop and surface it. Do not silently
  implement either side — the gap may be a real client change request.
- **Absence is not permission.** `services/event_semantics.py` deliberately has
  no entry for high-temperature or vibration because those are open client
  clarifications. Structural absence is a decision; do not fill it in.
- **A frozen document can still be wrong.** Freezing stops edits; it does not
  promote the document above the code it describes.

## Rung 1 — what we actually know about the client database

Confirmed from client screenshots, not inferred:

- PostgreSQL, schema `trfr_temperature`, approximately 2,112 tables.
- Table naming is `<transformer>_<device>` — e.g. `aa12_29017`, `aa28_29044`.
- Temperature tables carry `timestamp` and `temperature` as **VARCHAR**.
- `timestamp` is the primary key in the shown DDL.
- Readings arrive at roughly 30-minute intervals.
- The client intends to consolidate toward a single table.

`plant_monitoring` is **our development schema**, not the client's production
schema. Do not describe our schema as if it were theirs.

## Where each kind of question is answered

| Question | Authoritative source |
|---|---|
| What is true of the client's production DB? | rung 1 evidence; `DATABASE.md` records it |
| What does this app currently do? | the source file, cited by path:line |
| What is the current commit / test baseline? | `docs/context/CURRENT_STATE.md` (generated — never hand-edited) |
| Was this decided, and does it still stand? | `docs/context/DECISION_INDEX.md` → `docs/decisions/ADR-*.md` |
| What am I allowed to change right now? | `docs/context/ACTIVE_GATE.md` |
| Which RTL client requirement drives this? | `docs/RTL_FUNCTIONAL_SPEC_COMPLETION_TRACKER.md` |

Anything under `docs/archive/` is historical. It records what we once thought.
It is never evidence for what is true now.
