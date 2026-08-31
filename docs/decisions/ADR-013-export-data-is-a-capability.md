# ADR-013: EXPORT_DATA is an application capability, not a device action

Status: Approved
Date: 2026-08-31
Evidence: `services/authorization.py` (`CAPABILITY_POLICY`, `ACTION_POLICY`);
`services/action_guard.py:50` (`require_action`), `:92` (`require_capability`);
`callbacks/report_center.py` (`download_report_csv`, `_gather_export_rows`);
`services/report_service.py:61` (`installed_rtls_rows`, scope intersection);
`services/report_export.py` (R4-D3)
Implemented-by: `723dd0b`
Supersedes: **R4-D3** (`services/report_export.py`), in the part naming the
guard

## Context

`download_report_csv` called `require_action(user, EXPORT_DATA)`. That guard's
signature is `require_action(user, action, *, device_id: str)` — `device_id`
keyword-only, no default — so the call raised

```
TypeError: require_action() missing 1 required keyword-only argument: 'device_id'
```

before any row was fetched. The surrounding `except AuthorizationError` cannot
catch a `TypeError`, so the failure escaped the callback entirely.

**This never worked.** ROLE-3 added `device_id` to `require_action` in
`45f2e6e` (2026-08-22); `require_capability` arrived in `1db0f60`
(2026-08-24); the export callback was written in `2248afd` (2026-08-25),
three days after the signature changed and one day after the correct guard
existed. There is no commit in which this download path succeeded. Nothing
is being restored here — it is being made to work for the first time.

### The device dimension was always inert

`ACTION_POLICY` entries are `(roles allowed on any device, roles allowed only
on assigned ones)`. `EXPORT_DATA` read `(_EVERY_ROLE, _NO_ROLE)`. An empty
second set means no role's export permission ever depended on an assignment,
and `require_action` documents that it tests the any-device set first and
returns without touching the database when it matches. So the `device_id`
argument decided nothing for export, on any code path.

### A report has no device to name

`_gather_export_rows` passes `device_id=… if asset_scope == "device" else
None`. A report covers a plant (many devices), a transformer (many), one
device, or — per R4-D5, which stands — zero rows at all. There is no single
identifier `require_action` could be given honestly. `require_capability`'s
own docstring anticipates precisely this: inventing a placeholder id "would
both lie about the dimension and pay for an assignment read whose answer
could not matter."

## Decision

`EXPORT_DATA` moves from `ACTION_POLICY` to `CAPABILITY_POLICY` with the
**same role set**, and the callback calls `require_capability`.

```python
CAPABILITY_POLICY = { ..., EXPORT_DATA: _EVERY_ROLE }   # was (_EVERY_ROLE, _NO_ROLE)
```

The constant also moves up beside the other capability constants, so its
position in the file states its dimension.

### No authorization changes

`_EVERY_ROLE` is `frozenset(CONFIRMED_ROLES)` — administrator, technician,
general. All three exported before and export now. Both guards refuse
`user is None` with the same `AuthorizationError`. Unknown roles are refused
by both tables' default-deny. This is a change of **dimension**, not of
permission, and the migrated tests assert the role set explicitly so a
silent widening or narrowing would have failed.

### Scope is not, and never was, this guard's job

The guard never constrained which devices a report could reach:

```
scope_from_session(auth_data) -> DeviceScope
  -> _gather_export_rows(..., device_scope=scope)
  -> installed_rtls_rows(device_scope=...)
  -> repo.installed_rtls_report_rows(allowed_device_ids=scope.device_ids)
```

`installed_rtls_rows` states it: "Scope intersection is delegated entirely to
the repository's ANDed filters — no second visibility predicate lives here."
A technician's rows were, and remain, narrowed by `allowed_device_ids`. This
ADR does not touch `DeviceScope`, the repository filters, or the asset-scope
form parameters. Because the claim is load-bearing and easy to break later,
it is asserted directly rather than assumed:
`test_technician_export_stays_inside_the_assigned_scope` and
`test_out_of_scope_devices_cannot_be_reached_through_export`.

## What R4-D3 got right, and what it did not

R4-D3 (`services/report_export.py`) read:

> Authorization lives in the CALLBACK via require_action(EXPORT_DATA) before
> any rows are fetched; this module performs none.

Two of its three claims stand and are unchanged: authorization belongs in the
callback, and it must run **before any rows are fetched**
(`test_refusal_happens_before_any_row_work` pins this). Only the named guard
was wrong — and it was wrong the day it was written, describing a
two-argument `require_action` that had already stopped existing. Its text is
corrected in the same commit as the code, per `AGENTS.md`: a supersession
discoverable only from the new record is not a supersession.

## Consequences

- The CSV download works for the first time.
- Four existing test files were **migrated, not deleted**. Each kept its
  original claim and changed only the API asserting it:
  `test_authorization.py` (the every-role claim moved from the action matrix
  to the capability matrix, plus a new assertion that `ACTION_POLICY` no
  longer answers for export, so the two tables cannot disagree),
  `test_action_guard.py`, `test_action_guard_db.py`,
  `test_report_export_db.py`.
- `test_action_guard.py::test_may_export_without_an_assignment_lookup`
  becomes structural: it previously asserted the assignment read was skipped;
  with a guard that has no device, there is nothing to skip.
- `EXPORT_DATA` left the unknown-role parametrize list in the action
  default-deny tests and joined the capability one. Left in place it would
  have tested the unknown-**action** default-deny under a misleading name.

## What this ADR does not decide

R4-D1's honesty contract (CSV is a development-default format, the
client-approved production format is unresolved) is untouched, as are R4-D9's
limit on which reports are exportable and R4-D5's header-only zero-row file.
This ADR is about which guard authorizes an export, not about what an export
is.
