# Active Gate

Status: **CLOSED / PASS**
Date: 2026-09-17
Gate: NONE
Commit/push permission: **GRANTED.**

## Task

Align BR016 with the Functional Specification: the RTL Master automatically
disables message forwarding at 18:30 daily. Remove the dashboard's active
scheduler and unsupported Administrator same-day override without changing
manual message-forwarding controls or their authorization.

## Relevant files

- `services/message_forwarding_service.py`
- `services/authorization.py`
- `callbacks/device_manage.py`
- `components/device_manage_drawer.py`
- `app.py`
- `repositories/plant_monitoring_repository.py`
- `alembic/versions/010_forwarding_auto_disable.py`
- `tests/test_br016_ownership.py`
- `tests/test_authorization.py`
- `tests/test_action_guard.py`
- `docs/RTL_FUNCTIONAL_SPEC_COMPLETION_TRACKER.md`
- `docs/context/CURRENT_STATE.md`

## Non-goals (explicit)

- No real SMS or RTL Master transport/API is added or modified.
- The retained migration table is compatibility-only and is not a client
  production feature.

## Next implementation gate: NONE

## Known ambiguities

None.

## FS-BR016-1 — CLOSED / PASS

Implementation: `eadf85415dd49aa70a0673bd190bd8b6fa3a33c5`.

BR016 now has its Functional Specification ownership boundary: the dashboard
does not schedule, execute, or offer an Administrator override for the daily
18:30 forwarding cutoff. That operation is explicitly RTL Master-owned. The
manual per-user forwarding preference, its Administrator/assigned-Technician
authorization, and General User denial remain unchanged. Legacy migration 010
table data is retained only for backwards-compatible schemas and has no active
product caller.

Verification: 192 focused forwarding/authorization/migration tests passed;
the full non-DB suite exited 0; `python scripts/build_context_pack.py --check`
was clean; and browser verification passed for Administrator and an assigned
Technician. Both roles retain the manual forwarding drawer; no Administrator
auto-disable/override UI remains, and the drawer names the RTL Master as the
BR016 cutoff owner. Real RTL Master execution remains a separate external
integration item.

## FS-SCOPE-1 — CLOSED / PASS

`ROUTE_POLICY` now limits General User to monitoring hierarchy routes and
`/reports`; `CAPABILITY_POLICY[EXPORT_DATA]` remains available and
`ACTION_POLICY` continues to deny General Users every operational action.
The sidebar derives its links from that same route policy, while the router
uses the current trusted identity to refuse direct operational URLs before
rendering data.

Verification: 297 focused authorization/navigation/action tests passed;
`python -m pytest -m "not db"` passed 3,083 tests (706 deselected); General
User desktop browser verification passed at 1440×900, including direct URL
refusal for Notifications, Command Center and Command Center Locations.

## FS-TRACKER-ADOPT-1 — CLOSED / PASS

The root tracker was moved to `docs/` and adopted as the RTL functionality
requirements-completion authority. `SOURCE_AUTHORITY.md` now directs RTL
requirement questions to the Functional Specification/tracker, not older
PADs or internal material. Validation corrected BR012 and ACTIVE-01 from
`MISSING` to `PARTIAL`: the repository already has a tested local startup to
`rtl_active_state` projection, but no real RTL Master source or
synchronization. General User Notifications/Command Center access and
application-owned BR016 auto-disable remain `CONFLICT`.

Verification: focused context-pack tests passed; the context-pack structural
check and `git diff --check` were clean. No application/runtime code changed.

## DEV-READINGS-RESET-1 — CLOSED / PASS

Date: 2026-09-16. Baseline: `main` @ `365c871b04a185240b7b6bd670d1ea59977f40a6`
(the LOCAL-DB-CATCHUP-3 commit).

### Pre-flight

- DB target reconfirmed local/dev: `localhost:5436`, db `powerplant_demo`,
  schema `plant_monitoring` (via `config.settings`, no credentials
  printed); `docker ps` confirmed `plant_monitoring_postgres` running.
  Pre-reset `alembic current` = `014_alarm_ack_fk_no_action`.
- Pre-reset row-count snapshot taken for every non-readings table
  (`plants` 30, `transformers` 71, `devices` 120, `device_events` 13,
  `user_device_assignments` 97, `rtl_active_state` 2,
  `rtl_programming_requests` 1, `rtl_commands` 1, `audit_log` 6,
  `message_forwarding` 1, `users` 7, and the three config tables at 0)
  — used as the preservation baseline below. Pre-reset `readings` =
  1,831,680 (drifted from live-simulator activity across past sessions).

### Reset

- `python -m db.seed_plant_monitoring --reset` ran to completion: "Reset:
  1,831,680 reading(s) replaced. Hierarchy and operational history
  (events, assignments, active state, requests) preserved." Then reseeded
  "1,441 (30 days, 30-min intervals)" timestamps,
  `2026-08-17T09:30:00+00:00` to `2026-09-16T09:30:00+00:00` (current, per
  ADR-009's injectable-reference-time convention), and loaded
  "1,383,360 rows... in 60.3s" — the canonical 120 devices × 1,441
  timestamps × 8 metrics count.
- Post-reset row-count comparison: every non-readings table listed above
  identical to its pre-reset value, including the previously-acknowledged
  `device_events` row (event 14, `acknowledged_by_user_id` 103) unchanged.
  `readings` = 1,383,360 (canonical).
- `alembic current` = `014_alarm_ack_fk_no_action` — unchanged by the
  data-only reset.

### Verification

- `tests/test_seed_integrity.py` + `tests/test_plant_monitoring_repository.py::
  TestRangeQueries` — **25 passed** (the 6 previously-failing tests from
  LOCAL-DB-CATCHUP-2/3 are among them, now green).
- `python -m pytest -q` (full suite, DB included, against the real reset
  DB) — **all passed**, exit 0, zero failures.
- `git diff --check` — clean (no application code touched).
  `python scripts/build_context_pack.py --check` — CLEAN at gate open.

### Known ambiguity

None.

## LOCAL-DB-CATCHUP-3 — CLOSED / PASS

Date: 2026-09-16. Baseline: `main` @ `606fb05cb1c8670c74a5a78fc16dc4ae93786bc4`
(the ALARM-ACK-FK-014 commit).

### Pre-flight

- DB target reconfirmed local/dev: `localhost:5436`, db `powerplant_demo`,
  schema `plant_monitoring` (via `config.settings`, no credentials
  printed); `docker ps` confirmed `plant_monitoring_postgres` running.
  Pre-upgrade `alembic current` = `013_alarm_acknowledgement`.

### Migration

- `alembic upgrade head` succeeded: `013_alarm_acknowledgement` →
  `014_alarm_ack_fk_no_action`.
- Post-upgrade `alembic current` = `alembic heads` =
  `014_alarm_ack_fk_no_action`.
- Data preserved across the upgrade (row counts identical before/after):
  `plants` 30, `transformers` 71, `devices` 120, `readings` 1,831,680,
  `device_events` 13, `users` 7 — including the previously-acknowledged
  `device_events` row (event 14, `acknowledged_by_user_id` 103, from
  LOCAL-DB-CATCHUP-2's browser verification), byte-for-byte unchanged.
- `fk_device_events_acknowledged_by_user` delete_rule confirmed `NO ACTION`
  directly against `information_schema`; every FK delete_rule in the
  schema is now `{'NO ACTION'}` (was `{'NO ACTION', 'SET NULL'}` before
  this upgrade).
- `ck_device_events_acknowledgement_pair` CHECK confirmed still present and
  unchanged: `(acknowledged_at IS NULL) = (acknowledged_by_user_id IS NULL)`.

### Verification

- `tests/test_seed_reset_contract.py::TestPurgeOrderAgainstTheLiveSchema`
  (both tests, including `test_no_foreign_key_relies_on_cascade`) — **2
  passed** (previously 1 failed, per ALARM-ACK-FK-014's flagged
  known-ambiguity — now resolved).
- Focused + regression, one invocation:
  `tests/test_migration_alarm_ack_fk_no_action.py` +
  `tests/test_migration_alarm_acknowledgement.py` +
  `tests/test_alarm_acknowledgement_db.py` +
  `tests/test_seed_reset_contract.py` +
  `tests/test_programming_activity.py` +
  `tests/test_rtl_command_dispatch.py` — **86 passed, 0 failed** (up from
  85/86 before this upgrade).
- `python -m pytest -m "not db"` (full non-DB suite) — **all passed**,
  exit 0.
- `git diff --check` — clean. `python scripts/build_context_pack.py --check`
  — CLEAN at gate open.

### Known ambiguity

None.

## ALARM-ACK-FK-014 — CLOSED / PASS

Date: 2026-09-16. Baseline: `main` @ `4203de9e458e73476e0d16fe355c6c7d41191e3e`
(the LOCAL-DB-CATCHUP-2 commit).

### What was built

- `alembic/versions/014_alarm_ack_fk_no_action.py` — drops and recreates
  `fk_device_events_acknowledged_by_user` with `ondelete="NO ACTION"`
  (previously `"SET NULL"`, from migration 013). `downgrade()` restores
  `SET NULL` for exact reversibility. Migration 013 is untouched; the
  acknowledgement-pair CHECK it created is unaffected.
- `tests/test_migration_alarm_ack_fk_no_action.py` (new) — FK `delete_rule`
  is `NO ACTION` (queried directly from `information_schema`/
  `referential_constraints` against `isolated_schema`); the acknowledgement
  pair CHECK still rejects an incomplete pair and accepts a complete one;
  deleting a `users` row referenced by `device_events.acknowledged_by_user_id`
  is refused (`IntegrityError`), proving the FK no longer silently
  `SET NULL`s on delete.

### Verification

- `python -m alembic heads` — `014_alarm_ack_fk_no_action` (sole head;
  script-only check, no DB connection).
- Focused: `tests/test_migration_alarm_ack_fk_no_action.py` (4) +
  `tests/test_migration_alarm_acknowledgement.py` (4) +
  `tests/test_alarm_acknowledgement_db.py` (5) — **13 passed**.
- Regression, run together with the above plus
  `tests/test_seed_reset_contract.py` + `tests/test_programming_activity.py`
  + `tests/test_rtl_command_dispatch.py` — **85 passed, 1 failed** (the
  live-schema test discussed in "Known ambiguities" above; expected and
  accepted, not a new defect).
- `python -m pytest -m "not db"` (full non-DB suite) — **all passed**,
  exit 0.
- `git diff --check` — clean. `python scripts/build_context_pack.py --check`
  — CLEAN at gate open.
- Real dev Postgres remains at `013_alarm_acknowledgement` — deliberately
  not upgraded, per this gate's explicit instruction.

### Known ambiguity

None beyond the live-schema test discussed above, which was surfaced to
the user before proceeding rather than resolved unilaterally.

## LOCAL-DB-CATCHUP-2 note (2026-09-16, fully resolved by ALARM-ACK-FK-014 + LOCAL-DB-CATCHUP-3)

LOCAL-DB-CATCHUP-2's flagged defect ("`fk_device_events_acknowledged_by_user`
uses `SET NULL`, conflicting with `test_seed_reset_contract.py`'s
invariant") was fixed at the migration-script level by ALARM-ACK-FK-014's
migration 014, then actually applied to the real local dev database by
LOCAL-DB-CATCHUP-3 (above) — `test_no_foreign_key_relies_on_cascade` now
passes against the live schema. Fully closed; no residual action needed.
LOCAL-DB-CATCHUP-2's own historical record (below) is otherwise unchanged
and still accurate as a record of what that gate did.

**TECH-WORKSPACE-MERGE-1 note (2026-09-11):** `tech-workspace-1`
(TECH-WORKSPACE-1, closed on that branch 2026-09-10) has been merged into
`main` by this gate. Its own copy of this file had rewritten this header and
the `## Next implementation gate:` declaration to `TECH-WORKSPACE-1` purely
so its isolated CTX-GUARD-1 check would pass on that branch — its own note
said explicitly not to carry that rename onto `main`. That rename was
reverted as part of this merge; TECH-WORKSPACE-1's verified content is
preserved below as its own closed, historical section.

**CLIENT-PC-SYNC-3 note (2026-09-11):** CLIENT-SYNC-3 curated
TECH-WORKSPACE-1 to the client delivery branch, moving it from `3f21c3a` to
`983c171` — one milestone past what CLIENT-PC-SYNC-2 was queued against.
CLIENT-PC-SYNC-2 is therefore recorded as superseded before execution (it
was never started) rather than completed; CLIENT-PC-SYNC-3 below carries
the identical non-destructive backup/migrate/smoke procedure re-targeted at
the current milestone, with Technician "My RTLs" added to the browser-smoke
checklist.

## LOCAL-DB-CATCHUP-2 — CLOSED / PASS (defect flagged, not fixed)

Date: 2026-09-16. Baseline: `main` @ `1245b48bb79a029be65dd248f59e30a0cdeac222`.
Purpose: bring the real local development PostgreSQL database to Alembic
head and verify recent backend/UI tranches against live data. No
application code was changed by this gate.

### Pre-flight

- DB target confirmed local/dev, not client/Eskom/production: configured
  `POSTGRES_HOST=localhost`, `POSTGRES_PORT=5436`, db `powerplant_demo`,
  schema `plant_monitoring` (via `config.settings.database`/`monitoring`,
  no credentials printed); `docker ps` confirmed the running container is
  `plant_monitoring_postgres` (image `postgres:16`, port `5436`), matching
  prior session records of the real local dev environment. Pre-upgrade
  `alembic current` = `012_vibration_contract_answers`.

### Migration

- `alembic upgrade head` succeeded: `012_vibration_contract_answers` →
  `013_alarm_acknowledgement`.
- Post-upgrade `alembic current` = `013_alarm_acknowledgement`; `alembic
  heads` = `013_alarm_acknowledgement` (sole head).
- Schema readability and data preservation confirmed by direct row-count
  query before/after: `plants` 30, `transformers` 71, `devices` 120,
  `readings` 1,831,680, `device_events` 13, `users` 7 — all unchanged
  across the upgrade.
- New columns/constraint verified directly against `information_schema`/
  `pg_constraint`: `device_events.acknowledged_at`
  (`timestamp with time zone`, nullable),
  `device_events.acknowledged_by_user_id` (`integer`, nullable),
  `fk_device_events_acknowledged_by_user` (`ON DELETE SET NULL` to
  `users.user_id`), and `ck_device_events_acknowledgement_pair`
  (`(acknowledged_at IS NULL) = (acknowledged_by_user_id IS NULL)`) —
  exactly as the migration defines them.

### DB regression / full-suite results

- Gate-named focused/affected tests (`test_migration_alarm_acknowledgement.py`,
  `test_alarm_acknowledgement_db.py`, `test_programming_activity.py`,
  `test_rtl_command_dispatch.py`) — **61 passed**.
- `python -m pytest -m "not db" -v` (full non-DB suite) — **all passed**.
- `python -m pytest -q` (full suite, DB included, against the real upgraded
  dev DB) — 3761 collected, **7 failed**, rest passed. See "Known
  ambiguities / defect found" above for the breakdown: 1 real
  pre-existing FK/test-invariant conflict (not fixed, reported), 6
  pre-existing live-simulator data-drift failures (not a defect, seed data
  is stale relative to the original 30-day contract).

### Browser verification (Administrator + Technician, real upgraded data)

Dash app run locally (`python app.py`) against the upgraded DB; verified
via Playwright (Chrome extension was not connected this session):

- **Alarm acknowledgement**: acknowledged a real `power_down` device event
  (`plant-01-t1-d1`, event 14) from the Notification Center. DB confirmed
  `acknowledged_at`/`acknowledged_by_user_id` written, `audit_log` gained
  one atomic `ALARM_ACKNOWLEDGED` row (old/new snapshot, actor); UI updated
  to "Acknowledged · 2026-09-16 09:05 UTC" and the row's action disappeared.
- **Compact device audit history**: the device page's "Command & audit
  history" section showed the new "Alarm Acknowledged · admin · 16 Sep 2026
  09:05 UTC" entry immediately.
- **Program RTL lifecycle rail**: recorded a real Program RTL request
  against `plant-01-t1-d1`; UI showed the lifecycle rail (Queued (current) →
  Sent → Acknowledged → Succeeded), "Awaiting device integration" execution
  state, and a matching `RTL Program Requested` audit entry — command
  correctly stayed `queued` (fail-closed; no simulator was invoked).
- **Report export ("Preparing" → completion)**: generated and downloaded a
  Maximum Temperature CSV against real data (71 transformers); UI showed
  "Exported 71 row(s)" on completion and the file downloaded successfully.
- **Technician assignment saving**: assigned `demo.tech02` to previously
  unassigned device 29064 via the admin Assign drawer; UI showed
  "Assignment saved. demo.tech02 is assigned to this RTL..." confirmation.
- **Device registration inline identifier guidance**: typing an RTL UID on
  `/admin/devices/new` produced live inline feedback ("Meets the device
  code format (10 characters or fewer)").
- **Technician login/scoping**: `demo.tech01` logged in successfully and
  saw a scoped "My RTLs" view (16 plants, 24 assigned RTLs) with no
  Administrator-only nav items — role scoping intact post-upgrade.
- **Plant zero-inventory / Transformer zero-RTL empty states**: not
  reproducible — all 30 plants and 71 transformers have real assigned
  devices in the upgraded dev data; no empty-state path was exercised.
- One generic, pre-existing React dev-mode console warning ("changing an
  uncontrolled input... to be controlled") appeared on multiple pages; not
  related to this gate's migration or verified features, not investigated
  further (Dash's own debug overlay, `DASH_DEBUG=true`).

### Verification

- `git diff --check` — clean (docs/context only).
- `python scripts/build_context_pack.py --check` — CLEAN at gate open;
  full pack run at close (see below).

### Commit/push

Only this documentation/context closure is committed
(`docs(context): verify local database catchup`); no application code
changed. Pushed to `origin/main` per this gate's own explicit instruction.

## C08-BASELINE-1 — CLOSED / DEVELOPMENT BASELINES RECORDED

Documentation-only gate. **The values recorded below for C-08, C-15, C-04,
C-01, and C-02 are development baselines approved by the development
team/user so implementation can proceed — they are NOT confirmed
Eskom/client answers unless repository evidence proves otherwise.** C-07
remains genuinely on hold pending the client (unchanged, not a baseline).
C-05, C-06, and the Azure/private-APN/Entra ID family remain
Eskom-controlled/external, reconfirmed as still unanswered. Recorded in
`REQ-3I_Clarification_Register.md` (each item's own entry, an added §4 rule
distinguishing a development baseline from a client answer, and an updated
§5 ranking), `docs/context/CLIENT_QUESTIONS.md` ("Development Baselines
Set" section), and `docs/context/PROJECT_LEDGER.md` (§1, §3, §8, §9, §10).
While reconciling `PROJECT_LEDGER.md` against `REQ-3I`'s numbering (this
repository's authoritative clarification register, per
`docs/context/SOURCE_AUTHORITY.md` and the POWER-MASTER-PLAN-1 precedent),
three pre-existing ID mislabels were found and corrected there: the
high-temperature threshold was cited as `C-15` (that ID actually names the
separate Max Temperature reporting period; the threshold is `C-01`); report
format was cited as `C-10` (that ID actually names the separate notification
acknowledgement/retention question; format is `C-04`); and the vibration
open-question count was stated as 16 where direct inspection of
`docs/VIBRATION_METRIC_CONTRACT_TBD.md` shows 14. See
`docs/context/PROJECT_LEDGER.md` §8's note for the full correction record.
No application code touched.

**Second correction (2026-09-07, VIB-CONFIG-1 open):** the "14" above was
itself a miscount, not a change to the file — `docs/VIBRATION_METRIC_CONTRACT_TBD.md`'s
"Unknown / Required from Client/Backend" table has always had 15 rows
(the file has one commit in its entire history, `553d142`). Every tracked
reference to "14 [open] questions" for vibration is corrected to 15 as
part of this gate.

## Development baselines set (2026-09-06, pending client confirmation)

- **C-08 — DEVELOPMENT BASELINE SET.** The RTL Application (this
  repository) will own BR016's daily auto-disable — not the RTL Master.
  Default cutoff: 18:30 Africa/Johannesburg. An Administrator may set a
  temporary, same-day-only override of the cutoff with a mandatory reason;
  the override expires automatically at end of day and the default 18:30
  cutoff resumes automatically the next day. Every override change and
  every automatic disable action must be audited. This is an internal
  decision so implementation can proceed, not a confirmed client answer.
  **Still open, not decided by this round and not to be invented:** which
  users/RTLs the disable applies to, and whether an override is fleet-wide
  or per-user/per-RTL.
- **C-15 — DEVELOPMENT BASELINE SET.** Maximum Temperature report period:
  rolling 30 days by default, plus a custom date range. The period used
  must be shown on the report and its export.
- **C-04 — DEVELOPMENT BASELINE SET (format only).** Production report
  format is PDF + CSV. Native XLSX is not required. Retention/history
  remains open.
- **C-01 — DEVELOPMENT BASELINE SET (framework only).** Warning/critical
  temperature thresholds must be administrator-configurable, never
  permanently hardcoded, with all changes audited. Actual Eskom threshold
  values remain unconfirmed.
- **C-02 — DEVELOPMENT BASELINE SET (framework only).** Vibration must be a
  configurable framework, not hardcoded. Production sensor semantics/values
  remain unconfirmed (15 open questions in
  `docs/VIBRATION_METRIC_CONTRACT_TBD.md` — corrected 2026-09-07, direct
  count; previously miscounted as 14).
- **C-07 — HOLD.** Explicitly pending client hierarchy clarification; no
  mapping supplied. This one is genuinely waiting on the client, not a
  development baseline.
- **C-05, C-06, and the Azure / private-APN / Entra ID family — reconfirmed
  as Eskom-controlled/external.** Not answered this round; not expected to
  become application-side work.

All five baselines above are pending formal client confirmation. Treat them
as the working assumption for implementation, not as settled requirements —
if the client's eventual answer differs, the baseline and everything built
against it must be revisited.

## C08-AUTO-DISABLE-1 — CLOSED / PUSHED / REMOTE-VERIFIED

Branch: `main`, baseline `d10c566ef5e400d9163fdba2413580f3ca4517d9`.
Commit: `d10c566ef5e400d9163fdba2413580f3ca4517d9` — subject "feat(forwarding):
add scheduled auto-disable (C08-AUTO-DISABLE-1)". Pushed to `origin/main`;
local `HEAD`, `origin/main`, and `git ls-remote origin refs/heads/main` all
verified to match this SHA. Scheduler, override, and audit code now exist
on `main`, matching the scope and architecture decision below. This section
originally existed as the pre-implementation baseline (retained below);
what follows records what was actually built and independently re-verified
before commit.

### What was built

- `alembic/versions/010_forwarding_auto_disable.py` — migration adding the
  singleton `forwarding_auto_disable_override` table (mandatory reason,
  actor, day scope).
- `services/forwarding_auto_disable_service.py` — `apply_auto_disable(now)`:
  idempotent bulk-disable of every currently-enabled `message_forwarding`
  user when the effective cutoff (default or active override) is reached;
  a real state transition is audited, a repeat call for the same day is a
  silent no-op. Override set/change/clear also lives here: a mandatory
  reason is enforced, an identical re-set is a no-op, a real change (cutoff
  time or reason) is audited, and clearing an unset override is a no-op.
  Audit writes follow the existing `services/audit_service.py`
  mutation+audit-in-one-transaction pattern; a failed audit rolls back the
  override write or the bulk disable in the same transaction.
- `scripts/run_forwarding_auto_disable.py` — the standalone, externally
  invoked entry point (`python -m scripts.run_forwarding_auto_disable`),
  matching decision point 2 below: not embedded in any Dash/Gunicorn worker.
  The actual production trigger (cron, Railway scheduled job, etc.) is left
  deployment-configurable, per decision point 4 — this gate does not pick
  one.
- `config/forwarding_schedule.py` — `Africa/Johannesburg` via stdlib
  `zoneinfo`; default cutoff `time(18, 30)`.
- `components/auto_disable_override_panel.py` + `callbacks/forwarding_schedule.py`
  — minimal Administrator-only panel to set/clear the same-day override with
  a mandatory reason field, wired into `pages/plants_overview.py` /
  `app.py`.
- `repositories/plant_monitoring_repository.py` — override/bulk-disable
  persistence (largest diff of the tranche, 212 lines).
- `config/audit.py` — new audit action types for override set/change/clear
  and automatic disable.
- `services/authorization.py` — capability gate for the override panel
  (Administrator-only, matching the C-08 baseline).
- `requirements.txt` — `tzdata==2026.3` pinned explicitly and commented: the
  stdlib `zoneinfo` call needs an IANA tz database, which Windows dev
  machines don't ship natively (this environment only had one incidentally,
  via pandas' own optional dependency); Linux/Railway containers carry one
  at the OS level regardless. No scheduler library was added — the stdlib
  `zoneinfo` plus a plain standalone script were sufficient, per AGENTS.md's
  dependency-justification rule.
- Tests: `tests/test_forwarding_auto_disable.py` (32) +
  `tests/test_migration_forwarding_auto_disable.py` (6) — new, 38 total.
  `tests/test_device_event_service.py`, `tests/test_equipment_selector.py`,
  `tests/test_migration_foundation.py` — modified for this tranche.

### Verification (re-run and confirmed this session, not taken on faith)

- Focused: `tests/test_forwarding_auto_disable.py` +
  `tests/test_migration_forwarding_auto_disable.py` — **38 passed**, exit 0.
- Forwarding/audit-adjacent regression, run together in one invocation:
  `tests/test_audit_wiring.py` + `tests/test_message_forwarding.py` +
  `tests/test_migration_audit_log.py` + `tests/test_device_event_service.py`
  + `tests/test_equipment_selector.py` + `tests/test_migration_foundation.py`
  — **100 passed**, exit 0. (A prior informal count of "74" for this
  regression set could not be reproduced from any subset of the modified/
  related test files and is superseded by this verified figure.)
- Full suite: `python -m pytest -q` — **all passed, exit 0**, no failures.
- `python -m alembic heads` — `010_forwarding_auto_disable` is the sole
  head.
- `git diff --check` — clean.
- `git status --short` — matches the expected modified/new file set above,
  plus untracked `debug.log` (excluded from any commit).
- Real dev Postgres (`plant_monitoring_postgres`, port 5436) was down at the
  start of this verification pass (Docker Desktop was not running) and was
  started fresh to run the above — none of it was already "left running"
  from a prior session. `python -m alembic current` on that real dev DB
  reports **`007_audit_log`** — three migrations behind code (`010`). This
  is expected, not a defect in this gate: the test suite exercises migration
  010 only via the `isolated_schema` fixture (AGENTS.md testing rules), never
  against the real `plant_monitoring` schema. **Still true after this gate's
  push**: the real dev DB was deliberately left at `007` — commit and push
  do not run migrations against it. Before demonstrating the override panel
  locally against real dev data, run `alembic upgrade head` non-destructively,
  as its own deliberate step, environment checked first.
- Push verification: after `git push origin main`, `git rev-parse HEAD`,
  `git rev-parse origin/main`, and `git ls-remote origin refs/heads/main`
  all returned `d10c566ef5e400d9163fdba2413580f3ca4517d9`.

### Known ambiguity / open items carried forward

- The three "explicitly not answered" items below (user/RTL scope, override
  fleet-wide-vs-scoped, notification-on-disable) remain open and were not
  invented by this implementation.
- The "Scheduler architecture decision" below was recorded as an internal
  decision in this gate file at gate-open (2026-09-06), not in ADR form.
  RTL-IF-4's equivalent architecture decision (delivery-boundary separation)
  was written up as `ADR-020`. Whether this decision should likewise become
  its own ADR, or stay as gate-file prose, was not decided in this session
  and is flagged rather than resolved unilaterally.
- **Commit/push permission: GRANTED and exercised 2026-09-07.** Two decisions made by the
  user closing this gate: (1) no ADR needed — the scheduler choice is
  localized and reversible, unlike an RTL-IF-scale architectural boundary,
  and is already recorded here and in `PROJECT_LEDGER.md`; ADRs stay
  reserved for boundaries at that scale. (2) No independent Codex
  second-party review needed for this gate — this session's own re-run of
  focused/regression/full-suite tests, migration-head check, and pack/diff
  validation was accepted as sufficient; Codex review is reserved for
  high-risk security/integration changes or when results conflict. The
  earlier "74 passed" regression estimate is superseded by the verified
  **100 passed** figure above, which is authoritative.

---

## C08-AUTO-DISABLE-1 — original pre-implementation baseline (2026-09-06)

Documentation only at this point — no scheduler, override, or audit code has
been written yet. This section exists so a future implementation session has
the exact confirmed baseline without re-deriving it.

### Scope (from the C-08 development baseline above)

1. A daily scheduled job, owned by this application, that disables message
   forwarding (the existing `message_forwarding` per-user preference,
   `services/message_forwarding_service.py`) at a configurable cutoff time,
   default **18:30 Africa/Johannesburg**.
2. An Administrator-only capability to set a **temporary, same-day-only**
   override of that cutoff time, with a **mandatory reason** captured.
3. The override **expires automatically** at the end of the day it was set
   for; the default 18:30 cutoff resumes automatically the next day with no
   administrator action required.
4. **Every** override change and **every** automatic-disable action must
   write an audit row (pattern: `services/audit_service.py`, as used by
   forwarding/programming/deactivation/ingestion).

### Explicitly not answered — do not invent

- Which users/RTLs are affected: all users with forwarding currently
  enabled, or scoped by technician/RTL assignment?
- Whether an override applies fleet-wide or is scoped per-user/per-RTL.
- Whether the disable also needs to *notify* affected users (BR016 itself
  only asks for the disable, not a notification about it).

### Why this does not depend on C-05

The auto-disable action only needs to flip the existing, already-persisted
`message_forwarding.enabled` flag to `false` in this application's own
database — it requires no message transport, MQTT, or SMS gateway. It is the
first candidate application-engineering tranche unblocked since
`REQ-3I_Clarification_Register.md` was established. **Actual outbound
message delivery** (what "message forwarding" sends once enabled) remains
blocked on C-05, unchanged.

### Scheduler architecture decision (2026-09-06)

No background-worker/scheduler infrastructure exists anywhere in this
codebase yet (`REQ-1B_Implementation_Gap_Matrix.md` §15;
`PROJECT_LEDGER.md` §8/§10). This is an internal architecture decision and
does not require Eskom infrastructure access or client input — recorded now
so implementation does not have to re-derive it:

1. **An idempotent application service** implements "disable forwarding
   when due" — e.g. `apply_auto_disable(now)` in
   `services/message_forwarding_service.py` or a sibling module. Calling it
   twice for the same cutoff must not double-audit or error; it checks
   current state before acting, the same pattern already used by
   `services/audit_service.py`'s mutation+audit callers.
2. **A separately invokable scheduled command/process** calls that service
   — a standalone entry point (e.g. a small script or CLI command), not
   logic embedded inside a request/callback handler.
3. **No timer/background scheduler embedded in each Dash/Gunicorn worker.**
   A per-worker timer would fire once per worker process under multiple
   Gunicorn workers, causing duplicate/racing auto-disable attempts. The
   idempotent service in (1) protects against this if it ever happens
   anyway, but the design should not rely on that as the only safeguard.
4. **The actual production scheduling mechanism remains
   deployment-configurable** — cron, a Railway scheduled job, APScheduler
   run from a single designated process, or similar. Whoever opens this
   gate for implementation must choose and justify one appropriate to this
   stack (Python/Dash/Flask, single process, Railway deployment — AGENTS.md
   §Stack), per AGENTS.md's dependency-justification rule ("Before adding a
   dependency, explain why the existing stack cannot reasonably solve the
   requirement"). This decision record does not pick that mechanism itself.

### Sole remaining leading blocker for other RTL-IF/production tranches

- **C-05** — transport/producer/channel contract. Confirmed 2026-09-06 as
  Eskom-controlled/external; still unanswered. Remains the sole leading gate
  for physical programming execution, forwarding delivery, and all
  producer-dependent work. See `REQ-3I_Clarification_Register.md` §5.

## REPORT-MAXTEMP-1 — CLOSED / PUSHED / REMOTE-VERIFIED

Branch: `main`, baseline `d10c566ef5e400d9163fdba2413580f3ca4517d9` (the
C08-AUTO-DISABLE-1 commit). Commit: `95bdfa59487b0c171e9d7c07f96a6fa32d0bd81d`
— subject "feat(reports): implement maximum temperature report
(REPORT-MAXTEMP-1)". Pushed to `origin/main`; local `HEAD`, `origin/main`,
and `git ls-remote origin refs/heads/main` all verified to match this SHA.

Date: 2026-09-07. Maximum Temperature is now a real, data-backed report
(replacing its Prototype Only result), built against the C-15 development
baseline. Follows the same service → repository → callback pattern as
Installed RTLs (REPORT-2) and RTL Alarms 30 Days (REPORT-3).

### What was built

- `repositories/plant_monitoring_repository.py` —
  `max_temperature_report_rows`: one row per transformer, its single
  highest temperature reading across all its devices within `[since,
  until]`. Deterministic tie-break when a maximum is shared: earliest
  `reading_ts`, then `device_id`, then the `readings.id` surrogate key —
  never left to query-plan order. Two independent scope gates: an outer
  EXISTS hides a transformer entirely when the caller has no visible
  device on it at all (matches `list_transformers`'s convention — no bare
  transformer code leaks to an unassigned Technician); the LATERAL itself
  additionally restricts which of that transformer's OWN devices may
  supply the winning reading, so a transformer with a scope-mixed device
  set can never have an out-of-scope device's reading win. "Date
  Installed" is `devices.installed_at` of the SPECIFIC device that
  produced the winning reading — no transformer-level installation date
  exists anywhere in this schema, so nothing is synthesized; blank when
  that device has none on record.
- `services/report_service.py` — `MaxTemperatureRow`,
  `resolve_max_temperature_period` (rolling 30-day default ending at an
  injectable reference time, mirroring `ALARM_REPORT_WINDOW`'s shape, or
  the caller's explicit custom `[since, until]` verbatim), and
  `max_temperature_rows`. One shared resolver used by the preview path so
  the period displayed to the user can never diverge from the period
  actually queried.
- `callbacks/report_center.py` / `pages/report_center.py` — real table
  render (`_build_max_temperature_table`), a `Period used:` line above
  the table (`_format_report_period`) — presentation only, the column
  contract in `config/reports.py` is unchanged — and a real "Date Range"
  control exposing exactly two options for this report: `30d (default)`
  and `Custom`. No `24h`/`7d` — those belong to other reports' periods,
  not this baseline. Stale "prototype" wording in the page banner and
  honesty notice corrected to describe the real data source.
- No CSV/PDF export was added for this report — deliberately deferred to
  `REPORT-EXPORT-1`, a separate gate. `EXPORTABLE_REPORTS` is unchanged.
- OU/Zone/Sector/CNC/Feeder Name stay `None` in the domain row, same R2-D2
  convention as the other two reports — C-07 remains HOLD, not invented.

### Verification

- Focused: `tests/test_report_max_temperature.py` (15) +
  `tests/test_report_max_temperature_db.py` (15) — **30 passed**.
- Report-center regression, run together in one invocation:
  `tests/test_report_center.py` + `tests/test_report_installed_rtls.py` +
  `tests/test_rtl_alarms_report.py` + `tests/test_rtl_alarms_report_db.py`
  + `tests/test_report_export.py` + `tests/test_report_export_db.py` +
  `tests/test_report_export_authorization.py` — all passed (one pre-
  existing test file needed a fix, see Known ambiguity below, not a defect
  in this gate's own code).
- Full suite: `python -m pytest -q` — all passed, exit 0.
- `git diff --check` — clean. `python scripts/build_context_pack.py
  --check` — CLEAN.
- Real dev Postgres remains at migration `007` — untouched; this gate adds
  no migration at all (no schema change was needed).
- Push verification: after `git push origin main`, `git rev-parse HEAD`,
  `git rev-parse origin/main`, and `git ls-remote origin refs/heads/main`
  all returned `95bdfa59487b0c171e9d7c07f96a6fa32d0bd81d`.

### Known ambiguity

- `tests/test_auth_harden_repair.py::TestReportScopeLabels` used
  `"max_temperature"` as a placeholder report key specifically because it
  used to fall through to `generate_report`'s generic scope-label
  fallback (back when Max Temperature was prototype-only). Now that it is
  a real, specially-handled report, that key would have hit the new
  branch and made an unmocked DB call. Fixed by pointing those 6 tests at
  a genuinely unhandled report key (`_UNHANDLED_REPORT_KEY`) — the same
  no-leak security property is still covered, now independent of which
  report types happen to be implemented. Not a defect introduced by this
  gate's own report code; a coupling in a prior gate's test that this
  gate's change exposed.
- No new authority conflict between `AGENTS.md`, `SOURCE_AUTHORITY.md`, or
  the C-15 baseline recorded above and the source files inspected.

## REPORT-EXPORT-1 — CLOSED / PUSHED / REMOTE-VERIFIED

Branch: `main`, baseline `95bdfa59487b0c171e9d7c07f96a6fa32d0bd81d` (the
REPORT-MAXTEMP-1 commit). Commit: `7969324f377a5fee52b74617e4f7a17c5678f4b5`
— subject "feat(reports): add PDF and maximum-temperature export". Pushed
to `origin/main`; local `HEAD`, `origin/main`, and
`git ls-remote origin refs/heads/main` all verified to match this SHA.

Date: 2026-09-07. All three real reports (Installed RTLs, RTL Alarms 30
Days, Maximum Temperature) now export as both CSV and PDF, per the C-04
development baseline — PDF + CSV, no native XLSX. **This is a development
baseline pending client confirmation, not an Eskom-confirmed production
format.** This section originally existed as the pre-implementation
pointer (a stale "CSV only... unchanged by this gate" draft was corrected
in-place before implementation started); what follows records what was
actually built and verified.

### What was built

- `services/report_export.py` — `ExportDocument` gained `period_text`
  (and its old, misleadingly-named `period_label` field was renamed to
  `scope_label` — it always held the scope description, never a time
  period). Two registered formatters: `format_csv` (unchanged output
  shape for Installed RTLs/RTL Alarms) and new `format_pdf`, built on
  fpdf2's high-level `Table`, which repeats column headers on every page
  it spans by default. `EXPORTABLE_REPORTS` now lists all three reports.
  New `max_temperature_document()` builder, matching the exact 9-column
  contract.
- **Maximum Temperature CSV** keeps the exact report header as row 1 —
  no metadata preamble, no fake "Period" column, a plain rectangular
  table identical in shape to the other two. Its resolved period is
  identified only in its filename (`export_filename`'s `period_text`
  argument, gated to `report_key == "max_temperature"` — Installed RTLs'
  and RTL Alarms' filenames are byte-for-byte unchanged) and echoed in
  the export status panel in the UI ("Period exported: …"); neither is a
  change to the CSV bytes themselves.
- **PDF** visibly includes report title, scope, period, generated time,
  table headers, and paginated rows with repeated headers, for all three
  reports. Uses fpdf2's normal (compressed) output — no
  `pdf.compress = False`; this is production-shaped PDF behavior, not a
  development shortcut.
- `callbacks/report_center.py` — `_gather_export_rows` now returns
  `(rows, period_text)` and dispatches to the right document builder;
  Maximum Temperature's branch calls `_resolve_max_temperature_window` —
  the IDENTICAL helper the preview uses — so export and preview can never
  disagree about the window for the same form state (R4-D7). Authorization
  (`require_capability(EXPORT_DATA)`) still runs first, before any rows
  are fetched, for every report and every format.
- `pages/report_center.py` — a `report-export-format` control (CSV/PDF,
  default CSV) next to the Download button, which is relabeled
  "Download" (was "Download CSV", now format-neutral).
- `requirements.txt` — `fpdf2==2.7.9` pinned, with an inline comment
  explaining why (small, pure-Python, no system library dependency,
  built-in header-repeat/pagination) and why `reportlab` is NOT used even
  though it happens to already be present in this dev venv (arrived
  incidentally via an unrelated tool — the same trap the tzdata lesson,
  C08-AUTO-DISABLE-1, already caught once).
- OU/Zone/Sector/CNC/Feeder remain blank in every exported row, pending
  C-07 — not invented for export any more than for preview.

### Verification

- Focused: `tests/test_report_export.py` (40) +
  `tests/test_report_export_authorization.py` (18) +
  `tests/test_report_export_db.py` (6) — **64 passed**.
- Full report-center regression, run together in one invocation:
  `tests/test_report_center.py` + `tests/test_report_installed_rtls.py` +
  `tests/test_rtl_alarms_report.py` + `tests/test_rtl_alarms_report_db.py`
  + `tests/test_report_max_temperature.py` +
  `tests/test_report_max_temperature_db.py` +
  `tests/test_auth_harden_repair.py` (its export-callback helpers needed
  a signature-compat update for the callback's new parameters, not a
  defect) — all passed.
- Full suite: `python -m pytest -q` — all passed, exit 0.
- `git diff --check` — clean. `python scripts/build_context_pack.py
  --check` — CLEAN.
- Real dev Postgres remains at migration `007` — untouched; this gate adds
  no migration (no schema change was needed).
- Push verification: after `git push origin main`, `git rev-parse HEAD`,
  `git rev-parse origin/main`, and `git ls-remote origin refs/heads/main`
  all returned `7969324f377a5fee52b74617e4f7a17c5678f4b5`.

### Corrections applied during this gate (both requested by the user
### after the first implementation pass, before this closure)

1. The first pass gave Maximum Temperature's CSV a metadata preamble
   (Report/Scope/Period/Generated, then a blank line, before the real
   header). Removed entirely: CSV is now a plain rectangular table for
   every report, with no exceptions — the period lives in the filename
   and the UI status line only, never in the CSV body.
2. The first pass set `pdf.compress = False` for grep-ability in tests.
   Removed: `format_pdf` now uses fpdf2's normal compression. Because
   FlateDecode-compressed content streams cannot be substring-matched as
   raw text, the PDF tests were rewritten to verify formatter BEHAVIOR
   instead — structural framing (`%PDF-`/`%%EOF`, `/Type /Page` object
   counts, which are never inside a compressed stream) plus spies on
   `FPDF.cell`/`fpdf.table.Table.row` that capture the exact text/cells
   passed through while the real call still renders.

### Known ambiguity

None encountered beyond the two corrections above. No new authority
conflict between `AGENTS.md`, `SOURCE_AUTHORITY.md`, the C-04 baseline,
or the source files inspected.

## THRESH-CONFIG-1 — CLOSED / PUSHED / REMOTE-VERIFIED

Branch: `main`, baseline `7969324f377a5fee52b74617e4f7a17c5678f4b5` (the
REPORT-EXPORT-1 commit). Commit: `c83cf94b25cbd3ceec0e079938c355e221fe03b2`
— subject "feat(config): add temperature threshold management". Pushed to
`origin/main`; local `HEAD`, `origin/main`, and
`git ls-remote origin refs/heads/main` all verified to match this SHA.

Date: 2026-09-07. The C-01 framework — one global, Administrator-managed
temperature warning/critical threshold pair — is now real, against the
C-01 development baseline (`## Development baselines set` above):
administrator-configurable, never permanently hardcoded, every real
change audited. **Actual Eskom threshold values remain unconfirmed — this
gate builds the framework only, not production numbers.**
`MonitoringCondition` stays permanently `UNKNOWN` (AGENTS.md §Data rules):
nothing here reads the configuration back to evaluate a reading against
it, `high_temperature` event semantics remain inactive, and no
reading-to-alarm evaluation exists — all explicitly out of scope for this
gate.

### What was built

- `alembic/versions/011_temperature_threshold_config.py` — singleton
  table `temperature_threshold_config` (`id = 1`, CHECK-enforced — same
  shape as `forwarding_auto_disable_override`, migration 010).
  `warning_temperature_c`/`critical_temperature_c` `NUMERIC(12,3)` NOT
  NULL; unconfigured is ROW ABSENCE, never a row with placeholder or
  NULL-column values — no default is inserted, no Eskom value invented.
  A second CHECK, `warning_temperature_c < critical_temperature_c`,
  protects that relational invariant at the database level for any
  future caller or direct write, not only the service.
- `services/temperature_threshold_service.py` — `set_/clear_threshold_config`,
  `get_current_threshold_config`, `parse_temperature`. Every value is
  canonicalized to an exact `decimal.Decimal` at NUMERIC(12,3)'s scale
  (`_canonicalize`, `STORAGE_EXPONENT = Decimal("0.001")`) before any
  comparison, no-op check, or write — a value with more than 3 decimal
  places is REJECTED outright, never silently rounded. `warning_c <
  critical_c` is evaluated on that canonical form, so it can never
  disagree with what NUMERIC(12,3) actually stores. No arbitrary
  min/max range is enforced anywhere — C-01 gives none to encode, and one
  was not invented.
- `services/authorization.py` — new capability
  `MANAGE_TEMPERATURE_THRESHOLD`, Administrator-only.
- `callbacks/temperature_threshold.py` / `components/temperature_threshold_panel.py`
  — a minimal admin panel (same independent-slot pattern as C08's
  override panel), showing "Not configured." until both values are set.
  The °C unit comes from `get_metric("temperature")`
  (`config/metrics.py`) so the unit string is never duplicated, but
  displayed VALUES are the exact canonical `Decimal`, formatted
  fixed-point — deliberately NOT `MetricConfig.precision` (1 decimal
  place, a chart/table display concern for readings), which would have
  silently hidden real configured precision (e.g. a stored 60.250 would
  have shown as "60.3").
- `config/audit.py` — `TEMPERATURE_THRESHOLD_SET` (covers both initial
  set and any later change) / `TEMPERATURE_THRESHOLD_CLEARED`, against a
  fixed global entity (`temperature_threshold`/`global`), human-actor
  only (no scheduler exists for this feature). Identical canonical
  re-save is a silent no-op (no write, no audit); clearing an already-
  unconfigured state is a no-op; every real transition is audited with
  old/new snapshots (stored as `str()` of the Decimal — `json.dumps` has
  no native Decimal support, and `str()` preserves exactness a `float()`
  cast would not) and the actor. Mutation + audit share one
  `session_scope()`; a failed audit write rolls back the same
  transaction (verified for both set and clear).

### Verification

- Focused: `tests/test_migration_temperature_threshold_config.py` (12) +
  `tests/test_temperature_threshold.py` (44) +
  `tests/test_temperature_threshold_callback.py` (12) +
  `tests/test_temperature_threshold_panel.py` (7) — **75 passed**.
- Regression: `tests/test_authorization.py` + `tests/test_action_guard.py`
  + `tests/test_action_guard_db.py` + `tests/test_technician_operations.py`
  + `tests/test_audit_wiring.py` + `tests/test_equipment_selector.py` (new
  panel IDs added to its layout-wiring-guard fixture) +
  `tests/test_migration_foundation.py` (`EXPECTED_UPGRADE_TABLES` updated
  for the new table) — all passed.
- Full suite: `python -m pytest -q` — all passed, exit 0.
- `python -m alembic heads` — `011_temperature_threshold_config` is the
  sole head.
- `git diff --check` — clean. `python scripts/build_context_pack.py
  --check` — CLEAN.
- Real dev Postgres remains at migration `007` — untouched; deliberately
  not upgraded as part of this gate.
- Push verification: after `git push origin main`, `git rev-parse HEAD`,
  `git rev-parse origin/main`, and `git ls-remote origin refs/heads/main`
  all returned `c83cf94b25cbd3ceec0e079938c355e221fe03b2`.

### Correction applied during this gate (requested by the user after the
### first implementation pass, before this closure)

The first pass validated `warning_c < critical_c` on raw Python `float`
values, then persisted to `NUMERIC(12,3)`. That is unsound: two distinct
floats can satisfy the comparison in binary64 and still collapse to the
SAME three-decimal value once stored (the reported example: 20.0004 and
20.0005), silently breaking the invariant the service believed it
guaranteed. Fixed by canonicalizing to `Decimal` at storage scale before
any comparison (see "What was built" above) and by adding the database
CHECK as a second, independent layer of protection. The repository layer
(`TemperatureThresholdConfigRecord`, `set_/get_temperature_threshold_config`)
was changed from `float` to `Decimal` throughout for the same reason — the
driver already returns exact `Decimal` for `NUMERIC` columns; the removed
`float()` cast was discarding that exactness on every read.

### Known ambiguity

None encountered beyond the correction above. No new authority conflict
between `AGENTS.md`, `SOURCE_AUTHORITY.md`, the C-01 baseline, or the
source files inspected.

## VIB-CONFIG-1 — CLOSED / PUSHED / REMOTE-VERIFIED

Branch: `main`, baseline `c83cf94b25cbd3ceec0e079938c355e221fe03b2` (the
THRESH-CONFIG-1 commit). Commit: `859dbe28dd62584545d2c096dfc3017492682b61`
— subject "feat(config): add vibration contract management". Pushed to
`origin/main`; local `HEAD`, `origin/main`, and
`git ls-remote origin refs/heads/main` all verified to match this SHA.

Date: 2026-09-07. The C-02 framework — an audited, Administrator-editable
place to record answers to vibration's real sensor contract — is now
real. **`docs/VIBRATION_METRIC_CONTRACT_TBD.md`'s "Unknown / Required
from Client/Backend" table has 15 rows by direct count, not 14** — the
file has exactly one commit in its entire history (`553d142`), so it
never changed; the "14" figure tracked context repeated (including this
gate's own original queued-pointer text, below) was itself a miscount
from an earlier 2026-09-06 correction of a genuine "16". Every tracked
reference found this session — this file, `PROJECT_LEDGER.md`,
`docs/context/CLIENT_CLARIFICATION_PACK.md`,
`REQ-3I_Clarification_Register.md` — is corrected to 15, with the
miscount noted rather than erased. **This gate captures the contract
questions' answers as they become known; it does not answer any of them
itself, and vibration remains fully inactive everywhere else in the
application.**

### What was built

- `config/vibration_contract.py` — the 15 questions transcribed verbatim
  from the TBD document (key, question text, why-it-matters), as a plain
  tuple + lookup. Names the SLOTS only; invents no unit, axis model,
  threshold, aggregation, cadence, or sensor range for any of them.
- `alembic/versions/012_vibration_contract_answers.py` — a genuine
  multi-row key-value table, `vibration_contract_answers`
  (`question_key` PK, `answer_text` NOT NULL, `updated_by_user_id` FK
  users, `updated_at`) — deliberately NOT the singleton shape migrations
  010/011 use, since up to 15 independent facts exist here, any subset
  unanswered at a time. A row exists only for an ANSWERED question;
  absence is "unanswered", independently per key. No CHECK constrains
  `question_key` to the 15 known values (mirrors `config/audit.py`'s own
  precedent — the `audit_log.operation` column has no CHECK either): the
  valid key set lives in the Python registry above, so a 16th question
  needs no migration, only a new registry entry.
- `services/vibration_contract_service.py` — `set_answer`/`clear_answer`/
  `get_answer`/`get_all_answers`. Validates `question_key` against the
  registry; rejects blank answers outright (Clear is the explicit action
  for removing one, never an automatic side-effect of saving blank text).
  Identical re-save of a key's answer is a silent no-op; changing it is
  always a real, audited transition; clearing an already-unanswered key
  is a no-op. Answers are free-text contract CAPTURE only — this module
  never interprets what an answer means, and nothing reads it back for
  any runtime purpose.
- `services/authorization.py` — new capability
  `MANAGE_VIBRATION_CONTRACT`, Administrator-only.
- `callbacks/vibration_contract.py` / `components/vibration_contract_panel.py`
  — a minimal admin panel (same independent-slot pattern as C08's/
  THRESH-CONFIG-1's panels): a summary line per question ("Unanswered" or
  the recorded text, for all 15, in the TBD document's own order) plus a
  question-select + textarea + Set/Clear form.
- `config/audit.py` — `VIBRATION_CONTRACT_ANSWER_SET` (covers both
  initial answer and any later change) / `VIBRATION_CONTRACT_ANSWER_CLEARED`,
  entity `vibration_contract`, entity_id = the specific `question_key`
  (not a fixed "global" string like C08's/THRESH's single-fact
  entities, since each question is independently addressable). Every
  real transition audited with old/new `answer_text` and the actor;
  mutation + audit share one `session_scope()`, and a failed audit write
  rolls back the same transaction (verified for both set and clear).
- **Vibration remains completely inactive**: zero diff and zero mentions
  in `config/metrics.py`, `services/monitoring_service.py`
  (`MonitoringCondition`), `config/reports.py`, or any metric-selector/
  chart/KPI component. `services/event_semantics.py` has zero diff — its
  pre-existing dormant note ("High-temperature and vibration_event
  deliberately have NO entry") is untouched. No vibration reading query,
  alarm, or threshold-evaluation logic was added anywhere.

### Verification

- Focused: `tests/test_migration_vibration_contract_answers.py` (8) +
  `tests/test_vibration_contract.py` (24) +
  `tests/test_vibration_contract_callback.py` (13) +
  `tests/test_vibration_contract_panel.py` (9) — **54 passed**, plus one
  capability-policy test added to `tests/test_authorization.py`.
- Regression: `tests/test_action_guard.py` + `tests/test_action_guard_db.py`
  + `tests/test_technician_operations.py` + `tests/test_audit_wiring.py`
  + `tests/test_equipment_selector.py` (new panel IDs added to its
  layout-wiring-guard fixture) + `tests/test_migration_foundation.py`
  (`EXPECTED_UPGRADE_TABLES` updated for the new table) +
  `tests/test_temperature_threshold.py` — all passed.
- Full suite: `python -m pytest -q` — all passed, exit 0.
- `python -m alembic heads` — `012_vibration_contract_answers` is the
  sole head.
- `git diff --check` — clean. `python scripts/build_context_pack.py
  --check` — CLEAN.
- Real dev Postgres remains at migration `007` — untouched; deliberately
  not upgraded as part of this gate.
- Push verification: after `git push origin main`, `git rev-parse HEAD`,
  `git rev-parse origin/main`, and `git ls-remote origin refs/heads/main`
  all returned `859dbe28dd62584545d2c096dfc3017492682b61`.

### Known ambiguity

None encountered beyond the 14→15 documentation-count correction above.
No new authority conflict between `AGENTS.md`, `SOURCE_AUTHORITY.md`, the
C-02 baseline, or the source files inspected.

## RTL-PROG-EXEC-1 — CLOSED / PUSHED / REMOTE-VERIFIED

Branch: `main`, baseline `859dbe28dd62584545d2c096dfc3017492682b61` (the
VIB-CONFIG-1 commit). Commit: `0787b90a3f658b2bf347f1ae58b659b181d33c52`
— subject "feat(programming): reconcile command execution status". Pushed
to `origin/main`; local `HEAD`, `origin/main`, and
`git ls-remote origin refs/heads/main` all verified to match this SHA.

Date: 2026-09-07. Connects the two RTL-programming/command foundations
that already existed but did not yet talk to each other —
`rtl_programming_service.py` (OPS-PROG-1/RTL-IF-1: persists an operator's
programming REQUEST, atomically inserting one `rtl_commands` row per
accepted request) and `rtl_command_dispatch_service.py` + the existing
command lifecycle (RTL-IF-2, ADR-018). The command row no longer stays
`QUEUED` forever with no reconciliation: every command transition now also
projects a truthful status onto the programming request that created it,
in the same database transaction. **No production transport contract was
invented** — C-05 (the real MQTT/Eskom protocol) remains
Eskom-controlled/external and unanswered; nothing here selects, wires, or
auto-instantiates `SimulatorTransport` into any production code path.

### What was built

- **No migration.** `rtl_programming_requests`' existing `status`/
  `completed_at`/`error_message` columns and CHECK-constrained vocabulary
  (`pending`/`queued`/`sent`/`successful`/`failed`, migration 005) already
  supported the required lifecycle exactly — nothing needed to be added to
  the schema.
- `config/commands.py` — `REQUEST_STATUS_FOR_COMMAND_STATE`, the seam
  mapping every `rtl_commands.state` onto its `rtl_programming_requests.
  status` projection: `QUEUED → queued`; `SENT`/`ACKNOWLEDGED → sent`
  (both mean "handed to transport, not yet resolved" from the request's
  point of view); `SUCCEEDED → successful`; `FAILED`/`TIMED_OUT → failed`
  (the request's four-state completion model has no separate timeout
  status, and none was invented). `pending` is deliberately absent from
  the map — it is the row's insert-time default only, never an
  observable rest state once a request has been accepted.
- `repositories/plant_monitoring_repository.py` — `ProgrammingRequestRecord`
  now carries `completed_at`/`error_message` (previously always NULL by
  construction; now genuinely written). New
  `update_programming_request_status()`: pure persistence, one
  conditional-free UPDATE, `completed_at` written from the DB clock only
  when the caller says the projection is terminal, `error_message` written
  exactly as given.
- `services/rtl_command_service.py` — every lifecycle transition
  (`mark_sent`/`mark_acknowledged`/`mark_succeeded`/`mark_failed`/
  `mark_timed_out`) now performs the command's own conditional UPDATE
  **and** the request's status projection inside one shared
  `session_scope()` — a failure on either write rolls back both, so the
  command and its request can never disagree about where a transition
  landed (no split-brain). `error_message` is derived only from the
  command's own already-normalized, bounded fields (`failure_code`
  optionally combined with `failure_detail`) — never a raw exception or
  provider stack trace; a successful or in-flight projection carries no
  error message by construction, not by a separate branch that could
  drift out of sync.
- `services/rtl_programming_service.py` — `record_request()` now projects
  the brand-new request from `pending` to `queued` the moment its QUEUED
  command is created, in the SAME transaction as that command insert and
  the existing `RTL_PROGRAM_REQUESTED` audit write (PROG-D6, revised: this
  is the "future device-integration slice" its own docstring anticipated).
  A failed projection rolls the whole request back with it, same as a
  failed command insert always did.
- `services/rtl_programming_execution_service.py` (new) —
  `execute_request(request_id, transport)`: the protocol-neutral
  orchestration seam the gate asked for. Resolves the request's one
  existing command and hands it to the existing
  `rtl_command_dispatch_service.dispatch_command`, wrapping its
  `CommandNotDispatchableError` into this module's own
  `ProgrammingExecutionError`. Does not import, name, or construct
  `SimulatorTransport` — picking a transport is entirely the caller's
  decision — and is not called from any callback, page, or scheduler.
  Adds no retry, no polling, no background worker.
- `callbacks/device_manage.py` — one-word honesty fix: the Program RTL
  confirmation copy said "is saved and pending"; since a request is now
  observably `queued` (never `pending`) by the time `record_request()`
  returns, the copy now says "is saved and queued". The rest of the
  disclaimer ("No command has yet been sent…the physical RTL is not
  confirmed programmed") is unchanged and still true — nothing here
  wires execution into this callback.
- Existing command-lifecycle legality (`config.commands.
  ALLOWED_TRANSITIONS`) and concurrency protection
  (`update_command_state`'s `WHERE state = :expected_state` conditional
  UPDATE) are unchanged and remain the sole authority for what transition
  is legal — this gate only adds what happens, transactionally, once a
  transition is accepted.
- Tests: `tests/test_rtl_programming_execution.py` (new, 18 tests) —
  request creation ends `queued`; SENT/ACKNOWLEDGED both project to
  `sent`; success path (`successful`, `completed_at` set, no error);
  failure and timeout paths (`failed`, safe normalized `error_message`,
  never a raw exception); `completed_at` set only on terminal
  projections; an illegal transition never touches the request; a
  concurrent/stale conditional UPDATE loses at the DB layer before any
  projection runs; a failed request-projection write rolls back the
  command transition (and vice versa at request-creation time); a
  refused re-dispatch leaves the request projection untouched; the new
  execution service's success/failure/unknown-request/already-dispatched
  behavior; and a structural (`ast`-based) proof that the execution
  service never imports `SimulatorTransport`. `tests/test_rtl_programming.py`,
  `tests/test_rtl_command_service_lifecycle.py`,
  `tests/test_rtl_command_dispatch.py` — updated: three assertions that
  previously pinned "the request stays `pending`" or "the request row is
  byte-for-byte unchanged by the command's lifecycle" now assert the
  opposite for status/completed_at/error_message specifically (the
  deliberate change this gate makes) while still asserting every
  provenance column (`device_id`, `master_msisdn`, `requested_by`,
  `transformer_id`, `requested_at`, `request_method`) is untouched.

### Verification

- Focused: `tests/test_rtl_programming_execution.py` (18) +
  `tests/test_rtl_programming.py` (29) + `tests/test_rtl_commands.py` (9) +
  `tests/test_rtl_command_service_lifecycle.py` (12) +
  `tests/test_rtl_command_dispatch.py` (15) — **83 passed**.
- Regression: `tests/test_authorization.py` + `tests/test_action_guard.py`
  + `tests/test_action_guard_db.py` + `tests/test_action_guard_callbacks.py`
  + `tests/test_technician_operations.py` + `tests/test_audit_wiring.py` +
  `tests/test_equipment_selector.py` + `tests/test_migration_foundation.py`
  + `tests/test_auth_harden_repair.py` (exercises the Program RTL
  confirmation callback and its "queued" copy) — all passed.
- Full suite: `python -m pytest -q` — all passed, exit 0.
- `python -m alembic heads` — `012_vibration_contract_answers` remains the
  sole head (this gate adds no migration).
- `git diff --check` — clean. `python scripts/build_context_pack.py
  --check` — CLEAN.
- Real dev Postgres remains at migration `007` — untouched; this gate has
  no schema change to apply.
- Push verification: after `git push origin main`, `git rev-parse HEAD`,
  `git rev-parse origin/main`, and `git ls-remote origin refs/heads/main`
  all returned `0787b90a3f658b2bf347f1ae58b659b181d33c52`.

### Known ambiguity

None encountered. No new authority conflict between `AGENTS.md`,
`SOURCE_AUTHORITY.md`, ADR-017, ADR-018, or the source files inspected.
Whether this reconciliation design (the projection mapping, the
one-transaction pairing, the new orchestration-service boundary) should
be written up as its own ADR was considered and not decided unilaterally
this session — flagged rather than resolved, the same open item C08-AUTO-
DISABLE-1's scheduler decision left behind (see that section above): it is
localized and reversible (a dict mapping plus one shared transaction, not
a new external boundary), which argues against a new ADR, but a future
session may judge otherwise once RTL-PROG-SIM-1 exists alongside it.

## RTL-PROG-SIM-1 — CLOSED / PUSHED / REMOTE-VERIFIED

Branch: `main`, baseline `0787b90a3f658b2bf347f1ae58b659b181d33c52` (the
RTL-PROG-EXEC-1 commit). Commit: `603e1581a53a42e15c1ed865f774e8751363a770`
— subject "feat(programming): add development simulation flow". Pushed to
`origin/main`; local `HEAD`, `origin/main`, and
`git ls-remote origin refs/heads/main` all verified to match this SHA.

Date: 2026-09-07. The demo flow now runs end to end locally: **Program
RTL → request queued → explicitly simulate → sent → successful/failed**,
with the screen stating plainly that the last part is simulated and no
physical RTL was contacted. Built on RTL-PROG-EXEC-1's
`execute_request()` seam and the existing deterministic
`SimulatorTransport` (RTL-IF-2, ADR-018) — **no production transport was
chosen, and none was invented.** C-05 (the real MQTT/Eskom protocol)
remains Eskom-controlled/external and unanswered; this gate does not move
that forward and must not be mistaken for it. **No migration was
required** — this gate persists nothing new.

### The environment boundary (the point of this gate)

- `RTL_PROGRAMMING_SIMULATOR_ENABLED`, parsed **only** in
  `config/settings.py` (`resolve_programming_simulator_enabled`,
  `ProgrammingSimulatorSettings`) — environment parsing stays centralized
  there, as it is for every other setting in this application.
- **Defaults OFF.** Unset, blank, or any non-truthy value resolves to
  `False`. An environment that has never heard of this setting cannot
  simulate.
- **Explicit enablement in `APP_ENV=production` FAILS CLOSED at startup**
  with a `RuntimeError` raised during configuration resolution (import
  time), so the process refuses to start. It deliberately does NOT
  silently downgrade to `False`: an operator who asked a production
  deployment to run a simulator holds a mistaken belief about what that
  deployment is doing, and quietly ignoring the request would leave the
  belief intact. Same fail-closed shape as `resolve_flask_secret_key`
  (AUTH-PROD-HARDEN-1), for the same reason.
- **Production with the flag unset/false starts normally**, with no
  simulator controls in the layout and no simulation callback registered.
  Both behaviours were verified by actually importing the app under each
  environment, not merely asserted.
- Because the only truthy path returns from a branch that has already
  excluded production, no production process can hold `True` — which is
  what makes the simulator structurally unreachable there.

### What was built

- `services/rtl_programming_simulation_service.py` (new) — **the only
  application service that constructs a `SimulatorTransport`**, and only
  after `require_simulation_enabled()` passes (the setting AND a
  re-checked `not IS_PRODUCTION`, defence in depth). It then **delegates
  to `rtl_programming_execution_service.execute_request(...)`; no
  lifecycle logic is duplicated** — a test asserts `mark_sent`/
  `mark_acknowledged`/`mark_succeeded`/`mark_failed`/`mark_timed_out`/
  `update_command_state`/`update_programming_request_status`/
  `dispatch_command` appear nowhere in this module. Supported outcomes are
  **Success / Failure / Timeout only**, exactly `SimulatorTransport`'s own
  deterministic vocabulary — **simulation semantics, not Eskom protocol
  semantics** — and every operator-facing label starts with "Simulated".
- `callbacks/rtl_programming_simulation.py` (new) — `register()` is a
  **no-op unless simulation is enabled**, so in production and in any
  environment that has not opted in the callback does not exist at all.
  One explicit press performs exactly one attempt: no retry, no polling,
  no worker, no scheduler, no automatic execution.
- `components/device_manage_drawer.py` — a "Simulate execution
  (development only)" section inside the existing Program RTL panel,
  rendered **only** when enabled, carrying the required notice
  *"Development simulation — no physical RTL, MQTT, SMS or Eskom
  communication occurs"* plus "not evidence that any physical RTL was
  programmed". Provides the outcome selector, an explicit **Simulate
  execution** button, and a resulting request-status display. When
  disabled these controls do not exist at all — there is nothing hidden
  or disabled for a browser to re-enable. Also adds
  `PROGRAM_RTL_LAST_REQUEST_ID`, a store present in every environment so
  `confirm_program_rtl` has one output shape regardless of the flag.
- `callbacks/device_manage.py` — `confirm_program_rtl` gained one Output:
  it publishes the id of the request it just recorded. **Recording still
  executes nothing** — no dispatch, no transport, no simulator; the
  request is left `queued` exactly as RTL-PROG-EXEC-1 leaves it, and
  simulation requires a separate, deliberate operator click afterwards.
- `app.py` — `rtl_programming_simulation.register(app)` called
  unconditionally; the module itself owns the enablement decision, so
  there is one place it is made.
- `.env.example` — documents the setting, its OFF default, and the
  production fail-closed behaviour.

### Authorization and tamper protection

- **Existing `PROGRAM_RTL` action authorization is reused**, not
  re-invented: Administrator any RTL; Technician assigned RTL only;
  General User denied. `require_action` runs inside the callback, so
  hiding the control is not the protection — a fabricated click against a
  control that was never rendered is still refused.
- **Authorization runs BEFORE the request lookup.** An unauthorized
  caller never reaches `get_programming_request`, so it learns nothing at
  all — verified by asserting the lookup list stays empty on every denied
  path.
- **Browser-owned request ids are validated and must belong to the
  already-authorized device.** The store is untrusted: the id must be a
  real `int` (`bool` excluded explicitly, since it is an `int` subclass)
  and `request.device_id` must equal the device just authorized. A DB
  test injects another device's REAL request id and proves that device's
  command stays `QUEUED`.
- **Unknown and mismatched ids use identical refusal behaviour**, so this
  control cannot be used as a request-existence oracle; a test asserts
  the two rendered refusals are equal, and that neither echoes the other
  device's id. AUTH-HARDEN-1/AUTH-PROD-HARDEN-1 behaviour is untouched.

### What this does NOT claim

**A simulated `successful` is not evidence that a physical RTL was
programmed.** No MQTT, SMS, HTTP or Eskom payload/ACK contract was
implemented or invented; no retry, scheduler or worker was added; the
`DeviceTransport` interface is unchanged; and normal programming
execution still never instantiates a simulator — `SimulatorTransport` is
structurally absent from `rtl_programming_execution_service.py`,
`rtl_programming_service.py` and `callbacks/device_manage.py`, proven by
`ast`-based import inspection rather than by absence of a diff.

### Verification

- Focused: `tests/test_rtl_programming_simulation.py` (new, **63
  passed**) — default-off; explicit development enablement; production
  enable attempt fails closed; controls hidden when disabled and present
  when enabled; no callback registered when disabled; Administrator and
  assigned-Technician simulation allowed; unassigned Technician, General
  User and no-session denied before execution AND before any request
  lookup; tampered/mismatched/non-integer/missing ids refused;
  unknown-vs-mismatched refusal equivalence; Success → `successful`;
  Failure → `failed` with `SIMULATED_FAILURE`; Timeout → `failed` with
  `SIMULATED_TIMEOUT`; repeated execution refused by the existing
  lifecycle without overwriting the recorded outcome; recording a request
  executes nothing; and the structural import proofs above.
- RTL regression: `tests/test_rtl_programming_execution.py` +
  `tests/test_rtl_programming.py` + `tests/test_rtl_commands.py` +
  `tests/test_rtl_command_service_lifecycle.py` +
  `tests/test_rtl_command_dispatch.py` +
  `tests/test_simulated_event_source.py` — **117 passed**.
- Auth/settings/wiring regression: `tests/test_action_guard_callbacks.py`
  (its `TestProgramRtl._call` helper updated for the new third Output) +
  `tests/test_auth_harden_repair.py` + `tests/test_authorization.py` +
  `tests/test_action_guard.py` + `tests/test_action_guard_db.py` +
  `tests/test_technician_operations.py` + `tests/test_audit_wiring.py` +
  `tests/test_equipment_selector.py` +
  `tests/test_prod_session_hardening.py` +
  `tests/test_live_sim_settings.py` — **340 passed**.
- Callback/layout wiring was checked in BOTH modes: with the simulator
  enabled the callback registers and no callback references an id no
  layout renders; with it disabled neither half exists.
- Full suite: `python -m pytest -q` — all passed, exit 0.
- `python -m alembic heads` — `012_vibration_contract_answers` remains
  the sole head (this gate adds no migration).
- `git diff --check` — clean. `python scripts/build_context_pack.py
  --check` — CLEAN.
- Real dev Postgres remained at migration `007_audit_log` at this gate's
  close — untouched and deliberately not upgraded by it. **This is no
  longer current**: `LOCAL-DB-CATCHUP-1` (below) subsequently advanced the
  real dev DB to `012_vibration_contract_answers`.
- Push verification: after `git push origin main`, `git rev-parse HEAD`,
  `git rev-parse origin/main`, and `git ls-remote origin refs/heads/main`
  all returned `603e1581a53a42e15c1ed865f774e8751363a770`.

### Known ambiguity

None encountered. No new authority conflict between `AGENTS.md`,
`SOURCE_AUTHORITY.md`, ADR-018, or the source files inspected. The
open question flagged at RTL-PROG-EXEC-1's close — whether the
reconciliation/orchestration design should become its own ADR — now has a
second tranche standing on it (this gate's environment boundary) and
remains deliberately unresolved rather than decided unilaterally here.

## LOCAL-DB-CATCHUP-1 — COMPLETED / VERIFIED

Date: 2026-09-07. Environment/verification gate, **no application code
and no tracked-document change beyond this closure record**. The real
development database had fallen five migrations behind the code, because
every gate since `007_audit_log` deliberately left it alone (the suite
exercises migrations through the `isolated_schema` fixture only, never the
real `plant_monitoring` schema). This gate closed that gap as its own
careful, non-destructive step and then smoke-tested what the upgrade made
reachable. Application commit at execution time:
`603e1581a53a42e15c1ed865f774e8751363a770`.

### Preflight — the target was proven before anything was touched

- `APP_ENV=development` (`IS_PRODUCTION=False`, simulator resolved
  `False`).
- Docker container `plant_monitoring_postgres` (`postgres:16`, healthy),
  published `0.0.0.0:5436->5432/tcp`.
- Host `localhost`, **port 5436**, database `powerplant_demo`, schema
  `plant_monitoring`.
- The server was asked for its own identity rather than trusting
  configuration: `inet_server_addr 172.24.0.3`, `inet_server_port 5432`,
  PostgreSQL 16.14 (Debian) — inside the local Docker network, **not a
  client or production target**.
- `alembic current` = `007_audit_log`; `alembic heads` =
  `012_vibration_contract_answers` (sole head).
- Only non-secret connection metadata was reported at any point; no
  password, credential, secret key or `.env` content was printed.

### Backup — taken and validated before migrating

A PostgreSQL **custom-format** dump was written **outside the repository**
before the upgrade, via `docker exec … pg_dump -Fc` with the password
supplied through the environment and never echoed. Non-zero size:
**11,921,321 bytes**. Validated by streaming it back through
`pg_restore --list`, which read it successfully: CUSTOM format,
`dbname: powerplant_demo`, 184 TOC entries, 27 `TABLE DATA` entries. (The
backup path is deliberately not recorded here — it is a local operator
artifact, not repository state.)

### Migration — non-destructive, upgrade only

One `python -m alembic upgrade head`, which advanced:

```
007_audit_log
  -> 008_rtl_commands
  -> 009_rtl_command_lifecycle
  -> 010_forwarding_auto_disable
  -> 011_temperature_threshold_config
  -> 012_vibration_contract_answers
```

**No reset, no purge, no schema drop/recreate, and no seed script**
(`db/seed_plant_monitoring.py`, `db/seed_admin_demo.py`) was run at any
point.

### Preservation — every pre-existing population identical

| Table | Before | After |
|---|---|---|
| `plants` | 30 | 30 |
| `transformers` | 71 | 71 |
| `devices` | 120 | 120 |
| `readings` | 1,383,360 | 1,383,360 |
| `users` | 7 | 7 |
| `user_device_assignments` | 96 | 96 |
| `device_events` | 13 | 13 |
| `audit_log` | 3 | 3 |
| `message_forwarding` | 1 | 1 |
| `rtl_active_state` | 2 | 2 |
| `rtl_programming_requests` | 0 | 0 |

**The migration itself added no business records and no audit rows.**
Table count went 12 → 16.

### New schema objects verified

- `rtl_commands` — present with its 009 lifecycle columns (`sent_at`,
  `acknowledged_at`, `completed_at`, `failure_code`, `failure_detail`),
  `uq_rtl_commands_request_id` (ADR-017's one-command-per-request), and
  the four ordering/failure CHECK constraints.
- `forwarding_auto_disable_override` — singleton CHECK + user FK.
- `temperature_threshold_config` — singleton CHECK,
  `warning < critical` CHECK, user FK.
- `vibration_contract_answers` — PK + user FK, and deliberately **no**
  CHECK on `question_key` (VIB-CONFIG-1's decision, intact).

**All four new tables were empty / unconfigured after migration. No
business values were invented anywhere.**

### Administrator browser smoke (Playwright/Chromium, real upgraded DB)

Signed in with the configured administrator credential and confirmed
against the real data: Fleet Overview loads; the C08 auto-disable override
panel renders ("Default cutoff: 18:30 Africa/Johannesburg. No override…");
the temperature threshold panel renders and correctly reads **"Not
configured."**; the vibration contract panel renders **15 "Unanswered"**
items and "0 of 15 questions answered". No DB/schema error text appeared
anywhere on the page. **No fake temperature thresholds and no vibration
contract answers were created** — reachability/read rendering was treated
as sufficient, exactly as the gate required.

### Simulator smoke

- **Disabled state verified first**: with the simulator off, none of the
  four simulation control ids exist in the Program RTL panel, and the
  pre-existing "Requests are recorded, not sent." honesty notice is
  intact.
- **Temporary, process-only enablement** (an environment variable on the
  app process — `.env` was never edited, and a check confirmed the flag is
  absent from it) rendered the simulation controls, the **"Development
  simulation — no physical RTL, MQTT, SMS or Eskom communication occurs."**
  warning, and the "not evidence that any physical RTL was programmed"
  wording. Callback reachability confirmed: the simulation callback binds
  `program-rtl-sim-result.children` only in that mode.
- **No real simulated execution was performed.** The dev database contained
  **zero** programming requests, so no legitimate queued request existed to
  simulate. Per this gate's own constraint, **no fake Master MSISDN and no
  permanent fake programming history were created**. Success/Failure/
  Timeout execution is already covered by the isolated-schema DB tests in
  `tests/test_rtl_programming_simulation.py`.
- **The simulator flag was removed afterwards.** Final local state is
  simulator **disabled**: absent from the shell environment, absent from
  `.env`, `programming_simulator.enabled = False`,
  `is_simulation_enabled() = False`, and every app process started by this
  gate was stopped.

### Non-blocking observations (neither is a defect in this gate)

1. A pre-existing **React uncontrolled→controlled input warning** appears
   in the browser console on authenticated pages. Traced to the manage
   drawer's Program RTL inputs (`program-rtl-uid`, `program-rtl-msisdn`),
   which have carried no initial `value` prop since well before this work
   — byte-identical at pre-session commit `d10c566`. Cosmetic, dev-mode
   only, unrelated to migrations 008–012 and to RTL-PROG-SIM-1. Not fixed
   here: this gate does not edit application code.
2. **Two pre-existing `app.py` processes** (a different Python
   interpreter, not started by this gate, not bound to a port) remain
   running on the machine — the same "stray process" class
   `LOCAL-ENV-CLEAN-1` dealt with before. Left untouched because their
   ownership was uncertain and killing someone's running work is not a
   side effect this gate should take unasked.

### Final state

- **Real dev DB revision: `012_vibration_contract_answers`** — now level
  with the code. `alembic heads` still reports it as the sole head.
- Worktree clean except `?? debug.log`; `git diff --check` clean; no
  tracked file changed by the verification work itself (the Playwright
  scripts and screenshots were written to a session scratchpad outside the
  repository).

## CLIENT-SYNC-2A — COMPLETED / INSPECTION ONLY

Date: 2026-09-07. Read-only inspection against development checkpoint
`be560eeda825c8f2ec7f1b87620ad589d1dea24e` and client progress branch
`cc-1-command-center-progress` @ `3d4897cdd903d6012fca94620caedc73e081f517`
(both SHAs verified; client `main` = `aa1dd3c`). **Neither repository was
modified** — nothing copied, staged, committed, pushed, or checked out.

Authority read first: `docs/CLIENT_DELIVERY.md` (present locally,
gitignored by design at `.gitignore:38` — absence from GitHub is not
absence from the machine), `scripts/check_client_release.py`, and the
CLIENT-SYNC-1 provenance (`34d5d73`, the substantive 66-path Command
Center curation; `3d4897c`, a single `assets/app.css` fix).

### What the inspection established

- **Client branch migration head is `007_audit_log`** — five behind the
  code.
- **The delta is not feature-separable.** An import-closure walk from
  `app.py` on both branches (first-party imports only, resolving
  `from package import submodule`) gives **118 runtime files on dev vs 86
  on the client**: 28 missing entirely, 51 present but different. `app.py`
  and `callbacks/routing.py` are import hubs, so leaving out the
  simulator, vibration, threshold or C08 each requires **editing
  `app.py` and `pages/plants_overview.py`** — permanent client/dev source
  divergence that must be re-applied every week, not a file-selection
  choice. Reports, notification delivery and the simulated event source
  are self-contained by contrast.
- **Test obligation** (`CLIENT_DELIVERY.md` requires a green suite before
  any push): 64 new test files, 46 modified, 2 deleted. Client has 109
  test files, dev 171. Realistic total curation set ≈ 200 file
  operations — a parity sync, not a weekly slice.
- **The client branch holds 5 documents that exist nowhere on `main`**
  (`docs/DATA_AND_SYSTEM_BEHAVIOUR.md`, `DEMO_WALKTHROUGH.md`,
  `FEATURES_AND_WORKFLOWS.md`, `SYSTEM_OVERVIEW.md`,
  `USER_ROLES_AND_PERMISSIONS.md`, from `ea0e184`). They appear as
  deletions in a dev-vs-client diff — a blanket mirror would destroy the
  client's own documentation pack.
- **Migrations 008–012 are additive-only** (008/010/011/012 are
  `create_table`; 009 only `add_column`s onto the table 008 creates), so a
  non-destructive `alembic upgrade head` is supported by evidence on the
  client laptop — no reset, no reseed. New dependencies for the client:
  `tzdata==2026.3`, `fpdf2==2.7.9`.
- **The leakage guard had gaps**, and client-visible UI carried internal
  clarification-register ids. Both are fixed by CLIENT-SYNC-2A-FIX below.

A first pass at this inspection grouped files by grep and presented
feature-by-feature curation as available. It was wrong: the import
closure had not been computed. Recorded here because the corrected
finding — that curation here is parity-or-surgery — is the decision the
next gate rests on.

## CLIENT-SYNC-2A-FIX — IMPLEMENTED / VERIFIED / PENDING COMMIT

Date: 2026-09-07. Prepares the curation boundary before anything is
copied. **The client repository was not touched.**

### Client leakage guard strengthened

`scripts/check_client_release.py` now catches the nine paths CLIENT-SYNC-2A
found tracked on `main` while the guard stayed silent: our own open-question
register `docs/VIBRATION_METRIC_CONTRACT_TBD.md`, the internal
`docs/RTL_CLIENT_REVIEW_GATE.md`, the client's own specification PDF plus
`pdf_content.txt`/`pdf_content_up_to_3.4.txt` extracted from it,
`check_databases.py`, both `scripts/generate_workflow*.py`, and
`railway.json`. Violations on `main` go **84 → 93**; the client branch
still reports **clean, 263 files, no internal material**.

It also now refuses by **shape, not only by name** — any `.env*` other
than `.env.example`, and any `.log`/`.dump`/`.bak`/`.sql.gz`/`.pyc` —
because a hand-written list is precisely what rotted here, the same
failure mode as the original `PURGE_ORDER` defect (ADR-010/SEED-RESET-1).
Checked in both directions: no legitimate delivered file (`.env.example`,
`app.py`, migrations, assets, tests) is flagged, and `.env`, `.env.local`,
`debug.log`, `backup.dump` all are.

`docs/CLIENT_DELIVERY.md`'s never-curate list was updated to match (that
file is gitignored, so it is not part of the commit — but it is the
human control the doc itself calls "the control", so it must not drift
from the guard).

### Client-visible internal terminology scrubbed

Four rendered strings carried internal clarification-register ids. In each
the id was doing real work, so the **meaning was preserved and only the id
removed**:

- Threshold heading `"… Threshold (C-01, framework only)"` → `"… Threshold"`
  plus "Recorded as configuration only. These values do not yet raise
  alarms or change any device's monitoring status."
- Vibration heading `"Vibration Contract (C-02, framework only)"` →
  `"Vibration Contract"` plus "Records the vibration sensor specification
  as it is confirmed. Vibration is not yet measured, charted or alarmed
  anywhere in the application."
- Both Report Centre period notices: `"(development baseline C-15, pending
  client confirmation)"` → "that default is provisional and remains
  subject to confirmation" (the asserted `"rolling 30 days"` wording is
  unchanged).

Verified by rendering both panels — no internal id reaches the screen.
**Deliberately kept:** `BR016`/`BR008`, which are the CLIENT's own
functional-spec ids and meaningful to them, and the `ADR-002` reference in
a `situation_summary.py` docstring, which is not rendered.

**Deliberately NOT scrubbed:** internal gate names and ids in module
docstrings and code comments (`temperature_threshold_panel.py:1`,
`callbacks/vibration_contract.py:1`, `pages/report_center.py:4`, …). That
terminology is pervasive across the codebase (`RTL-IF-2`, `AUD-1`,
`FWD-D5`, `ADR-018`) and is genuine traceability on `main`; removing it
wholesale would be a large, value-destroying change. Whether delivered
`.py` files may carry it is a **curation-policy decision for
CLIENT-SYNC-2B**, not a defect here.

### Reset-contract table classification fixed

The gap was **genuinely stale**, so it was fixed rather than left.
Migrations 010, 011 and 012 each added a table and none was classified;
`tests/test_seed_reset_contract.py`'s hand-written `KNOWN_TABLES` (12) and
`db/seed_plant_monitoring.py`'s `RESET_PRESERVES` were stale in the SAME
direction, so `assert KNOWN_TABLES == classified` kept passing — the one
way a hand-written expectation fails silently, and exactly the rot that
check exists to prevent.

**No behavioural defect existed**: `RESET_REPLACES == ("readings",)` so a
reset never touched them, and all three FK only to `users`, which
`PURGE_ORDER` deliberately never deletes — so
`TestPurgeOrderAgainstTheLiveSchema` was correctly silent. The contract
simply did not *say* they were preserved.

Fixed on both sides: `forwarding_auto_disable_override`,
`temperature_threshold_config` and `vibration_contract_answers` are now in
`RESET_PRESERVES` (stating what already happens), and `KNOWN_TABLES` is
**derived from `op.create_table(...)` in the migration files** — which is
what its own docstring already claimed it was. 15 tables, self-maintaining,
and a future migration that adds an unclassified table now fails this test.
Proven to bite by simulating one. It remains a pure (`not db`) test,
complementing the live-schema purge walk rather than replacing it.

### Verification

- Focused: `tests/test_seed_reset_contract.py`,
  `tests/test_temperature_threshold_panel.py`,
  `tests/test_vibration_contract_panel.py`,
  `tests/test_temperature_threshold.py`, `tests/test_vibration_contract.py`,
  `tests/test_report_center.py`, `tests/test_report_max_temperature.py`,
  `tests/test_report_export.py`, `tests/test_equipment_selector.py` — all
  passed.
- Full suite: `python -m pytest -q` — all passed, exit 0.
- Leakage: guard clean against `cc-1-command-center-progress` (263 files);
  93 violations against `main`, the nine new ones confirmed individually.
- `python scripts/build_context_pack.py --check` — CLEAN.
  `git diff --check` — clean.
- Alembic head unchanged (`012_vibration_contract_answers`); real dev DB
  unchanged at `012`; **no migration added by this gate**.
- **Client repository untouched** throughout.

## CLIENT-SYNC-2B — COMPLETED / DELIVERED / REMOTE-VERIFIED

Date: 2026-09-07. Development baseline
`72dd1cf95e94b642f05b517c804cea235a0067b4`. The accepted milestone is
delivered to the client repository.

**Delivered client branch:** `cc-1-command-center-progress`
**Client commit:** `3f21c3a000de5026868c2031eb865569c368e509` — subject
"feat(client): synchronize accepted runtime milestone", parent
`3d4897cdd903d6012fca94620caedc73e081f517`. Local `HEAD` and the client
remote's `refs/heads/cc-1-command-center-progress` both verified to match
this SHA. 217 files changed (106 added, 107 modified, 3 deleted, 1 rename),
+32,390 / −2,928.

### What was delivered

Runtime **parity**, not a surgical subset — CLIENT-SYNC-2A established that
`app.py`/`callbacks/routing.py` are import hubs, so a subset would have
required permanent client/dev source divergence re-applied every week.
357 paths were copied byte-identical from `main` via
`git checkout main --pathspec-from-file`: all of `alembic/ assets/
callbacks/ components/ config/ db/ pages/ repositories/ services/ tests/`
plus `app.py`, `routes.py`, `alembic.ini`, `pytest.ini`,
`docker-compose.yml`, `requirements*.txt`, the four architecture documents
the client already held, and `scripts/run_forwarding_auto_disable.py`.
The client tree went 263 → 366 files, 109 → 170 test files.

**Migrations 008–012 delivered** (`rtl_commands`, command lifecycle,
forwarding auto-disable override, temperature threshold config, vibration
contract answers), taking the client from `007_audit_log` to
`012_vibration_contract_answers`. All additive, so the documented upgrade is
non-destructive. `requirements.txt` carries the two new pins
(`tzdata==2026.3`, `fpdf2==2.7.9`).

**The simulator remains default OFF.** `RTL_PROGRAMMING_SIMULATOR_ENABLED`
ships commented out in `.env.example`, documented in client-facing language
with no internal identifiers, stating that no physical RTL, MQTT, SMS or
other external communication occurs and that enabling it under
`APP_ENV=production` stops the application at startup. The code ships inert:
including it costs nothing visible, whereas removing it would have required
`app.py` surgery.

**The five client-only documents were preserved** —
`docs/DATA_AND_SYSTEM_BEHAVIOUR.md`, `DEMO_WALKTHROUGH.md`,
`FEATURES_AND_WORKFLOWS.md`, `SYSTEM_OVERVIEW.md`,
`USER_ROLES_AND_PERMISSIONS.md`. They exist nowhere on `main` and a blanket
mirror would have deleted them. With `GETTING_STARTED.md` they remain the
entire contents of the delivered `docs/`.

**Client-tailored files were not overwritten:** `README.md` (gained an
"Upgrading an existing installation" section — reinstall dependencies,
`alembic upgrade head`, and an explicit instruction NOT to run the seed
scripts), `docs/GETTING_STARTED.md`, `.gitignore`, `.gitattributes`,
`.env.example`.

Scoping delivery to application material rather than "everything on `main`
minus the guard" mattered: the naive set pulled in 30 internal `docs/`
files — spec audits, UX acceptance records, wireframes, baseline
screenshots — that the client does not have and the guard does not catch.

### Two blockers found and resolved (CLIENT-SYNC-2B-FIX)

1. **A delivered test depended on undelivered material.**
   `tests/test_build_context_pack_check.py` exercises
   `scripts/build_context_pack.py`, which is never delivered — removed from
   the delivery, as it was never client-relevant coverage. And one assertion
   in `tests/test_seed_reset_contract.py` read ADR-010, which is correctly
   excluded. Rather than dropping ~20 useful tests or diverging the client
   copy, the test was **fixed on `main`** (`72dd1cf`) to skip only when
   `docs/decisions/` is absent altogether; where the directory exists a
   missing or silent ADR still fails, and the path is anchored to the
   repository root rather than the working directory. All three behaviours
   were verified before pushing. The delivered file is byte-identical to
   `main`.
2. **The documented push target was stale.** `docs/CLIENT_DELIVERY.md`
   said to curate on `client-release` and run
   `git push client client-release:main`. `client-release` is `d89a090`,
   218 files, **no Command Center** — it stopped being the delivery branch
   and was never brought forward, so that command would have delivered a
   pre-Command-Center tree. The live delivery branch is
   `cc-1-command-center-progress`, which is what the client actually reads
   (`refs/heads/…` and `refs/pull/1/head` on their remote). The local
   gitignored `CLIENT_DELIVERY.md` was corrected: delivery branch, push
   command, the guard step, the fact that the guard reads a committed
   branch rather than the staged index (with the one-liner to check the
   index), and the new rule that a delivered test may not depend on
   undelivered material.

### Verification

- **Full client suite: exit 0** — 366-file tree, 170 test files, run against
  the development PostgreSQL through environment variables so no `.env` was
  written into the client tree, with `isolated_schema` keeping it off the
  real schema. Three legitimate skips: two pre-existing
  `DEMO_USERNAME/DEMO_PASSWORD not configured`, and the ADR test correctly
  reporting "no docs/decisions/ — curated delivery without ADRs".
- **Leakage check on the staged tree: 366 files, ZERO violations.** No
  `.env`, dump, log or debug artefact staged. (The guard's branch-based mode
  reads the committed tree, so the staged index was checked directly —
  the meaningful check before a commit.)
- `git diff --cached --check` reported two items, both proven
  byte-identical to `main` and therefore inherited rather than introduced:
  trailing whitespace at line 21 of the vendored
  `assets/fonts/ibm-plex-sans/LICENSE.txt` (third-party licence shipped
  verbatim — `assets/app.css` requires the font) and a blank line at EOF in
  `tests/test_report_installed_rtls.py`. Surfaced to the user before
  pushing; they chose to push as-is, since a third-party licence must not
  be edited and neither item came from this curation.
- **Client `main` untouched** at `aa1dd3cb13ac3b6c1e9191398b888a2be3c903ca`;
  the stale local `client-release` untouched at `d89a090` and absent from
  the client remote entirely. Only the one branch was pushed.
- Real development database unchanged at `012_vibration_contract_answers`.

## TECH-WORKSPACE-1 — CLOSED / IMPLEMENTED / VERIFIED / BROWSER-ACCEPTED / MERGED TO MAIN (TECH-WORKSPACE-MERGE-1, 2026-09-11)

Opened 2026-09-10 on branch `tech-workspace-1` at `main`/`tech-workspace-1`
common ancestor `27a6db0`, closed on that branch the same day, and merged
into `main` on 2026-09-11 by gate TECH-WORKSPACE-MERGE-1 (see the merge note
in the file header). `CLIENT-PC-SYNC-2` above remains `main`'s one real
active/queued gate — this section is a closed historical record, not a
supersession of it.

**Independent review (Codex, 2026-09-10): no blockers.** Reviewed and
confirmed before implementation: preserve every `scope.device_id` even when
absent from `FleetHealth`; a missing rollup defaults to NO_DATA; labels come
only from the scoped `list_device_paths(scope.device_ids, scope=scope)` —
never `hierarchy_code_index`/`list_all_devices`; EMPTY and UNRESTRICTED get
explicit, distinct handling (never a truthiness check on the same value); no
action controls and no second authorization predicate; one shared
`scope`/`rendered_at` per render; `populate_overview` moves consistently
from 10 to 11 Outputs; device navigation stays row_id-based (sort/filter
safe); zero My-RTLs label queries for an unrestricted or an empty scope. UX
placement confirmed: My RTLs renders ABOVE Fleet Condition.

### What was built (Slice 1 + Slice 2, not yet Slice-3 browser-verified)

- `components/my_rtls.py` (new) — `my_rtls_panel(rows)`: the card surface,
  reusing `components/card.py`'s `card_header` and `components/entity_table.py`
  exactly as the plant/transformer/device tables already do (`link_column_id`,
  `state_column_id`, `responsive=True`). Empty rows render a truthful "No
  RTLs are currently assigned to you." message rather than an absent panel —
  EMPTY and "no panel at all" (UNRESTRICTED) must read as different facts.
  No action controls anywhere in this module (ADR-016).
- `callbacks/listings.py` — `build_my_rtls_rows(scope, health)`: iterates
  `scope.device_ids` (never `health.devices`), defaulting a missing rollup to
  `aggregate_freshness([])`/NO_DATA — the Known ambiguity this gate flagged
  at open. Labels come from one `hierarchy_service.list_device_paths(device_ids,
  scope=scope)` call, skipped entirely when there are no ids (EMPTY costs
  zero queries, matching UNRESTRICTED's zero cost of never calling this
  function at all). `sort_my_rtls_rows_exception_first` — same NO_DATA >
  STALE > FRESH, then-code rule as every other table on this page.
  `my_rtls_section(scope, health)` — returns `None` for `scope.is_unrestricted`
  (ADR-004, never a role comparison); a restricted scope, EMPTY included,
  always renders a panel.
- `callbacks/listings.py::register` — `populate_overview` gained
  `Output("my-rtls", "children")` as an 11th Output (was 10); its early-return
  `(no_update,) * 10` became `(no_update,) * 11`. `my_rtls_section(scope,
  health)` is called inside the existing `build()` closure, from the SAME
  `scope`/`health` every other Layer-2 output already reads — no second
  query, no second freshness computation.
- `pages/plants_overview.py` — one new `html.Div(id="my-rtls")` slot, placed
  immediately above the Fleet Condition `html.Section` (the approved
  placement) and above Needs Attention.
- `assets/app.css` — `.my-rtls`/`.my-rtls__empty`, matching `.needs-attention`'s
  own spacing/empty-state rules rather than inventing new ones; `.card`
  supplies the surface.
- Tests: `tests/test_my_rtls.py` (new, 19) — row builder (every scope id
  covered even when absent from health, NO_DATA default, metrics-noun
  freshness label, scoped-label wiring, raw-id fallback, no
  `list_all_devices`/`hierarchy_code_index` reachable from the row builder,
  exception-first ordering), the rendering-condition function, and the
  component (columns, empty state, count wording, no action-control text,
  responsive wrapper). `tests/test_my_rtls_wiring.py` (new, 12) — page-slot
  presence/position/emptiness, Output-count (11, ending in `my-rtls`),
  Inputs/State unchanged, `(no_update,) * 11` on a non-overview route, the
  EMPTY-vs-UNRESTRICTED query-count contract (0 queries either way; 1 query
  for a real restricted+nonempty scope), one shared `FleetHealth` call, and
  Admin/General rendering left otherwise unaffected by the new slot.
  `tests/test_fleet_condition.py` — updated for the same Output-count/
  no_update-length change (10 → 11), consistently.

### Verification

- Focused: `tests/test_my_rtls.py` (19) + `tests/test_my_rtls_wiring.py` (12)
  — **31 passed**.
- Regression named by this gate, run together: `tests/test_authorization.py`
  + `tests/test_action_guard.py` + `tests/test_technician_operations.py` +
  `tests/test_device_scope.py` + `tests/test_route_scope.py` +
  `tests/test_credentialed_personas.py` — all passed.
- `python -m pytest -m "not db" -v` — **2957 passed** (was 2926 at gate open;
  +19 +12 new, zero regressions), exit 0.
- DB tests most relevant to this gate's own code path —
  `tests/test_device_paths_db.py` + `tests/test_route_scope_db.py` +
  `tests/test_scope_repository.py` — all passed.
- Full suite: `python -m pytest -q` — 6 failures, all in
  `tests/test_seed_integrity.py` and
  `tests/test_plant_monitoring_repository.py::TestRangeQueries`, none of
  which this gate's diff touches. Reproduced identically on the unmodified
  tree (`git stash` + re-run) — pre-existing dev-DB drift from the live
  simulator (row counts/date span exceed the original 30-day seed baseline),
  not a regression from this gate. Every DB test that exercises this gate's
  own code path (device scope, `list_device_paths`, the overview route)
  passed.
- `python scripts/build_context_pack.py --check` — CLEAN, both before and
  after this implementation pass.

### Slice 3 — Browser acceptance (real credentialed Technician session)

Ran against the real dev DB (`plant_monitoring_postgres`, port 5436, at
migration head `012_vibration_contract_answers`), the app started locally
(`python app.py`), and a real login as `demo.tech01`/`tech1234` (24 active
assignments) — not a mocked identity. Also spot-checked `admin`/`demo1234`
and `demo.general01`/`general1234`.

**One real defect found, reported before fixing, then fixed in this same
session:** clicking a My RTLs row highlighted the cell (`active_cell` was
set) but never navigated — `callbacks/listings.py` had no
`Input("my-rtls-table", "active_cell")` callback, unlike the other three
listing tables which each have one. Confirmed via screenshot (cell
highlighted, `window.location.pathname` unchanged) and via the server log
showing no `routing` warning at all for the click (the route callback never
fired). Neither `tests/test_my_rtls.py` nor `tests/test_my_rtls_wiring.py`
had caught it — both exercise the row builder and the page-level wiring,
neither exercises an actual row click.

**Fix:** `navigate_from_my_rtls_table`, registered immediately after
`navigate_from_devices_table`, reusing `device_row_target` verbatim (the My
RTLs identity column id is `"device"`, the same as `devices-table`'s, so no
second target function was needed). One companion fix was required:
`tests/test_equipment_selector.py`'s `test_every_callback_id_exists_in_some_layout`
guard failed because `my-rtls-table` — like `device_operations_panel`'s and
the three admin panels' ids before it — only exists inside a
callback-rendered component, never a static layout; added
`collect_ids(my_rtls_panel([...one row...]))` to that test's
`PAGE_LAYOUT_IDS` union, the same pattern already used for those four.
`tests/test_my_rtls_wiring.py::TestMyRtlsRowNavigation` (new, 6): callback
wired to `my-rtls-table` with `allow_duplicate=True`; identity-column click
navigates to the correct device; `row_id` (not the post-sort/filter `row`
index) drives navigation; a non-link column click is `no_update`; a missing
`active_cell` is `no_update`; a `None` `row_id` is `no_update`.

**Full acceptance checklist:**

| Check | Result |
|---|---|
| Login lands on `/plants` | Confirmed via the real flow: visiting a protected route while logged out preserves `pathname`; the login form renders there; signing in re-triggers routing on that same pathname, now authenticated. (Visiting the literal `/login` URL and signing in from there does not redirect — pre-existing behaviour in `callbacks/auth.py`/`routing.py`, reproduces identically for `admin`, untouched by this gate's diff — noted, not fixed, out of scope.) |
| My RTLs above Fleet Condition | Confirmed |
| Only assigned RTLs appear | Confirmed — 24 rows for `demo.tech01`, matching `list_active_device_ids_for_user(104)` exactly |
| Assigned RTLs with NO_DATA still appear | Not live-verified — the dev DB currently has 0 NO_DATA/STALE devices fleet-wide (all 120 fresh, no live simulator running); user chose to rely on `tests/test_my_rtls.py`'s unit coverage instead of mutating dev data for this one check |
| Exception-first ordering | Sort mechanics confirmed (Plant-column sort re-ordered correctly with row identity intact); the NO_DATA-before-STALE-before-FRESH exception order itself was not visually demonstrable live for the same all-fresh-data reason above — covered by `TestExceptionFirstOrdering` |
| One-click navigation after sort/filter | Confirmed working after the fix — re-clicked the same RTL (29118) that failed before the fix; landed on `/devices/plant-29-t2-d1` |
| Assigned device shows Manage RTL + allowed actions | Confirmed — Program RTL, Message Forwarding, Deactivate RTL all present |
| Forged/unassigned device URL refused | Confirmed — both an unassigned real device and a nonexistent device_id get the identical "No access" panel; server log shows clean warnings, no leakage |
| Needs Attention present and scoped | Confirmed |
| Admin Overview unchanged | Confirmed — 120 fleet-wide, no My RTLs panel, full admin sidebar/nav intact |
| General Overview unchanged | Confirmed — same, no My RTLs panel |
| 1366×768 / 1440×900 overflow | Confirmed clean at both (`document.documentElement.scrollWidth == clientWidth` at both widths, no visual clipping) |

### Gate-close verification (this session, after the navigation fix)

- Focused: `tests/test_my_rtls.py` + `tests/test_my_rtls_wiring.py` +
  `tests/test_table_navigation.py` + `tests/test_equipment_selector.py` +
  `tests/test_fleet_condition.py` — **138 passed**.
- Regression named by this gate: `tests/test_authorization.py` +
  `tests/test_action_guard.py` + `tests/test_technician_operations.py` +
  `tests/test_device_scope.py` + `tests/test_route_scope.py` +
  `tests/test_credentialed_personas.py` — all passed.
- `python -m pytest -m "not db"` — **2963 passed** (was 2926 at gate open;
  +37 new across `test_my_rtls.py`/`test_my_rtls_wiring.py`, zero
  regressions), exit 0.
- DB tests most relevant to this gate's own code path —
  `tests/test_device_paths_db.py` + `tests/test_route_scope_db.py` +
  `tests/test_scope_repository.py` — **60 passed**.
- `python scripts/build_context_pack.py` — CLEAN, `CURRENT_STATE.md`
  refreshed. `python scripts/build_context_pack.py --check` — CLEAN.
- `git diff --check` — clean, no whitespace/conflict-marker issues.
- Full suite: `python -m pytest -q` — same **6 pre-existing failures**
  as recorded at gate open, all in `tests/test_seed_integrity.py` and
  `tests/test_plant_monitoring_repository.py::TestRangeQueries`. None of
  this gate's diff touches those files or their code paths. Re-confirmed
  via `git stash` + re-run against the unmodified tree in an earlier pass
  this session — identical failures reproduce with none of this gate's
  code present, so they are dev-DB drift from the live simulator (actual
  row counts/date span now exceed the original 30-day seed baseline), not
  a regression from this gate. Documented here rather than fixed — out of
  this gate's scope.

### Commit/push permission: GRANTED (2026-09-10)

User authorized closing this gate: commit all TECH-WORKSPACE-1 files
(excluding the untracked, unrelated `debug.log`) and push branch
`tech-workspace-1`. **At the time this permission was granted, the gate was
not yet merged to `main`** — `main` still declared `CLIENT-PC-SYNC-2` as its
real active gate. **Update (2026-09-11, TECH-WORKSPACE-MERGE-1):** this
branch has since been merged into `main`; `CLIENT-PC-SYNC-2` remains `main`'s
active gate unchanged (see the merge note in this file's header). Nothing in
the client delivery repo was touched by either gate.

Full current-state findings, recommended UX structure, risks and the slice
plan were produced in the planning session and relayed to the user directly
(not duplicated verbatim here); what follows is the frozen, user-approved
scope this gate now executes against.

## Task

Give the Technician persona direct visibility of and access to their
assigned RTLs from the existing Fleet Overview (`/plants`), without
widening any permission and without adding a second place authorization is
decided.

Concretely: a "My RTLs" panel on `pages/plants_overview.py`, rendered when
`current_device_scope()` is a restricted scope (`not scope.is_unrestricted`
— never a role comparison, per ADR-016's rule against a second permission
table), listing every device in `scope.device_ids` with its freshness state
and a one-click link to `/devices/{device_id}` via `routes.device_href`. No
action controls in the panel — the existing device page already mounts the
shared `device_manage_drawer()` for exactly the personas `may_action`
approves (ADR-016, `08e44af`), and this gate must not create a second entry
point to those three actions.

Decisions frozen for this gate (user-approved 2026-09-10, supersede the
planning session's own recommendations where they differ):

- **D1 — deferred.** No per-RTL recent-event marker in this gate. Events
  stay in the Notification Center / Command Center only.
- **D2 — keep both.** My RTLs and the existing Needs Attention panel both
  render for a Technician; the overlap (both exception-first) is accepted,
  not resolved by suppressing either.
- **D3 — no cap.** The work list is uncapped — it is the Technician's
  complete assignment set, not a fleet-wide sample, so ADR-011-style
  disclosure-with-truncation does not apply here.
- **D4 — deferred.** No signed-in identity line added to the sidebar in
  this gate.
- **D5 — deferred.** No account-level message-forwarding status line added
  to the panel in this gate.
- **No new ADR** for this gate unless implementation surfaces a genuinely
  new architectural rule not already covered by ADR-002/ADR-004/ADR-016;
  the mechanism this gate uses (branch on `scope.is_unrestricted`, reuse the
  existing operational-action entry point) is already fully licensed by
  those three and documenting it again would not be a new decision.
- **Admin/General must render behaviorally and visually unchanged** by this
  gate — not asserted as byte-identical markup. A wiring test comparing
  literal Dash tree equality before/after is the wrong test for this; assert
  on the specific outputs (plants table rows/columns, KPI cards, Needs
  Attention, Administration block) being unaffected and on the new panel
  slot being `None`/absent for those two roles.

## Relevant files

Existing files this gate reads and expects to modify (read-verified this
session):

- `pages/plants_overview.py` — layout only; gains one new panel slot.
- `callbacks/listings.py` — `populate_overview` (`Output` list currently 10
  wide, ends `(no_update,) * 10` on the early return — both must move
  together with any new Output added); `administration_section` is the
  precedent for a capability/scope-gated section that skips its query
  entirely rather than building and discarding.
- `components/fleet_summary.py` — `fleet_subtitle_text`; a scoped variant
  needed for a restricted persona.
- `components/needs_attention.py` — read for the exception-first
  three-key row convention (`_state`/`_severity`/`id`) this gate's new row
  builder must match, not duplicate.
- `components/entity_table.py` — the `link_column_id` + `active_cell`
  navigation idiom every existing listing table uses.
- `routes.py` — `device_href`; identifiers are never hand-interpolated.
- `services/authorization.py` — `ROUTE_POLICY`, `CAPABILITY_POLICY`,
  `ACTION_POLICY`; this gate must not add or change a row in any of the
  three.
- `services/device_scope.py` — `DeviceScope`, `scope_for`,
  `current_device_scope`; the sole authority this gate's rendering
  condition is derived from (ADR-004).
- `services/action_guard.py` — `may_action`/`require_action`; read-only
  reference, not called from the new panel.
- `services/monitoring_service.py` — `FleetHealth`, `aggregate_freshness`,
  `severity_rank`; the rollup the new row builder reads, never recomputes.
- `services/hierarchy_service.py` — `list_device_paths`; the one batched
  ADR-008 read path for plant/transformer/device labels.
- `repositories/plant_monitoring_repository.py` —
  `list_active_device_ids_for_user`; already the sole source of
  `scope.device_ids` for a technician, unchanged by this gate.
- `components/device_operations.py`, `callbacks/device_manage.py`,
  `pages/device_dashboard.py` — the existing, unmodified reachability path
  (ADR-016) this gate's rows link into; a diff touching these three means
  the gate has gone wrong.
- `components/app_sidebar.py` — read-only reference for the ADR-004/ROLE-2
  visibility convention; no nav key added in this gate (D4 deferred).
- `docs/decisions/ADR-002-fleet-attention-is-freshness-only.md` — attention
  is freshness only; this gate must not invent an alarm/threshold concept.
- `docs/decisions/ADR-004-device-scope-is-not-user-selectable.md` — no
  scope selector; the panel is a read-only indicator of `scope_for()`.
- `docs/decisions/ADR-016-operational-actions-are-shared-administration-is-not.md`
  — the one authorized entry point to the three device actions; this gate
  reuses it and does not create a second one.

Not yet created (do not exist at gate-open, so deliberately not
backtick-bulleted above — `scripts/build_context_pack.py`'s Relevant-files
check would fail a citation to a path that does not exist yet): a new
`components/my_rtls.py` presentation component, a `my_rtls_section` /
row-builder pair added to `callbacks/listings.py`, and
`tests/test_my_rtls.py` + `tests/test_my_rtls_wiring.py`.

## Required tests

- `python -m pytest -m "not db" -v` — must stay at 2926 passed or higher
  after every slice; never allowed to go red.
- New, slice 1: `tests/test_my_rtls.py` — pure row-builder/component tests
  (structural/rendered Dash assertions, never `repr()` comparisons).
- New, slice 2: `tests/test_my_rtls_wiring.py` — scope branching
  (`EMPTY` vs `UNRESTRICTED` must take different code paths, never
  distinguished by truthiness), query-count assertion (one
  `list_device_paths` call per render, zero when unrestricted), Output-count
  assertion on `populate_overview`.
- Regression, run unchanged every slice: `tests/test_authorization.py`,
  `tests/test_action_guard.py`, `tests/test_technician_operations.py`,
  `tests/test_device_scope.py`, `tests/test_route_scope.py`,
  `tests/test_credentialed_personas.py` — the proof that no permission
  moved.
- At gate close (needs Docker + seeded DB): `python -m pytest -v`, plus a
  real credentialed-Technician browser check per
  `tests/test_credentialed_personas.py`'s logins.

## Non-goals (explicit)

- No `ROUTE_POLICY`, `CAPABILITY_POLICY`, or `ACTION_POLICY` row added,
  removed, or changed.
- No new route (`/my-rtls` or similar) and no new sidebar nav key.
- No scope selector, no admin "view as technician", no per-role UI branch
  that compares `role` directly instead of going through `DeviceScope`.
- No action controls (Program RTL / Message Forwarding / Deactivate) in
  the new panel — those stay reachable only through the existing device
  page entry point.
- No registration, assignment management, or user management surface
  opened to a non-administrator.
- No alarm/threshold/warning-critical concept invented anywhere — this
  system has none (ADR-001, ADR-002; `MonitoringCondition` is always
  `UNKNOWN`).
- No commit, no push, until this gate's own "Commit/push permission" field
  is updated to GRANTED.

## Known ambiguities

- A Technician's assigned RTL that has never reported (or sits under an
  inactive transformer) may be absent from `FleetHealth.devices`. The row
  builder must iterate `scope.device_ids`, not `health.devices`, and
  default a missing rollup to `aggregate_freshness([])` (NO_DATA) — the
  same rule `build_plant_rows` already follows. Flagged here so slice 1's
  tests are written against this case deliberately, not discovered by a
  gap in coverage.
- `rtl_active_state` (administrative active/inactive) is a separate axis
  from `devices.status`/freshness, and there is currently no bulk reader
  for it. This gate's panel ships with no active-list column and makes no
  claim about it; a deactivated-but-still-listed RTL is expected, not a
  defect, until a future gate decides whether to add one.

---

## CLIENT-SYNC-3 — CLOSED / DELIVERED / REMOTE-VERIFIED

Date: 2026-09-11. Development baseline `fa69c9c66f3d28d9bb6620040a93ffba918022ef`
(the TECH-WORKSPACE-MERGE-1 commit, above). The accepted milestone is
delivered to the client repository.

**Delivered client branch:** `cc-1-command-center-progress`
**Client commit:** `983c17169a0cedd2282a0df4731228e0b05feac7` — subject
"feat(client): synchronize technician workspace milestone", parent
`3f21c3a000de5026868c2031eb865569c368e509`. Local `HEAD` and the client
remote's `refs/heads/cc-1-command-center-progress` both verified to match
this SHA.

### What was delivered

Exactly the 8 runtime files that changed between the dev baseline this
branch was last synced from (`72dd1cf`, CLIENT-SYNC-2B) and the current dev
baseline (`fa69c9c`) — established by diffing the entire repository between
those two commits, not by reasoning about the merge alone, so nothing else
was missed: `assets/app.css`, `callbacks/listings.py`,
`components/my_rtls.py` (new), `pages/plants_overview.py`,
`tests/test_equipment_selector.py`, `tests/test_fleet_condition.py`,
`tests/test_my_rtls.py` (new), `tests/test_my_rtls_wiring.py` (new) — the
Technician "My RTLs" work-list panel (TECH-WORKSPACE-1), copied
byte-identical from dev `main` via `git checkout fa69c9c -- <paths>` and
verified identical afterward. 8 files changed, 749 insertions, 3 deletions.

**Excluded, same never-curate / undelivered-dependency precedent
CLIENT-SYNC-2B established:** `docs/context/ACTIVE_GATE.md`,
`docs/context/CURRENT_STATE.md`, `docs/context/PROJECT_LEDGER.md`,
`scripts/build_context_pack.py` (never delivered), and its new test
`tests/test_context_pack_gate_guard.py` (exercises the undelivered script —
CLIENT-SYNC-2B's rule that a delivered test may not depend on undelivered
material). The five client-only documents, `README.md`,
`GETTING_STARTED.md`, `.gitignore`/`.gitattributes`/`.env.example` were left
untouched.

### Verification

- Full client suite (real dev Postgres via env vars on the command line, no
  `.env` written into the client tree): **6 failed, 3623 passed, 3
  skipped**. All 6 failures (`tests/test_seed_integrity.py`,
  `tests/test_plant_monitoring_repository.py::TestRangeQueries`) reproduced
  identically on dev `main` itself against the same shared database —
  pre-existing dev-DB drift from the live simulator (already documented in
  TECH-WORKSPACE-1's own gate-close record above), not introduced by this
  curation.
- Leakage check (`scripts/check_client_release.py`'s `violations()`, run
  against the client tree's actual `git ls-files` output including the
  newly staged files): **NONE**.
- `git diff --check` (staged): clean.
- **Client `main` untouched** at `aa1dd3cb13ac3b6c1e9191398b888a2be3c903ca`;
  local `client-release` untouched at `d89a09035ffd259c00eb4f2138ec1f42cfb97505`.

## CLIENT-PC-SYNC-2 — SUPERSEDED BEFORE EXECUTION (2026-09-11, by CLIENT-PC-SYNC-3)

**Never started.** Superseded, not completed — no client laptop was touched
under this gate. Superseded because CLIENT-SYNC-3 (above) moved the client
delivery branch forward from `3f21c3a` to `983c171` after this gate was
queued, so a client-laptop sync against `3f21c3a` would now install a stale
milestone. Retained below verbatim as the historical record of what was
queued; CLIENT-PC-SYNC-3 below carries the identical procedure re-targeted
at the current milestone.

Set 2026-09-07, once CLIENT-SYNC-2B was delivered and remote-verified above.
Not started. Scope: update the **client's own laptop** to this milestone over
Remote Desktop (`PROJECT_LEDGER.md` §7a), migrate its database
non-destructively, then browser-smoke the result before demonstrating it.

It must:

- **Pull `cc-1-command-center-progress` at `3f21c3a…`** on the client
  machine — not `main`, which is deliberately behind, and not the stale
  `client-release`.
- **Verify the target environment BEFORE migrating**, the same way
  LOCAL-DB-CATCHUP-1 did on the development machine: confirm which
  host/port/database/schema that laptop's Alembic actually points at, and
  confirm it is the client's local development database. Check first,
  migrate second.
- **Back up that database before touching it**, and validate the backup is
  readable — not merely non-empty.
- **`pip install -r requirements.txt`** for `tzdata` and `fpdf2`.
- **Migrate non-destructively: `alembic upgrade head` only.** No reset, no
  purge, no reseed, no `--reset` — the client laptop's existing data must
  survive, and the README now says so explicitly. Record row counts before
  and after and compare them.
- **Browser-smoke what the upgrade makes reachable**: login, Fleet Overview,
  Command Center, the device workflow, reports with CSV/PDF export, and the
  three configuration panels — leaving thresholds unconfigured and vibration
  answers unanswered rather than inventing client values.
- **Leave the simulator OFF** unless deliberately demonstrating it, and turn
  it back off afterwards. No screen may imply a physical RTL was programmed.
- Report any defect found rather than fixing it on the client machine.

## CLIENT-PC-SYNC-3 — CLOSED / PASS

Set 2026-09-11, superseding CLIENT-PC-SYNC-2 (above) before it was executed:
CLIENT-SYNC-3 moved the client delivery branch forward to `983c171` after
CLIENT-PC-SYNC-2 was queued against `3f21c3a`. Not started. Scope is
otherwise identical to CLIENT-PC-SYNC-2 — update the **client's own laptop**
to this milestone over Remote Desktop (`PROJECT_LEDGER.md` §7a), migrate its
database non-destructively, then browser-smoke the result before
demonstrating it.

It must:

- **Pull `cc-1-command-center-progress` at `983c171…`** on the client
  machine — not `main`, which is deliberately behind, and not the stale
  `client-release`.
- **Verify the target environment BEFORE migrating**, the same way
  LOCAL-DB-CATCHUP-1 did on the development machine: confirm which
  host/port/database/schema that laptop's Alembic actually points at, and
  confirm it is the client's local development database. Check first,
  migrate second.
- **Back up that database before touching it**, and validate the backup is
  readable — not merely non-empty.
- **`pip install -r requirements.txt`** for `tzdata` and `fpdf2`.
- **Migrate non-destructively: `alembic upgrade head` only.** No reset, no
  purge, no reseed, no `--reset` — the client laptop's existing data must
  survive, and the README now says so explicitly. Record row counts before
  and after and compare them.
- **Browser-smoke what the upgrade makes reachable**: login, Fleet Overview,
  Command Center, the device workflow, **Technician "My RTLs" work list and
  one-click navigation from it to an assigned device** (TECH-WORKSPACE-1 —
  the milestone this sync newly adds over CLIENT-PC-SYNC-2's target),
  reports with CSV/PDF export, and the three configuration panels — leaving
  thresholds unconfigured and vibration answers unanswered rather than
  inventing client values.
- **Leave the simulator OFF** unless deliberately demonstrating it, and turn
  it back off afterwards. No screen may imply a physical RTL was programmed.
- Report any defect found rather than fixing it on the client machine.

### Verification — reported by the user who performed the sync on the client laptop (2026-09-15)

This procedure ran on the client's own laptop over Remote Desktop, a
machine outside this session's reach. What follows is the user's direct
report of what was done and observed there; it has not been, and cannot
be, independently re-run or re-verified from this repository/session —
recorded as reported, per `SOURCE_AUTHORITY.md` rung 5 (our conversation)
being the only rung this session can reach for facts about a system it
does not control.

- Client branch/SHA confirmed pulled: `cc-1-command-center-progress` @
  `983c17169a0cedd2282a0df4731228e0b05feac7` — matches the `983c171…`
  target this gate names above and `PROJECT_LEDGER.md`'s recorded client
  delivery pointer.
- Database migrated non-destructively `007_audit_log` →
  `012_vibration_contract_answers` (`alembic upgrade head` only).
- Protected/pre-existing row counts unchanged before vs. after the
  migration.
- Administrator browser acceptance: PASS.
- Technician (`demo.tech01`) browser acceptance: PASS.
- 24 assigned RTLs visible to the technician.
- "My RTLs" navigation to an assigned device works (TECH-WORKSPACE-1, the
  milestone this sync newly adds over CLIENT-PC-SYNC-2's target).
- Access to an unassigned RTL is refused for the technician.
- No Administration UI leakage to the technician.
- `RTL_PROGRAMMING_SIMULATOR_ENABLED=False` on the client laptop — simulator
  left OFF.
- No defect reported.

**Result: CLOSED / PASS.** No application code was touched by this gate —
it is an environment/verification gate (same shape as `LOCAL-DB-CATCHUP-1`
above), so this closure only updates `docs/context/ACTIVE_GATE.md` and
`docs/context/PROJECT_LEDGER.md`. Per explicit instruction, no new
implementation gate is opened by this closure.

## CMD-AUDIT-VIS-1 — CLOSED / PASS

Opened and closed 2026-09-15. The shared RTL device page's existing protected
history section now identifies Command & audit history: persisted command type,
requester, timestamp, lifecycle, safe result/error and execution mode, plus
device-scoped `audit_log` entries. Audit payload JSON stays internal. The
repository applies the existing neutral device-id scope in SQL by joining the
audited device; the service also refuses an out-of-scope device before a query.

The callback resolves both identity and `DeviceScope` from the trusted server
session and reuses `PROGRAM_RTL` visibility policy: Administrator any RTL,
Technician current assignment only, General User none. Browser `auth-store`
data is a rerender trigger only. Command lifecycle that moves past queued is
explicitly labelled Simulation; the page continues to say physical RTL delivery
is not connected. No command dispatch, device transport, acknowledgement or
lifecycle mutation was added.

Verification: 115 focused non-DB tests passed (27 deselected); the private-temp
non-DB suite passed (2983 passed, 687 deselected); context checks and
`git diff --check` passed. PostgreSQL was intentionally not started, so
DB-marked repository coverage remains unrun. Browser acceptance was not run
because neither Dash nor PostgreSQL was already running.

## ALARM-ACK-1 — CLOSED / PASS

Implemented and verified 2026-09-15. Notification Center now presents the
internal acknowledgement state of persisted reportable alarm events and gives
Administrator and assigned Technician users a scoped acknowledgement action.
General User remains read-only. Acknowledgement persists actor and timestamp
on `device_events` and writes `ALARM_ACKNOWLEDGED` to `audit_log` atomically;
it never clears/resolves an alarm and adds no external delivery or hardware
transport. Freshness-derived notifications remain non-acknowledgeable.

Focused pure tests, context verification, and the private-basetemp non-DB
suite passed. Database-marked persistence/migration tests were added but not
executed because PostgreSQL was intentionally offline; no database or Docker
state was started. Physical RTL acknowledgement remains unimplemented.

## COMMAND-DISPATCH-1 — CLOSED / PASS

Implemented and verified 2026-09-15. The existing `DeviceTransport` seam and
`rtl_commands` lifecycle now have an explicit fail-closed dispatch boundary:
no transport leaves commands queued, while an injected transport can drive the
existing SENT, ACKNOWLEDGED, SUCCEEDED, FAILED, and TIMED_OUT transitions.
`DispatchPolicy` provides validated timeout/retry configuration with retries
disabled by default; explicit retry counts are refused until client-approved
semantics exist. No protocol, payload, endpoint, ACK format, or physical RTL
behavior was invented. `SimulatorTransport` remains development/test-only.

Focused dispatch-policy/simulator tests, context verification, and the
private-basetemp non-DB suite passed. Database-marked lifecycle tests were not
run because PostgreSQL was intentionally offline; no database or Docker state
was started.

## ALARM-ACK-013-FIX — CLOSED / PASS

Opened and closed 2026-09-16. Corrected migration
`013_alarm_acknowledgement`'s `op.create_check_constraint` invocation: its
`table_name` and `condition` positional arguments had been reversed. The
resulting PostgreSQL constraint remains exactly
`(acknowledged_at IS NULL) = (acknowledged_by_user_id IS NULL)` on
`device_events`. Added an operation-level regression test that asserts the
Alembic call's exact positional order, and moved the migration contract tests
to the shared `isolated_schema` fixture.

Verification: migration tests 4 passed; affected ALARM-ACK-1,
CMD-AUDIT-VIS-1, COMMAND-DISPATCH, and lifecycle DB tests 69 passed; non-DB
suite 3065 passed; `alembic heads` reported the single head
`013_alarm_acknowledgement`; context-pack close check and `git diff --check`
passed. No real development database upgrade was run.

## AUDIT-VIEWER-1 — CLOSED / PASS

Opened and closed 2026-09-16. Added the Administrator-only `/admin/audit-log`
route, sidebar entry, trusted callback capability check, and a safe,
bounded read projection of existing `audit_log` rows. The repository joins the
existing actor to `users`, retaining a `System` fallback for null actors, and
never returns `old_values` or `new_values`. The page has no mutation controls;
the shared table's native filter row and paging are the only exploration aids.

Verification: 165 focused authorization/presentation tests passed; 56
isolated-schema viewer/audit-wiring/device-history DB tests passed; full
non-DB suite 3076 passed. Browser verification as the configured Administrator
confirmed the sidebar route, newest-first rows, five requested columns, and
read-only presentation. Context-pack close check and `git diff --check`
passed.

## Historical next implementation gate: NONE

### RTL-PROG-VIS-1 — CLOSED / PASS

Opened and closed 2026-09-15. The shared device page now has a compact
Programming Activity section, reached naturally from the Technician's My RTLs
workflow or any Administrator device dashboard. A scoped, windowed repository
reader joins the persisted request, command and requester-display data without
an N+1 pattern; the read service and callback apply the current trusted
`DeviceScope` before querying and in SQL. The existing `PROGRAM_RTL` policy is
reused: Administrator is any-device, Technician is current-assignment-only,
and General User is denied. Browser `auth-store` data is trigger-only; trusted
server identity decides visibility.

The UI names queued requests truthfully, labels every currently progressed
lifecycle as development Simulation, exposes safe result/error text, and says
plainly that physical RTL delivery is not connected. Recording a new request
refreshes the activity display; no mutation, transport, protocol, retry, or
physical acknowledgement was added. No migration was required.

Verification: 111 focused non-DB tests passed (27 deselected); the full
non-DB suite passed with an isolated private pytest base directory (2979
passed, 687 deselected); `python scripts/build_context_pack.py --check` and
`git diff --check` passed. PostgreSQL was intentionally not started, so the
new isolated-schema repository test remains DB-marked and unrun here. Browser
acceptance was not run because neither a local Dash process nor the project
PostgreSQL service was already running.

**The gap this closes.** Both Administrator and Technician can already
create RTL programming requests (the Program RTL drawer, `PROGRAM_RTL`
action guard, `rtl_programming_service.py`), and the backend already
persists and reconciles the full request/command lifecycle
(`rtl_programming_requests` — `master_msisdn`, `requested_by`,
`requested_at`, `status`, `completed_at`, `error_message` —
`repositories/plant_monitoring_repository.py`; `rtl_commands` lifecycle via
`services/rtl_command_service.py`, RTL-PROG-EXEC-1). None of that is
exposed as a proper Programming Activity/History UI: the only existing
reader, `list_recent_programming_requests(device_id, limit=5)`, is a single
device's own drawer read-back, not a work-list or history screen, and there
is no scope-aware or batched reader for it (unlike `list_device_paths`
for hierarchy labels).

**What RTL-PROG-VIS-1 should expose, when opened:**

- Per-RTL latest programming status.
- Requested time and requester (resolve `requested_by` to a display
  identity, not a bare user id).
- RTL Master MSISDN.
- Completion/result/error where available (`completed_at`,
  `error_message`, already persisted).
- Recent programming history (not just the latest request per RTL).
- Scope-safe Technician visibility — through `DeviceScope`/
  `current_device_scope()` exactly as every other gate does (ADR-004);
  no second visibility predicate.
- Later, optional: an Admin fleet-level programming summary — explicitly
  deferred past this gate's own first slice, not assumed to ship with it.

**Explicitly not decided by this note:** UI placement (its own page vs. a
Fleet Overview panel vs. folded into Command Center), whether it needs a
new scope-aware repository reader or reuses/extends an existing one, exact
column set, and whether it needs its own ADR. Whoever opens this gate
decides those, the same way every other gate in this file states its task
at open rather than here.

---

## CLIENT-SYNC-2B — original queued scope (2026-09-07, SUPERSEDED)

Set 2026-09-07, once CLIENT-SYNC-2A-FIX was verified above. Not started.
Scope: **curate runtime parity into the client branch** — carry the
accepted development milestone into `client-release` and push it to
`powerplant-dashboard-client`, then prepare the weekly Remote Desktop demo.

CLIENT-SYNC-2A established that the honest options are parity or surgery:
the 79-file runtime set (28 missing + 51 differing) plus 5 migrations and
~112 test-file operations, or hub-file edits to `app.py` /
`pages/plants_overview.py` that diverge client source from dev permanently
and must be re-applied every week. **Whoever opens this gate decides that
first** — everything else follows from it.

It must:

- Copy in dependency order — `config/` → `services/` → `components/` →
  `pages/` → `callbacks/` → `app.py` **last**, since it is the import hub
  and copying it early leaves the tree unimportable.
- **Preserve the five client-only documents** listed above; they must
  survive the sync.
- Ship migrations 008–012 and instruct a **non-destructive
  `alembic upgrade head`** — no reset, no reseed — plus the two new
  dependencies. The client README currently documents a `--reset` refresh
  flow and needs an "upgrading an existing database" section.
- Keep the simulator **default-off**: the `.env.example` line stays
  commented, and the production fail-closed guard must survive curation
  intact. Including the code inert is cheaper and safer than the `app.py`
  surgery removing it would require.
- Decide the docstring/comment terminology policy left open above.
- Run `python -m pytest -v` (green) **and**
  `python scripts/check_client_release.py` (exit 0) before any push, then
  read `git ls-tree -r --name-only client-release` by hand — the guard is
  a second check, never a replacement for the curation judgement.

---

## CLIENT-SYNC-2 — original queued scope (2026-09-07, SUPERSEDED)

Superseded by CLIENT-SYNC-2A / CLIENT-SYNC-2A-FIX / CLIENT-SYNC-2B above,
which split this single gate into inspect → prepare the boundary →
curate. Retained because its constraints were not weakened by that split
— every one of them still binds CLIENT-SYNC-2B.

Set 2026-09-07, once LOCAL-DB-CATCHUP-1 was verified. Scope: curate the
accepted current development milestone into the client delivery
repository/branch and prepare the next weekly client demo
(`docs/context/PROJECT_LEDGER.md` §7a — accepted development is
synchronized to the client GitHub repo at suitable weekly milestones, and
demonstrated on the client's own laptop by Remote Desktop).

**This is a CURATION gate, not a mirror.** Whoever opens it must:

- **Inspect the existing client-delivery workflow and CLIENT-SYNC-1's own
  provenance FIRST** — `docs/CLIENT_DELIVERY.md`, the `client-release` /
  `client-demo-1` branches, and `scripts/check_client_release.py` — before
  deciding anything. The curation policy already exists; this gate follows
  it rather than inventing a new one.
- **Determine exactly which accepted changes since the last client sync
  are suitable for demonstration**, item by item, with a reason for each
  inclusion and exclusion.
- **Preserve the existing `client-release` leakage safeguards unchanged**:
  the never-curate list, the curation-by-hand model, and
  `scripts/check_client_release.py` still govern every push.
- **Do NOT blindly mirror the development repository.**
- **Keep development-only/internal tooling, context documents, secrets,
  debug files and simulator enablement OUT of the client delivery** unless
  the existing curation policy explicitly permits them.
- Simulation **may** be demo-capable, but must remain clearly
  development-only and **default-off** — the RTL-PROG-SIM-1 boundary
  (explicit opt-in, fail-closed under `APP_ENV=production`) must survive
  curation intact, and no client-facing screen may imply a physical RTL
  was programmed.

---

## Next implementation gate: LOCAL-DB-CATCHUP-1 — QUEUED, NOT STARTED

Set 2026-09-07, once RTL-PROG-SIM-1's implementation was verified above.
Not started. Scope: deliberately and **non-destructively** upgrade the
real development database from migration `007_audit_log` to the current
head `012_vibration_contract_answers`, then browser-smoke the operational
and configuration flows added since `007`. Five migrations have
accumulated behind the real dev DB (008 `rtl_commands`, 009 command
lifecycle, 010 forwarding auto-disable override, 011 temperature
threshold config, 012 vibration contract answers) because every gate
since deliberately left it alone — the suite exercises them through the
`isolated_schema` fixture only, never the real `plant_monitoring` schema.
This gate is that catch-up, done as its own careful step.

It **must**:

- **Take no reset or reseed action.** Not `--reset`, not `--purge`, not a
  re-run of `db/seed_plant_monitoring.py` or `db/seed_admin_demo.py`.
  This is `alembic upgrade` only.
- **Verify the environment and database target BEFORE migrating** —
  confirm which host/port/database/schema `alembic` is actually pointing
  at (the local `plant_monitoring_postgres` container, port 5436), and
  confirm it is not a client or production target. Check first, migrate
  second.
- **Preserve existing dev data.** Existing plants/transformers/devices/
  readings/users/assignments/audit history must survive; record row
  counts before and after and compare them.
- **Verify the 007 → 012 upgrade** — `alembic current` before and after,
  the five expected migrations applied in order, `alembic heads` still a
  single head, and the new tables actually present in the real schema.
- **Browser-smoke the newly reachable flows**: C08 auto-disable override
  UI, temperature threshold UI, vibration contract UI, and the simulated
  programming flow (which requires setting
  `RTL_PROGRAMMING_SIMULATOR_ENABLED` locally — see RTL-PROG-SIM-1 above
  — and must be turned back off afterwards).
- **Keep `debug.log` excluded** from any commit, as every gate has.

This is an environment/verification gate, not a feature gate: it should
add no application code unless the smoke test finds a real defect, in
which case that defect is the finding and fixing it is a separate
decision.

---

## POWER-MASTER-PLAN-1 — CLOSED / MASTER PLAN ADOPTED (prior gate)

Date: 2026-09-05

Documentation-only gate. Validated `docs/context/Power_RTL_Master_Build_Plan_2026-09-04.md`
against the repository (AGENTS.md, ADR-017–020, `PROJECT_LEDGER.md`,
`REQ-1B_Implementation_Gap_Matrix.md`, `REQ-3I_Clarification_Register.md`,
`docs/RTL_FUNCTIONAL_SPEC_EXTRACT.md`), corrected two inaccuracies found in
the plan (Client Clarification Pack priority ordering had C-05 ahead of
C-08 — reversed of `REQ-3I` §5's authoritative ranking; BR015 was
overstated as PARTIAL rather than `REQ-1B`'s NOT IMPLEMENTED), corrected a
stale checkpoint SHA and a stale "NOT STARTED" clarification-pack status in
`PROJECT_LEDGER.md`, and resolved a pre-existing internal ordering
inconsistency in `docs/context/CLIENT_QUESTIONS.md`. No application code
touched. The master plan is now the adopted roadmap; this repository's
mature application/integration foundation is unchanged by this gate.

At the time this gate closed, the next implementation gate was NONE —
awaiting client clarification, with C-08 and C-05 as the two leading
blockers. **That has since changed**: see the C08-BASELINE-1 section above,
which is now current.

## RTL-IF-4 — Notification delivery abstraction (prior gate, CLOSED / PUSHED / REMOTE-VERIFIED)
Branch: `main`, baseline `e3f49b14e4ea122190f9081b15967ddae00657ea`
Commit: `0b2a4d5ec2c88d5a395729d30dee86abf1b6fb4d` — subject
"feat(integration): add notification delivery abstraction". Pushed to
`origin/main`; local `HEAD` (at the time of that push), `origin/main`, and
`git ls-remote origin refs/heads/main` all verified to match this SHA (see
Verification below). This paragraph describes that already-completed,
already-verified push of `0b2a4d5ec2c88d5a395729d30dee86abf1b6fb4d` — it
does not assert anything about whatever commit this documentation edit
itself becomes part of, which is pushed separately, afterward, as its own
step (RTL-IF-4-CLOSE Step 6).
Commit/push permission: **GRANTED and exercised.** RTL-IF-4 was implemented
against explicit "DO NOT COMMIT OR PUSH" instructions and left
`READY FOR REVIEW / NOT COMMITTED`. It was then independently verified by
Codex (RTL-IF-4V — diff scope, in-app notification separation,
provider-neutral delivery contract, deterministic mock delivery, recipient
boundary, privacy/security, forwarding regression, event semantics, no
persistence/schema additions, test quality, architecture boundary all
PASS; no blockers; one non-blocking note — provider-specific endpoint/body
validation remains deferred until real provider formats and limits are
known), and this session's own RTL-IF-4-CLOSE task explicitly authorized
the commit and push recorded above.

**Caveats, preserved from implementation through this closure:** mock
delivery only; no real SMS/email; no production recipient policy; the
Notification Center remains independent and unmodified; message forwarding
is not completed by this tranche (still persists a preference only, sends
nothing); the durable delivery lifecycle (persistence, acknowledgement,
escalation, retention, retry) remains client-dependent and is not
implemented.

## Purpose

Introduce a protocol/provider-neutral notification-delivery boundary for
future Mock/SMS/Email delivery, without changing current in-app
Notification Center behavior and without inventing unresolved client
recipient rules:

```
existing persisted event -> existing event semantics -> existing Notification Center  [UNCHANGED]

future delivery caller -> DeliveryRequest -> NotificationDelivery interface
                                            -> MockNotificationDelivery now
                                            -> SMS / Email adapters later
```

See `docs/decisions/ADR-020-notification-delivery-is-separate-from-the-in-app-projection.md`
for the full decision record.

## What changed

- **`services/notification_delivery.py`** (new) — the contract:
  `CHANNEL_SMS`/`CHANNEL_EMAIL` (`SUPPORTED_CHANNELS`), `STATUS_DELIVERED`/
  `STATUS_FAILED`, `DeliveryRequest` (channel, recipient_endpoint, body,
  reference_id, subject — no Flask/session object, no DB session, no
  provider credentials, no Eskom/SMS vendor payload), `DeliveryResult`
  (status, detail — no provider response id), `NotificationDelivery`
  (`Protocol`, `deliver(request) -> result`, no authorization inside it —
  authorization already happened upstream, entirely the caller's job).
  `UnsupportedChannelError` refuses any channel outside
  `SUPPORTED_CHANNELS` before any delivery attempt.
- **`services/mock_notification_delivery.py`** (new) — deterministic
  `MockNotificationDelivery`: outcome (`succeed=True`/`False`) fixed at
  construction, returned synchronously for every `deliver()` call; no
  network, sleep, thread, or background loop; `.sent` accumulates every
  accepted `DeliveryRequest` so tests can assert exactly what would have
  been delivered. Not a real SMS/email provider — does not model any
  vendor's API or failure codes.
- **`docs/decisions/ADR-020-...md`** (new) — the decision record: why
  delivery stays a separate, unconsumed boundary; why no recipient-
  resolution policy exists; why no schema migration exists.
- **`docs/context/DECISION_INDEX.md`** — ADR-020 row added.
- Tests: `tests/test_notification_delivery.py` (new, 15 tests) — provider-
  neutral request shape, contract field audit (no Flask/session/DB object,
  no provider response id), deterministic mock SMS/email success and
  failure, request accumulation across repeated calls, unsupported-channel
  refusal before recording as sent, no-network-call proof, `Protocol`
  conformance, a caller-resolved real user contact endpoint (via
  `repo.get_user_by_id`) passed explicitly into a `DeliveryRequest`, and —
  via `ast`-based import inspection, not string search — structural proof
  that `notification_service.py`/`event_semantics.py` neither import nor
  are imported by either new module, and that no `callbacks/`/`pages/`/
  `components/` file imports either new module.

**Nothing in `services/notification_service.py`,
`services/event_semantics.py`, `services/message_forwarding_service.py`,
`services/device_event_service.py`, or
`repositories/plant_monitoring_repository.py` was modified.** No schema
migration. This tranche is additive-only: two new modules, one new test
file, one new ADR, and the two context documents.

## Explicitly NOT implemented (out of scope, per the task)

Real SMS, Exchange/email integration, Twilio or any other provider, MQTT/
RabbitMQ, worker, scheduler, retry engine, a `notification_deliveries`
table, notification acknowledgement, escalation, production recipient
routing, 18:30 forwarding, forwarding delivery, high-temperature/vibration
rules, UI redesign, admin notification configuration. No recipient-
resolution policy of any kind — `DeliveryRequest.recipient_endpoint` is
always caller-supplied; this tranche implements no logic that decides who
receives what. No durable delivery history. Enabling message forwarding
still sends nothing (FWD-D9, unchanged) — forwarding is not completed by
this tranche. No new runtime dependencies were installed.

## Verification

- Focused: `tests/test_notification_delivery.py` — 15 passed.
- Regression: `tests/test_notification_service.py` +
  `tests/test_event_semantics.py` + `tests/test_event_consumption_db.py` +
  `tests/test_message_forwarding.py` +
  `tests/test_rtl_command_service_lifecycle.py` +
  `tests/test_rtl_command_dispatch.py` +
  `tests/test_migration_rtl_command_lifecycle.py` +
  `tests/test_simulated_event_source.py` — all passed, run together in one
  invocation, unmodified.
- `python -m pytest -m db -q` — all passed, exit 0, no failures (Windows
  Git Bash swallows this pytest install's final summary line; exit code 0
  plus an unbroken dot sequence with no `F`/`E` markers across every
  progress chunk is the evidence available this session — same caveat
  recorded at RTL-IF-1 through RTL-IF-3's close).
- `python -m pytest -m "not db" -q` — all passed, exit 0, same evidence
  shape as above.
- `python -m pytest -q` (full suite) — all passed, exit 0, same evidence
  shape as above.
- `python scripts/build_context_pack.py --check` — CLEAN, at both open and
  close of this gate.
- `git diff --check` — clean, no whitespace errors.
- `git status --short` — matches the file list above plus untouched
  `debug.log`; no unexpected changes.
- Push verification (RTL-IF-4-CLOSE Step 4): after `git push origin main`,
  `git rev-parse HEAD`, `git rev-parse origin/main`, and
  `git ls-remote origin refs/heads/main` all returned
  `0b2a4d5ec2c88d5a395729d30dee86abf1b6fb4d`.

## Codex RTL-IF-4V independent verification

Result: **VERIFIED**, no blockers — diff scope PASS; in-app notification
separation PASS; provider-neutral delivery contract PASS; deterministic
mock delivery PASS; recipient boundary PASS; privacy/security PASS;
forwarding regression PASS; event semantics PASS; no persistence/schema
additions PASS; test quality PASS; architecture boundary PASS.

Non-blocking note: provider-specific endpoint/body validation (phone
number format, email address format, message length limits, encoding)
remains deferred until a real provider's actual format and limits are
known — `DeliveryRequest.recipient_endpoint`/`.body` accept any string
today, deliberately, since inventing validation rules ahead of a real
SMS/email provider would risk encoding assumptions the eventual provider
does not share.

This gate does not overstate what was built: no real SMS or email exists,
`MockNotificationDelivery` is exactly what its name says, no production
recipient-routing policy exists, and the existing Notification Center is
unmodified and structurally independent of this boundary.

## Security / privacy

No secret enters browser-facing data — `DeliveryRequest`/`DeliveryResult`
carry no credential field at all. The adapter never trusts a browser
role/user_id: `DeliveryRequest` has no identity field, and `deliver()`
performs no authorization check, by design (authorization is entirely the
caller's job, upstream). `MockNotificationDelivery.deliver()`'s failure
`detail` string is a fixed, safe, hardcoded literal — never derived from
caller input, so it cannot leak anything the caller supplied. No test in
this tranche embeds a real credential, phone number, or email address —
`tests/test_notification_delivery.py`'s one DB-marked test creates its own
disposable fixture user on the isolated schema. Recipient resolution, when
it is eventually implemented, remains explicitly deferred to a future
tranche — not sketched here even as a stub. AUTH-HARDEN-1/AUTH-PROD-HARDEN-1
behavior is untouched: no file in `services/auth_service.py`, `app.py`, or
`config/settings.py`'s session/cookie settings was read or modified.

## Known ambiguity

None encountered. No authority conflict between `AGENTS.md`,
`SOURCE_AUTHORITY.md`, `PROJECT_LEDGER.md` §8 (client-undecided delivery/
recipient rules), ADR-018, ADR-019, or the notification/forwarding source
files inspected.

## Next queued gate

None queued. This gate is implemented, independently verified (Codex
RTL-IF-4V), committed as `0b2a4d5ec2c88d5a395729d30dee86abf1b6fb4d`, and
pushed to `origin/main` with the remote match confirmed above. What comes
next is a separate, later decision — most plausibly whichever client
decision resolves first among production recipient-routing policy, a real
SMS/email provider selection, or the durable delivery lifecycle (§8), but
none is decided by this gate.
