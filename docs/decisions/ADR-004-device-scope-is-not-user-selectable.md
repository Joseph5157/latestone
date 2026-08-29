# ADR-004: Device scope is authorization-derived — no page may offer a scope selector

Status: Approved
Date: 2026-08-22 (ROLE-3), reaffirmed for Command Center 2026-08-28
Evidence: `services/device_scope.py:1-24` (module contract); `services/authorization.py:41-73` (`ROUTE_POLICY`, `ADMINISTRATOR`/`TECHNICIAN`/`GENERAL`)
Implemented-by: `9966bd7` (`DeviceScope` as the single device-visibility authority), merged to `main` at `71b8db6`
Supersedes: nothing new — this ADR backfills a ROLE-3 decision that Command Center's header now also depends on

## Decision

`services/device_scope.py` is **the only** answer to "may this user see this
RTL?" (module docstring, line 3). `DeviceScope.device_ids` is either `None`
(unrestricted — Administrator and General) or a `frozenset` (Technician,
scoped to assignments). No second predicate is permitted to exist anywhere in
the codebase, including a new one written for Command Center.

For Command Center specifically: any header or shell element that shows the
current scope (device count, "your fleet", etc.) is a **read-only indicator**
of what `scope_for()` already returns. There is no selectable scope, no
dropdown to pick a different device set, and no admin "view as technician"
control. Building one would be a second predicate answering the same
question `services/device_scope.py` already owns — exactly the failure mode its own
docstring calls out: "two tables answering one question each pass their own
tests while contradicting each other."

Technician scope resolves per session via one assignment read
(`scope_for` — impure, deliberately: "Resolve it once per render and pass the
result down; do not call it in a loop," `services/device_scope.py:9-11`). Command
Center must follow that same call discipline, not re-resolve scope per panel.

## Affected areas

- `services/device_scope.py` — the authority; do not duplicate
- `services/authorization.py` — route-level access, a different question
  (may this role open this route) that device scope does not answer and vice
  versa; keep the two separate per the module's own "SCOPE" section
  (`services/authorization.py:28-34`)
- `command center/components/CC01_HEADER.md` — the header scope indicator
  this ADR binds
- Any future Command Center service — must call `scope_for()` once per render
  and filter through the returned `DeviceScope`, never write a new query
  predicate
