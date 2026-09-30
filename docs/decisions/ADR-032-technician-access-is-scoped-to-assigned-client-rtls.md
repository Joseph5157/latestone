# ADR-032: Technician access is scoped to assigned client RTLs, and assignment is application-owned

Status: Approved
Date: 2026-09-30
Evidence: `docs/audit/technician-assignment-forensics-01/TECHNICIAN_ASSIGNMENT_FORENSICS.md`;
`docs/database/CLIENT_RTL_SQLSERVER_KNOWLEDGE_BASE.md` §19 and §23;
`docs/client/CLIENT_DB_CLARIFICATION_01_RESPONSE_TRACKER.md` CDB-05;
`services/rtl_scope.py`; `services/rtl_assignment_service.py`;
`alembic/versions/016_rtl_technician_assignments.py`
Implemented-by: `ec3be92` (`feat(technicians): scope access to assigned RTLs`; full sha ec3be9243acc54975816f79f3fcadb73018455ef — the commit carries this ADR too, so the sha is recorded here afterwards, as ADR-031 did)

## Context

Until now the real client-RTL routes (`/rtls`, `/rtls/<uid>`, `/rtls/network`,
`/events`, the factual dashboard) were closed to Technicians because no approved
map from a client RTL UID to a Technician existed. Forensics found a clean but
partial legacy assignment snapshot (64 of 339 registered RTLs) with no dates,
actor or history, and it could not tell us the policy. CDB-05 is now answered.

## Decision

1. **Assigned-only access.** A Technician may see and work with only the client
   RTLs currently assigned to them, on every real route: Fleet (`Assigned RTLs`),
   RTL Detail, Network, Historical Events and the Technician dashboard.
2. **One current Technician per RTL.** An RTL may have many Technicians over
   time but only one open assignment; a Technician may hold many RTLs. Enforced
   by a PostgreSQL partial unique index on the open row, not only by code.
3. **Administrator-only assignment.** Only an Administrator assigns, reassigns
   or ends an assignment. The service checks the authenticated actor itself, in
   addition to the route policy and the callback check.
4. **History is retained.** Reassignment ends the old row and opens a new one in
   one transaction; the old row is never overwritten. Actor and time are
   recorded and audited (`RTL_ASSIGNMENT_CREATED` / `_ENDED` / `_REASSIGNED`).
5. **One shared UID scope.** `services/rtl_scope.py` is the only place that turns
   assignments into "which client UIDs may this caller access?". Fleet, Detail,
   Network, Events and the dashboard take that scope and apply it before/inside
   their source reads (Events inside the SQL). A structural test fails if
   another module reads assignments or a real-route callback branches on role.
   `None` (unrestricted: Administrator, General User) is never conflated with an
   empty set (a Technician with no assignments) or with a denied scope.
6. **Unassigned RTLs** are an Administrator-only assignment pool. Being
   unassigned never grants anyone access. General User visibility is unchanged.
7. **Identity.** The assignment names the application user (`users.user_id`) and
   the client RTL UID (`device_list.device_uid`, no FK across databases;
   registration is validated against the read-only source at write time).
   `users.client_person_id` bridges an application user to a SQL Server
   `persons.person_id`; people are never matched by display name at
   authorization time. The synthetic `devices.device_id` is not an assignment
   identity and no device-id to RTL-UID mapping exists or is created.
8. **SQL Server stays READ_ONLY.** The workflow is application-owned
   (PostgreSQL) until a separately approved SQL Server migration/write gate.
   `technician_assignments` and `techmician_device_list` are never written.
9. **Legacy transition.** The 64 currently registered legacy assignments are
   adopted once, by an explicit preview-first command (never at start-up), as
   provenance `LEGACY_IMPORT`: no assigned date and no assigned-by, with the
   import time kept separately (a CHECK constraint forbids inventing them). The
   four historical/unregistered UIDs are not imported. A conflict stops the
   import; nothing is overwritten and an assignment an Administrator ended is
   not resurrected. The legacy table is transitional evidence, not authority.
10. **Future Program RTL scope (recorded only).** A Technician may program an
    RTL only if it is assigned to them. Programming is not implemented here and
    assignment grants no command capability.

## Consequences

- The route gate now admits every role to the real-RTL routes; the scope, not the
  role table, decides which UIDs a Technician reaches. An out-of-scope, an
  unregistered and an unassigned UID all produce the same forbidden answer and
  no source read (no existence oracle).
- The synthetic Technician "Devices" route is denied to every role and the
  Technician lands on the factual dashboard. The synthetic Command Center is no
  longer reachable from production routing; its code is legacy cleanup debt.
- The older `user_device_assignments` table (synthetic `device_id`) is unchanged
  and unrelated; it is not a second copy of this concept but a different
  identity space, and retires with the synthetic model.
- A mandatory reassignment reason was not part of the approved policy and is not
  built. Ending an assignment exists in the service; the UI offers assign,
  reassign and history only.
