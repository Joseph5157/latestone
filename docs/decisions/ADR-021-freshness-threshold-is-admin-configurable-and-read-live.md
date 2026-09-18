# ADR-021: The freshness threshold is Administrator-configurable and read live

Status: Approved
Date: 2026-09-18
Evidence: `alembic/versions/015_freshness_threshold_config.py`;
`services/freshness_threshold_service.py` (`effective_stale_after_minutes`,
`set_config`, `clear_config`); `services/monitoring_service.py`
(`evaluate_freshness`); `components/fleet_condition.py`;
`callbacks/freshness_threshold.py`; `tests/test_freshness_threshold.py`
Implemented-by: `08acb6e` (`feat(freshness): let Administrators set the freshness threshold live`)
Supersedes: nothing — extends CLIENT-FEEDBACK-FRESHNESS-1's single global
threshold (env var, 24 h default)

## Context

Freshness (Fresh / Stale / No Data) uses one global Stale-after threshold.
Until now it came only from the `FRESHNESS_STALE_AFTER_MINUTES` environment
variable (default 1,440 minutes), so changing it needed a developer and a
redeploy.

At the 2026-09-18 review the client's superior questioned whether one
uniform threshold matches real device communication patterns. The
Functional Specification documents only a 24-hour cadence (BR006, BR008) —
there are no per-RTL, per-model or per-feeder values to implement yet.

The repository already had two Administrator-configurable settings
(temperature threshold, migration 011; vibration contract, migration 012).
Both are "framework only": stored and audited, but read by nothing.

## Decision

1. **One global value, editable by an Administrator.** A singleton
   `freshness_threshold_config` row (`id = 1`). No row means "use the
   environment default"; clearing deletes the row. Same shape and audit
   rules as the temperature threshold (`FRESHNESS_THRESHOLD_SET` /
   `_CLEARED`, entity `freshness_threshold` / `global`, same-value re-save
   is a silent no-op). Capability `MANAGE_FRESHNESS_THRESHOLD`,
   Administrator only.
2. **Read live, unlike the two framework-only settings.**
   `evaluate_freshness` and the Fleet Overview threshold copy call
   `effective_stale_after_minutes()`: the configured value if present,
   otherwise `monitoring.stale_after_minutes`. A save changes what counts as
   Stale everywhere on the next refresh.
3. **Resolved once per request, never per reading.** `evaluate_freshness`
   runs about 960 times per fleet render. The value is read at most once per
   Flask request and kept on `flask.g`. This is request-scoped, not process
   state, so every worker sees a change on its next request and `AGENTS.md`'s
   "no global mutable state" rule holds. Outside a request (scripts) each
   call reads the database.
4. **Typo guards, not business thresholds.** Whole minutes, 5 to 525,600
   (365 days), enforced by the service and repeated as a database CHECK.
   Neither bound is a client-confirmed value.
5. **BR008 stays independent.** The formal ">24h no data" notification rule
   does not read this value (FS §17 rule 4), with a test asserting the
   boundary.

## Consequences

- An Administrator can respond to the client's cadence concern without a
  code change. Every change is attributable in `audit_log`.
- Freshness evaluation now depends on the database for its threshold. A
  failing read surfaces through the page's existing error handling rather
  than silently falling back to 24 hours, which would misstate the
  Administrator's setting.
- Unmarked tests see the override as unconfigured (`tests/conftest.py`), so
  the pure-logic suite stays database-free.
- **Next (Tier 2, not decided in detail):** a per-device override that
  inherits this global value unless set. The user chose per-device over
  per-model granularity on 2026-09-18. Real per-RTL values must come from
  the client.
