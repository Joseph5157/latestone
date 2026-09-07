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

## VIB-CONFIG-1 — IMPLEMENTED / VERIFIED / PENDING COMMIT

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

### Known ambiguity

None encountered beyond the 14→15 documentation-count correction above.
No new authority conflict between `AGENTS.md`, `SOURCE_AUTHORITY.md`, the
C-02 baseline, or the source files inspected.

## Next implementation gate: RTL-PROG-EXEC-1 — QUEUED, NOT STARTED

Set 2026-09-07, once VIB-CONFIG-1's implementation was verified above.
Not started. Scope: connect the two RTL-programming/command foundations
that already exist but do not yet talk to each other —
`rtl_programming_service.py` (OPS-PROG-1: persists an operator's
programming REQUEST, atomically inserting one `rtl_commands` row per
accepted request — RTL-IF-1) and `rtl_command_dispatch_service.py` +
`SimulatorTransport` (RTL-IF-2, ADR-018: exercises that same
`rtl_commands` row's `sent_at`/`acknowledged_at`/`completed_at`/
`failure_code` lifecycle). Today the command row RTL-IF-1 creates stays
`QUEUED` forever — nothing ever calls `dispatch_command` on it, and no
lifecycle status is reconciled back onto the programming request or
shown in the UI (`rtl_programming_service.py`'s own PROG-D6/D7 record
this as deliberately deferred, not forgotten). This gate is that
connection: executable request → dispatch → lifecycle status →
reconciled back, entirely against the EXISTING deterministic
`SimulatorTransport`. **Do not invent the production transport contract**
— C-05 (the real MQTT/Eskom protocol) remains Eskom-controlled/external
and unanswered; `SimulatorTransport` stays exactly what ADR-018 already
says it is, never upgraded into a stand-in for a real device connection.
Whoever opens this gate must decide what TRIGGERS dispatch (on request
creation? a poller? an explicit admin action?) and exactly what "status
reconciliation" surfaces to the operator — neither is assumed here.

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
