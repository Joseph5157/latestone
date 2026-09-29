# Decision Index

Status: Approved
Date: 2026-08-29
Last updated: 2026-09-29 — added ADR-029

Every ADR in `docs/decisions/`, one line each. This file is the map; the ADR
is the territory — read the ADR before acting on a decision, don't act on
the one-line summary alone.

Per `AGENTS.md`: every ADR carries `Status` (Proposed / Approved / Superseded
/ Rejected) and `Implemented-by` (a commit sha, or "not yet") as **independent
fields**. Approved-and-not-yet-implemented is normal — it means the decision
is settled but the code doesn't exist yet. Check both columns before assuming
either "approved" means "built" or "not yet" means "undecided."

| ADR | Decision | Status | Implemented-by |
|---|---|---|---|
| [ADR-001](../decisions/ADR-001-event-classification-no-thresholds.md) | Events are closed, pre-classified facts — no consumer holds a numeric threshold (amended by ADR-023: a separate derived temperature condition) | Approved | `bb1e2e9` |
| [ADR-002](../decisions/ADR-002-fleet-attention-is-freshness-only.md) | Requires Attention = Stale + No Data only, never mixed with event history | Superseded by ADR-024 | `29a4c5a` |
| [ADR-003](../decisions/ADR-003-location-is-plant.md) | Location = Plant; no Zone/Feeder/GIS level exists in the schema | Approved | `699ece0` |
| [ADR-004](../decisions/ADR-004-device-scope-is-not-user-selectable.md) | Device scope is authorization-derived; no page may offer a scope selector | Approved | `9966bd7` |
| [ADR-005](../decisions/ADR-005-auto-refresh-is-page-owned-polling.md) | Auto-refresh is a page-owned `dcc.Interval`, not a shared "live" feed | Approved | `23642da` (precedent); Command Center's own interval `b8315c8` |
| [ADR-006](../decisions/ADR-006-route-scoped-theming-is-architecture.md) | Route-scoped dark/light theming is CC-1 architecture, not later polish; the semantic palette is route-scoped in BOTH appearances | Superseded by ADR-025 | `267b11a` |
| [ADR-007](../decisions/ADR-007-event-demo-seed-uses-ingest-event.md) | The CC-1 event demo seed must call `ingest_event()`, never `insert_device_event()` directly | Approved | `a49620f` |
| [ADR-008](../decisions/ADR-008-command-center-reuses-existing-read-paths.md) | Command Center's read side is `get_fleet_health()` + `list_recent_device_events()` + the batched `list_device_paths()`, never new SQL or Fleet Overview's presentation components | Approved | `1940b93`, `bb1e2e9` (precedent); Command Center's call sites `a49620f` |
| [ADR-009](../decisions/ADR-009-priority-investigation-ranks-on-freshness-only.md) | Priority Investigation ranks on freshness only; a STALE age is the OLDEST metric's timestamp, and exists only when every metric has one | Superseded by ADR-024 | `ce5d4ac` |
| [ADR-010](../decisions/ADR-010-monitoring-reset-preserves-operational-history.md) | A monitoring reset replaces measurements and preserves operational history; the destructive teardown is a separate, acknowledged `--purge`; no CASCADE | Approved | `29f5290` |
| [ADR-011](../decisions/ADR-011-affected-locations-is-top-n-with-disclosure.md) | Affected Locations names the worst 8 Plants and discloses the rest; a selected Plant below the cut is retained and says why | Superseded by ADR-024 | `6aafc4c` |
| [ADR-012](../decisions/ADR-012-rank-bars-are-capped-and-route-themed.md) | The rank bar is a fixed 15rem track on route-scoped tokens; no track absorbs surplus width, and the encoding basis is unchanged | Superseded by ADR-024 | `e33d0e1`, `59f92a9` |
| [ADR-013](../decisions/ADR-013-export-data-is-a-capability.md) | EXPORT_DATA is a device-less capability, not a device action; same roles, guard changed to `require_capability`, scope still enforced by the repository's `allowed_device_ids` | Approved | `723dd0b` |
| [ADR-014](../decisions/ADR-014-latest-reads-are-bounded-seeks.md) | Every latest-reading read is a bounded index seek, at device grain too; `get_latest_readings_for_device` no longer scans the device's history, and the guard measures rows examined rather than wall-clock | Approved | `3b33015` |
| [ADR-015](../decisions/ADR-015-credentials-name-logins-not-roles.md) | Credential configuration names logins and can never express a role; the `users` row decides user_id, name, role and status. No password column, no migration — the rule survives the eventual swap to the client's mechanism | Approved | `f0862d0` |
| [ADR-016](../decisions/ADR-016-operational-actions-are-shared-administration-is-not.md) | A device's operational actions are a shared surface reachable from the device page by any role authorized for them; assignment/registration stay administrator-only on `/admin/devices`. `may_action` and `require_action` are one decision, so a rendered control and an honoured click cannot disagree | Approved | `08e44af` |
| [ADR-017](../decisions/ADR-017-rtl-commands-are-the-protocol-neutral-transport-seam.md) | `rtl_commands` is the one seam between an authorized programming request and a future device transport; one command per request (`uq_rtl_commands_request_id`), created atomically with the request and its audit row; `command_type`/`state` carry no CHECK constraint so a future transport tranche can extend the vocabulary without a migration | Approved | `831ea2b` |
| [ADR-018](../decisions/ADR-018-simulator-transport-is-not-the-eskom-protocol.md) | `SimulatorTransport` is a deterministic, in-process test contract (SUCCESS/FAILURE/TIMEOUT), not the Eskom protocol; the six-state `rtl_commands` lifecycle (`QUEUED→SENT→ACKNOWLEDGED→SUCCEEDED`, or `SENT→FAILED`/`TIMED_OUT`) is enforced by `rtl_command_service`'s transition map, never the database; `dispatch_command()` is explicit-caller-only, never automatic | Approved | `bb7fea3` |
| [ADR-019](../decisions/ADR-019-simulated-event-source-reuses-canonical-ingestion.md) | `simulated_event_source.py` is a thin front end onto the existing `ingest_event()` boundary, not a second event pipeline; its `SUPPORTED_EVENT_TYPES` allowlist is a simulator-only restriction layered on top of (never instead of) `ingest_event()`'s open-vocabulary policy; distinct from `SimulatorTransport` (outgoing) by direction, not merged | Approved | `a89fbf9` |
| [ADR-020](../decisions/ADR-020-notification-delivery-is-separate-from-the-in-app-projection.md) | `notification_delivery.py`/`mock_notification_delivery.py` are a provider-neutral outgoing-delivery boundary, structurally uncoupled from the existing Notification Center (`notification_service.py`, unmodified); `DeliveryRequest.recipient_endpoint` is always caller-supplied — no recipient-resolution policy is implemented; no `notification_deliveries` table, since delivery lifecycle/retention/escalation are still client-undecided | Approved | `0b2a4d5` |
| [ADR-021](../decisions/ADR-021-freshness-threshold-is-admin-configurable-and-read-live.md) | The global freshness threshold is an Administrator-configurable singleton, read live by `evaluate_freshness` once per request; no row = environment default; BR008 unaffected | Approved | `08acb6e` |
| [ADR-022](../decisions/ADR-022-registration-enforces-the-5-digit-uid-fleet-wide.md) | Registration enforces the 5-digit RTL UID (one shared rule with programming) and refuses a code already registered anywhere in the fleet; application-level only, no DB constraint until the client confirms | Approved | `c47cf87` |
| [ADR-023](../decisions/ADR-023-temperature-condition-uses-admin-limits.md) | Temperature condition (Normal/Warning/Critical/Limits not set/No recent data) is evaluated only by `temperature_condition_service`, on each RTL's latest reading against Administrator-configured limits, in Decimal; a derived condition, not an event; amends ADR-001 and the AGENTS.md data rule | Approved | `a0f1223` |
| [ADR-024](../decisions/ADR-024-overview-and-command-center-split-by-question.md) | Fleet Overview (`/plants`, every role) answers where everything is and how hot; Command Center (`/command-center`, Administrator/Technician) answers what needs attention now; no panel on both; `/` lands operational roles on Command Center; supersedes ADR-002/009/011/012 | Approved | `2cfad36` |
| [ADR-025](../decisions/ADR-025-dark-mode-is-app-wide-and-remembered.md) | Dark mode is app-wide (one class on `app-root`), Dark by default, remembered per browser (`localStorage` store); toggle in the sidebar; login stays light; supersedes ADR-006 | Approved | `07d1b02` |
| [ADR-026](../decisions/ADR-026-one-colour-key-colour-means-urgency.md) | One colour key for the dashboard: colour means urgency (Critical red, Warning amber, No data purple, Device fault grey-blue, Normal green, Not rated grey), the label says what; blue is selection only; tones owned by `components/status_colors.py` | Approved | `21a5d1f` |
| [ADR-027](../decisions/ADR-027-device-page-alarm-history.md) | Device page shows the RTL's own alarms as chart markers, a read-only alarm history list, and shaded "No readings" gaps (> 4 × the RTL's median spacing in the window); Administrators and Technicians only; no new query | Approved | `6bbf26c` |
| [ADR-028](../decisions/ADR-028-ring-gauges-for-part-of-whole-counts.md) | Ring/donut gauges allowed only for part-of-whole counts (RTLs working, problems by kind); no needle/speedometer dials, no full pies, no single-value gauges; ADR-026 tones, CSS conic-gradient | Approved | `7973853` |
| [ADR-029](../decisions/ADR-029-sql-server-only-target-architecture.md) | Final production database is SQL Server only; PostgreSQL is transitional; client RTL DB stays read-only until an approved change proposal | Approved | not yet |

## Reading this table

- **Nine of the ten gate CC-1** (`docs/context/ACTIVE_GATE.md` links the
  subset each gate actually touches — don't load all ten for every CC-1
  task; load what the gate names).
- Five of the ten (001-004, 008) are not new decisions invented for CC-1 —
  they are pre-existing, already-shipped behaviour (event semantics, fleet
  freshness, the plant schema, ROLE-3 device scope, the `FleetHealth`/event
  read functions) that CC-1 must conform to and reuse. They are backfilled
  here because CC-1 depends on them and they had no durable record before
  now, not because CC-1 changed them.
- Four (005-007, 009) are CC-1-original decisions, and all four are built.
- ADR-010 is not a CC-1 decision at all: it records the SEED-RESET-1 defect
  fix, which CC-1 acceptance depended on but which governs the seeds rather
  than the Command Center.
- Every ADR in this table carries an `Implemented-by` sha.
- ADR-013 is the first SUPERSESSION in this table, and it supersedes a
  decision that is not an ADR: R4-D3, frozen in
  `services/report_export.py`'s docstring. That docstring is corrected in
  the same commit — a supersession discoverable only from the new record
  is not a supersession (`AGENTS.md`).
- ADR-012 is not a CC-1 decision either. It is the CC-2 defect gate against
  a panel CC-1 accepted, and it deliberately supersedes nothing: ADR-011
  governs *which* plants the panel names, ADR-012 only how the row is drawn.
- ADR-002 was corrected 2026-08-29 (same day as ADR-008): its original
  "Affected areas" pointed at `components/fleet_condition.py` as something
  to reuse. It isn't — see ADR-008. The decision itself (`Requires
  Attention = Stale + No Data`) didn't change, only which file embodies the
  reusable part.
- No ADR is Superseded or Rejected yet — ADR-013 supersedes R4-D3, which
  is a frozen decision in a docstring, not an ADR. When an ADR is
  superseded, edit its own file's
  `Status:` field in the same commit that supersedes it — per `AGENTS.md`,
  a supersession is only real once the old record says so itself, not only
  the new one.

## Provenance

Backfilled 2026-08-29 during CTX-1, scoped deliberately to what the CC-1
planning pack (`command center/`, frozen 2026-08-28) depends on — not a
full sweep of every decision in the project's history. Older tranches
(DB-1..4, ROLE-1..3, ADMIN-0P..3, NAV-1..3, ENT-2..6, BOOTSTRAP-1) have no
ADR yet; they remain recoverable from `git log` and agent memory until
something depends on them enough to justify backfilling. Do not treat their
absence here as evidence they were never decided.
