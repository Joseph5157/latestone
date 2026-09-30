# LATEST-NETWORK-CONTEXT-01 — current network context acceptance

Date: 2026-09-30 · Baseline `c562fb6` · Viewport 1366×900 · Local app against the
restored client `RTL` SQL Server (`rtl_app_reader`, SELECT only). Raw run log:
`acceptance-run.log`; console: `console-errors.log` (none).

## The rule (ADR-031)

Population `device_list` → current transformer `trfr_list` → hierarchy from the
view row naming the same code (database equality, never fuzzy) → latest
settings / check-in / telemetry codes only *flag* disagreement.

## Evidence that fixed the precedence (live, read-only, 339 registered / 185 mapped)

| Latest code in… | Agrees with `trfr_list` | Differs | No record |
|---|---|---|---|
| `settings_upload_log` | 185 | 0 | 0 |
| `startup_msg_log` (check-in) | 185 | 0 | 0 |
| `master_temperature` | 183 | 2 (UID 29042 `EMV35` vs `ozw28`; UID 29598 `TEST29598` vs `cza67`) | 0 |

No source ties at its latest timestamp for any registered RTL. Code letter case
differs between tables (`PINS144` / `pins144`) — same transformer — so equality
is the database's case-insensitive one. Of the 154 unmapped RTLs, 109 carry
codes in all three tables, 21 in check-in+telemetry, 11 in settings+check-in, 4
in telemetry only, 1 in settings only, 8 in none: all history, none promoted.

## Observed live

**General User** (`demo.general01`): sidebar *Network* → `/rtls/network`.
Cards: 339 in view · 185 mapped · 154 unmapped · 178 hierarchy resolved · 7
hierarchy unavailable; 339 rows. `01-general-network-all.png`

Cascade Zone → Sector → CNC → Feeder → Transformer (each list constrained by
the parent): Empangeni Zone (2 zones offered) → 16 RTLs, all cards follow the view
(16 mapped / 0 unmapped / 16 resolved); Sector → 16; CNC (4 offered) → 6; Feeder
(2 offered) → 4; Transformer DA10 (4 offered) → 1. `02-general-cascade-transformer.png`

RTL 29639 → `/rtls/29639` (canonical detail, not `/devices`). `03-…`

*No current transformer mapping · 154* → 154 rows, cards 154 in view / 0 mapped.
`04-general-unmapped.png`. *Hierarchy unavailable · 7* → 7 rows, transformer
shown with "Hierarchy unavailable" (e.g. PINS206 / UID 29646).
`05-general-hierarchy-unavailable.png`. *Needs review · 2* → UIDs 29042 and
29598, each showing its `trfr_list` transformer plus "Needs review: latest
temperature reading names …".

**Administrator**: identical figures and 339 rows. `07-administrator-network-all.png`

**Technician**: no *Network* sidebar item; typing `/rtls/network` renders the
"No access" panel; zero RTL links, zero tables, no zone/hierarchy text in the
page HTML. `06-technician-network-forbidden.png`

Forbidden-word scan (Plant, Asset Navigator, Online, Offline, Healthy,
Inactive, Active, Voltage, Frequency, Power factor, Energy, undefined, NaN,
null, None) — no hits for any role. Console errors: 0.

## Reads

Six set-based statements per page load (registered, mappings, hierarchy, latest
settings, latest check-in, latest telemetry code — each joined to
`device_list`), ~0.5 s against the local copy. Filter changes re-render the
stored snapshot and read nothing.
