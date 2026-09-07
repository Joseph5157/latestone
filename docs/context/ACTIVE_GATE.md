# Active Gate

Status: **CLOSED / DEVELOPMENT BASELINES RECORDED**
Date: 2026-09-06
Gate: C08-BASELINE-1 — Record development baselines (C-01, C-02, C-04, C-08,
C-15) pending client confirmation, and queue the next implementation gate

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
  remain unconfirmed (14 open questions in
  `docs/VIBRATION_METRIC_CONTRACT_TBD.md`).
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

## REPORT-MAXTEMP-1 — IMPLEMENTED / VERIFIED / PENDING COMMIT

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

## Next implementation gate: REPORT-EXPORT-1 — QUEUED, NOT STARTED

Set 2026-09-07, once REPORT-MAXTEMP-1's implementation was verified above.
Not started — no CSV/PDF export code exists for Maximum Temperature yet.
Scope: give Maximum Temperature the same development-default CSV export
Installed RTLs and RTL Alarms already have (`services/report_export.py`,
`EXPORTABLE_REPORTS`), rebuilding rows through the SAME
`max_temperature_rows`/`resolve_max_temperature_period` functions the
preview uses (R4-D7's principle), and deciding whether/how the resolved
period is represented in the exported document. The client-approved
production report format (PDF vs CSV vs XLSX) remains the C-04 baseline —
CSV only, development default — unchanged by this gate.

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
