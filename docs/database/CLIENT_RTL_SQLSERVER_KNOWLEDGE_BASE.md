# CLIENT RTL SQL SERVER — AUTHORITATIVE KNOWLEDGE BASE

**Project:** Power / Eskom Remote Temperature Logger (RTL) Dashboard  
**Purpose:** Single source of truth for all future work involving the client RTL SQL Server database.  
**Status:** Consolidated from completed read-only forensic audits.  
**Authoritative repository checkpoint during audits:** `3571b24b394bdc3c860afc0741eb24a418c3f169`  
**Database:** Microsoft SQL Server — `RTL`  
**Database policy:** READ-ONLY until mapping, proposal, client approval, and a separate approved write gate.  
**Timezone decision:** SAST / UTC+2.  
**Precedence:** ADRs remain authoritative for approved architectural decisions, especially ADR-029. This file is the consolidated source of truth for verified client SQL Server facts, interpretations, and unresolved business decisions. If a future approved ADR or client decision changes a conclusion, this file must be updated accordingly. Against older exploratory notes and earlier audit prose, this file wins unless a later approved audit or client decision updates it.  
**Gate:** SQLSERVER-EVIDENCE-CONSOLIDATION-11.

---

## 1. NON-NEGOTIABLE DATABASE RULES

1. The final production target is **Microsoft SQL Server only**.
2. PostgreSQL is transitional application/development infrastructure and will be retired only after safe migration.
3. The client SQL Server must remain **READ_ONLY** until existing structures are understood, current app requirements are mapped, genuine gaps are identified, proposed changes are documented, and the client approves those changes.
4. Never add or change tables, columns, indexes, views, constraints, permissions, procedures, triggers, or data without an approved future gate.
5. Never expose sensitive values such as cell numbers, email addresses, API keys, password hashes, or other personal contact data.
6. Do not synthesize data to fill missing client telemetry.
7. Do not silently correct, clamp, average, deduplicate, or reinterpret client source data unless an approved rule exists.
8. Use set-based SQL. Avoid N+1 database access patterns.
9. Keep SQL Server provenance separate from application-owned state.

---

## 2. DATABASE SNAPSHOT FACTS

| Item | Count |
|---|---:|
| User tables | 19 |
| Views | 4 |
| `master_temperature` rows | 2,456,901 |
| Telemetry UIDs | 400 |
| Current registered RTL UIDs (`device_list`) | 339 |
| Current RTL→Transformer mappings (`trfr_list`) | 185 |
| `device_status` rows | 339 |
| TUG transformer asset rows (`tug_report`) | 70,738 |
| `persons` | 8 |
| `roles` | 3 |
| `technician_assignments` | 0 |
| Legacy technician rows (`techmician_device_list`) | 68 |
| `settings_upload_log` rows | 3,400 |
| `alarm_log` rows | 3,346 |
| `startup_msg_log` rows | 397,813 |
| `sensor_error_log` rows | 1,177 |
| `powerdown_log` rows | 719 |
| `comms_alarm` rows | 132 |

The database has no stored procedures, functions, triggers, sequences, or synonyms relevant to the application.

---

## 3. TERMINOLOGY — USE THESE WORDS

### Client hierarchy vocabulary

**Operating Unit → Zone → Sector → CNC → Feeder → Transformer → RTL**

Do **not** call the top hierarchy level `Plant`. **Plant is not a client SQL Server hierarchy level** and must not be used as production client-data terminology. It appears in this repository only where the legacy synthetic PostgreSQL model (30 plants / 71 transformers / 120 devices) is documented; that model is retired from production (section 21).

Do not invent Division, Region, Area, Site, or Station unless a future client-approved source introduces them.

### RTL terminology

Use:
- **RTL**
- **RTL UID**
- **Registered RTL**
- **Mapped RTL**
- **Unmapped RTL**
- **Operational evidence**
- **Historical evidence**

Do not casually equate:
- registered = active,
- unmapped = retired,
- old = offline,
- `High Temp.` = current status,
- legacy `Online` = application Online state.

---

## 4. REGISTERED FLEET

### Authoritative current registration directory

`dbo.device_list`

Facts:
- 339 rows
- 339 unique UIDs
- every current registered UID also has a `device_status` row

**Interpretation:** `device_list` is the authoritative **current registered RTL directory**.

It is **not** an authoritative active-fleet list.

It contains no registration timestamp, activation state, deactivation state, retirement state, last-seen field, transformer, or lifecycle reason.

Correct wording:
> Registered RTL directory: 339

Avoid:
> 339 active RTLs

---

## 5. HISTORICAL UID UNIVERSE

Across 13 UID-bearing sources, the observed historical universe is:

- **427 total UIDs**
- **339 currently registered**
- **88 historical-only**

Absence from `device_list` does **not** prove retirement or deletion.

The database stores no explicit lifecycle state.

---

## 6. OPERATIONAL FLEET EVIDENCE

Using dated operational evidence through **17 September 2026 SAST**:

| Current registered population | Count |
|---|---:|
| Operational evidence in 2026 | 111 |
| Historical evidence only | 220 |
| No operational evidence found | 8 |
| Total registered | 339 |

Additional 2026 evidence:
- 109 registered RTLs have temperature telemetry in 2026.
- 111 have Check-in evidence in 2026.

Current mapping relationship:

| Current directory group | 2026 evidence | Historical only | No evidence | Total |
|---|---:|---:|---:|---:|
| Mapped | 111 | 74 | 0 | 185 |
| Unmapped | 0 | 146 | 8 | 154 |
| Total | 111 | 220 | 8 | 339 |

### Important conclusion

The 154 unmapped RTLs contain:
- 146 with historical operational evidence only,
- 8 with no operational evidence found,
- 0 with dated 2026 operational evidence under the audited definition.

Safe wording:
> Currently registered but not currently mapped, with no dated 2026 operational evidence.

Do **not** automatically call them retired, inactive, or offline.

---

## 7. TEMPERATURE TELEMETRY

### Source

`dbo.master_temperature`

This is the authoritative discovered source for real temperature telemetry.

Facts:
- 2,456,901 rows
- 400 telemetry UIDs
- 319 of 339 currently registered UIDs have telemetry
- 20 registered UIDs have no telemetry
- 81 telemetry UIDs are not currently in `device_list`

The database contains **temperature only** as continuous telemetry.

There is no confirmed continuous source in this database for:
- voltage,
- current,
- active power,
- reactive power,
- power factor,
- frequency,
- energy.

### Production rule

Do not fabricate the seven unsupported metrics.

If the client later provides another authoritative source, integrate it separately. Otherwise hide/remove those metrics in production.

---

## 8. LATEST TEMPERATURE RULE

For current registered UIDs:
- 319 currently have a valid latest telemetry row.
- Current snapshot has no conflicting latest-timestamp ties.
- Historical same-timestamp conflicting values do exist.

Approved handling if a latest timestamp has:
- one value → use it,
- multiple identical values → use the common value,
- multiple conflicting values → mark temperature **ambiguous** and preserve the conflicting values.

Do not choose highest, lowest, average, or an arbitrary value.

Client decision is still required for the business rule if conflicting latest values ever affect current operation.

---

## 9. UNUSUAL TEMPERATURE VALUES

Observed data contains repeated 0 values, repeated 85 values, values ≥160, a maximum observed value of 493, sentinel-like historical dates, and duplicate UID/timestamp groups.

Sensor-error analysis did **not** prove that 0, 85, 493, or ≥160 telemetry values are sensor-error codes.

### Rule

Show source temperature as received.

Do not silently clamp, normalize, replace, filter, or discard source values.

---

## 10. TIMESTAMPS

Project decision: **interpret client operational timestamps as SAST / UTC+2.**

SQL Server timestamps are generally `datetime2(7)` and contain no offset.

Do not compare them directly with UTC server time without conversion.

Important source cutoffs differ:
- telemetry: through 17 Sep 2026,
- startup/check-in: through 26 Aug 2026,
- alarms: through 17 Aug 2026,
- settings history: through Aug 2025.

Do not assume missing later rows mean inactivity when comparing different source tables.

---

## 11. `vw_installed_rtls`

`vw_installed_rtls` currently returns exactly 339 UIDs, but it is **not structurally anchored on `device_list`**.

Recovered dependencies:
- `device_status`
- `master_temperature`
- `vw_transformer_org_hierarchy`

Field provenance:

| View field | Actual source meaning |
|---|---|
| UID | `device_status.device_uid` |
| Transformer | `device_status.trfr` |
| OU/Zone/Sector/CNC/Feeder | hierarchy view |
| Last Recorded Temperature | latest `master_temperature` value |
| RTL Status | `device_status.last_status` |
| Timestamp of Last Recorded Data | `device_status.last_status_timestamp` |

### Critical warning

“Timestamp of Last Recorded Data” is **not** the latest telemetry timestamp. It is the timestamp associated with the stored alarm/status event.

Therefore:

**Do not use `vw_installed_rtls` as the main Fleet Overview source.**

Preferred fleet read architecture:

`device_list`
+ independent hierarchy enrichment
+ independent `device_status` raw facts
+ set-based latest `master_temperature`

---

## 12. HIERARCHY AND CURRENT TRANSFORMER MAPPING

### Current RTL→Transformer mapping candidate

`dbo.trfr_list`

Facts:
- 185 rows
- 185 distinct UIDs
- 185 distinct transformer codes
- current snapshot is one-to-one
- mapping authority is not formally client-approved

`device_status.trfr` matches `trfr_list` for current non-null mappings.

### Hierarchy

`vw_transformer_org_hierarchy` provides:
- 185 rows
- 178 complete hierarchy paths
- 7 mapped transformer rows with hierarchy missing

Empirical chain:

`trfr_list` → transformer code → `tug_report.description` → Operating Unit / Zone / Sector / CNC / Feeder

Use hierarchy as factual reference with caveats until client confirms authority.

### Current network context rule (LATEST-NETWORK-CONTEXT-01, ADR-031)

Population = `device_list`. Current transformer = `trfr_list` only. Hierarchy =
the view row naming the same code (database equality: trimmed, case-insensitive;
never fuzzy), else "Hierarchy unavailable". The latest code in
`settings_upload_log`, `startup_msg_log` and `master_temperature` is compared
with it and only ever *flags* a disagreement.

Measured 2026-09-30 over the 185 mapped RTLs: latest settings and latest
check-in agree for all 185; latest telemetry agrees for 183 and differs for
UID 29042 (`EMV35` vs `ozw28`) and UID 29598 (`TEST29598` vs `cza67`). No source
has a tie at its latest timestamp. Codes differ in letter case between tables
(`PINS144` / `pins144`) — the same transformer, which is why comparison is
case-insensitive. The 154 unmapped RTLs mostly carry historical codes in these
tables (109 in all three); those stay history and are not promoted to current.

---

## 13. TRANSFORMER MOVEMENT AND ASSIGNMENT HISTORY

Transformer movement is normal.

Among 400 telemetry UIDs:
- only 52 used one transformer code,
- 105 used two,
- many used three or more,
- one UID used up to 22 codes.

There were 2,434 observed code changes.

A current-only mapping table cannot preserve the real historical story.

### Architecture rule

Future RTL→Transformer assignment must preserve dated history.

Conceptually preserve:
- RTL UID
- transformer
- assignment start
- assignment end
- current/open assignment
- source/provenance
- actor
- reason
- optional previous-assignment link

Do not simply overwrite `trfr_list` as the application's only assignment history.

Exact future schema is not yet approved.

---

## 14. TUG TRANSFORMER ASSET DIRECTORY

### Source

`dbo.tug_report`

Facts:
- 70,738 rows
- 1 Operating Unit
- 3 Zones
- 8 Sectors
- 45 CNCs
- 820 feeder labels / 822 feeder IDs
- transformer code embedded in free-text `description`
- 9-digit `location` is unique across all 70,738 rows

### Strongest technical asset key candidate

`tug_report.location`

Do not use transformer code alone as a key.

Reasons:
- 8 transformer codes are duplicated,
- some duplicates represent different assets,
- 26 descriptions have fused code/voltage text,
- many descriptions contain spelling errors,
- asset status/currentness is not stored.

### Technical suitability

`tug_report` is **SUITABLE WITH FILTERING** as a read-side transformer directory.

It is not yet client-confirmed as the authoritative transformer master.

Safe future picker pattern:

Zone → Sector → CNC → Feeder → search Transformer

Use `location` as the hidden technical identifier.

Do not infer active/current/installed status from presence in TUG.

---

## 15. PROGRAMMING / SETTINGS HISTORY

### Source

`dbo.settings_upload_log`

Facts:
- 3,400 rows
- 366 UIDs
- history from 2020–2025

Observed request methods:
- `RTL Master`
- `RTL Client`
- `SMS Command`
- `SMS`

Observed reporting intervals:
- 1hr
- 6hr
- 24hr

Settings rows may include UID, transformer code, reporting interval, timestamp, operator, and method.

There is no stored acknowledgement, success result, failure result, response, error text, command text, or delivery status.

### Strong evidence

In measurable cases, interval changes were followed by matching telemetry cadence in roughly 96% of cases.

Programming commonly occurred before first telemetry and around transformer-code changes.

### Correct interpretation

Historical “Program RTL” capability clearly included recording/sending transformer code and reporting interval.

The database does not prove whether this database transmitted the command, another application transmitted it, SMS remains an approved production transport, or any particular request succeeded.

Future command lifecycle must be application-owned if live programming remains in scope.

---

## 16. COMMUNICATION SEMANTICS

### `Check-in`

A recurring `startup_msg_log` classification whose cadence follows configured 1hr / 6hr / 24hr intervals with small positive delay/jitter.

Check-in is useful communication evidence.

### Legacy `Online`

Mostly a 2017–2020 periodic classification.

It is **not** a reliable current Online state.

Do not map it directly to application `ONLINE`.

### `last_comms_ok`

`device_status.last_comms_ok`:
- TRUE: 130
- FALSE: 2
- NULL: 207

It is a partial persisted legacy result and does not represent current freshness.

### `comms_alarm`

132 rows corresponding to devices where the legacy communication result is populated.

It is **not** a current offline list or communication alarm history.

### Production Online/Offline

No production Online/Offline rule exists in the database.

Future state must derive from approved policy using some combination of latest accepted telemetry, Check-in evidence, configured reporting interval, powerdown/startup context, and lifecycle eligibility.

Client policy must define accepted communication evidence, grace, Late/Offline thresholds, powerdown handling, recovery behavior, and treatment of telemetry without Check-in.

Until approved, do not present derived Online/Offline as authoritative.

---

## 17. ALARMS AND HEALTH EVENTS

The legacy database does not contain a unified alarm lifecycle.

| Event | Source |
|---|---|
| High Temperature | `alarm_log` |
| Sensor Error | `sensor_error_log` |
| Battery Low | `startup_msg_log` |
| Powerdown | `powerdown_log` |
| Check-in / legacy Online | `startup_msg_log` |
| Partial comms snapshot | `comms_alarm` |

### High Temperature

`alarm_log`:
- 3,346 rows
- 122 UIDs
- all classified `High Temp.`

Most alarm payloads are ≥80, but **80°C is not an approved threshold**.

Alarm events are not simply `master_temperature WHERE temperature >= 80`.

### Event source timing and coverage (verified by HISTORICAL-EVENTS-01)

| Class | Source and filter | Event time column | Value column | Span |
|---|---|---|---|---|
| High Temperature | `alarm_log` | `event_timestamp` | `temperature` | 2020-12-04 to 2026-08-17 |
| Sensor Error | `sensor_error_log` | `reading_timestamp` (no `event_timestamp` column) | `temperature` (999.00 observed; stored as is, not an interpreted code) | 2000-01-01 sentinel and later, to 2026-05-24 |
| Battery Low | `startup_msg_log` where `status = 'Battery Low'` (7,674 of 397,813 rows) | `event_timestamp` | `battery_voltage` | to 2026-08-25 |
| Powerdown | `powerdown_log` | `event_timestamp` | `battery_voltage` | 2017-11-07 to 2025-03-03 |

* `sensor_error_log` has 2 rows with a NULL `reading_timestamp` and 7 rows
  before 2010 (the `2000-01-01 00:00` sentinel); time-bounded reads exclude the
  NULLs, so a whole-history window counts 1,175 of 1,177.
* Each row carries its own `trfr` (the transformer recorded with the event).
  Events for UIDs no longer in `device_list` exist: 402 High Temperature,
  504 Sensor Error, 1,737 Battery Low, 618 Powerdown rows (19 / 26 / 46 / 25 UIDs).
* Newest event overall: 2026-08-25 (Battery Low). A rolling "last 30 days from
  today" window is therefore empty on this restored copy; the app anchors its
  default window on the newest recorded event.

### Lifecycle missing

The database has no explicit acknowledgement, resolution, clear, episode end, return-to-normal, operator comment, or escalation.

Safe UI meaning:
> High Temperature event occurred.

Unsafe without new application workflow:
> This RTL currently has an unresolved High Temperature alarm.

The same principle applies to Sensor Error, Battery Low, and Powerdown.

Preserve source events as immutable historical facts.

Build application-owned attention episodes only after client-approved lifecycle rules exist.

---

## 18. PEOPLE AND ROLES

Sources:
- `persons`
- `roles`
- `contact_list`

Observed role names are exactly:
- Administrator
- Technician
- General User

Current people:
- 3 Administrators
- 5 Technicians
- 0 General Users

### Authentication

Credential-looking columns exist, but current rows do not contain usable credentials.

Therefore:
- reuse/adapt `persons` and `roles` as identity/business structures,
- do not assume legacy authentication is usable,
- production authentication remains a new application capability.

There are no database permission tables defining UI capabilities.

Role semantics must be application-controlled.

---

## 19. TECHNICIAN ASSIGNMENTS

### Legacy

`techmician_device_list`
- 68 rows
- 5 technicians
- legacy/unconstrained structure

### Newer constrained structure

`technician_assignments`
- 0 rows
- FK to persons
- FK to `device_list`
- uniqueness on person/device
- `assigned_date`
- no active/unassigned lifecycle

### Direction

Prefer adapting `technician_assignments` for future application ownership.

Do not create a duplicate third assignment system.

Future needs likely include active/current assignment, unassignment, reassignment history, assigned-by, and start/end timestamps.

Client policy is still required for multiplicity and scope.

Legacy data does **not** prove that assignment historically gated programming.

---

## 20. NOTIFICATIONS AND FORWARDING

Existing structures:
- `contact_list`
- `persons`
- `message_forwarding_list`

Evidence is weak.

Missing:
- alarm/event linkage,
- per-device recipient mapping,
- clear channel rules,
- delivery lifecycle,
- retry history,
- consent history.

Do not assume notification ownership or behavior.

Future client decisions are required for recipients, channels, ownership, consent, privacy, and retention.

---

## 21. CLIENT DATABASE CAPABILITY CLASSIFICATION

### REUSE / ADAPT FROM SQL SERVER

- registered RTL directory — `device_list`
- temperature telemetry — `master_temperature`
- TUG transformer asset directory — `tug_report`
- current RTL→Transformer mapping candidate — `trfr_list`
- hierarchy reference — hierarchy view + TUG
- high-temperature history — `alarm_log`
- startup/check-in and battery events — `startup_msg_log`
- powerdown history — `powerdown_log`
- sensor-error history — `sensor_error_log`
- persons — `persons`
- role vocabulary — `roles`
- technician assignment structure — `technician_assignments`
- programming/settings history — `settings_upload_log`
- legacy report shapes — existing views, used carefully

### NEW APPLICATION-OWNED CAPABILITY REQUIRED

Subject to client approval:
- authentication
- RTL lifecycle / deactivate / retire
- RTL lifecycle history
- transformer assignment history
- alarm acknowledgement
- alarm resolution
- operator comments
- escalation
- application audit trail
- configurable temperature thresholds
- current communication-state derivation
- notification workflow/delivery history
- live command/request lifecycle if remote actions remain in scope

### RETIRE FROM PRODUCTION

Unless another authoritative source is supplied:
- synthetic Plant hierarchy
- synthetic devices
- synthetic transformer inventory
- synthetic readings
- seven synthetic non-temperature metrics

---

## 22. DEMO-SAFE DATA

Safe factual display:
- Registered RTL directory: 339
- RTLs with operational evidence in 2026 YTD: 111
- RTLs with temperature telemetry in 2026 YTD: 109
- RTLs with Check-in evidence in 2026 YTD: 111
- Current transformer mappings: 185
- Registered RTLs with historical evidence only: 220
- Registered RTLs with no operational evidence found: 8
- Data available through: 17 September 2026 SAST

Fleet row fields safe now:
- RTL UID
- latest real temperature
- latest telemetry timestamp
- transformer if mapped
- hierarchy if available
- historical source event indicators with dates

Do not present as authoritative yet:
- Online/Offline
- current unresolved alarm
- current Battery Low
- current powerdown
- active/inactive/retired
- hot-RTL ranking from `vw_maximum_temperature`
- `vw_installed_rtls` “Last Recorded Data” as telemetry freshness
- seven unsupported electrical metrics

---

## 23. CLIENT BUSINESS DECISIONS STILL REQUIRED

1. **Operational fleet / lifecycle**
   - What should happen to the currently registered-but-unmapped historical population?
   - Should devices be explicitly Deactivated / Retired rather than deleted?
   - What states and reasons should be supported?

2. **Communication policy**
   - What counts as accepted communication?
   - Should Online/Offline use a multiple of configured interval or another timeout?
   - Is a Late state required?
   - How should powerdown affect status?
   - What marks recovery?

3. **TUG business facts** (technical use of TUG as read-only hierarchy reference is an engineering decision, ADR-031 — not a client question)
   - Is `location` a stable asset identifier?
   - How is TUG refreshed?
   - How are retired/decommissioned transformer assets represented?

4. **Authentication**
   - How should Administrator / Technician / General User identities authenticate?
   - Account creation, activation, deactivation, password/SSO policy?

5. **Technician assignment**
   - Can one RTL have multiple technicians?
   - Can one technician have many RTLs?
   - Must reassignment preserve history?
   - What actions are permitted to assigned technicians?

6. **Program RTL**
   - Does the new application actually transmit configuration to devices?
   - Or only create/record a programming request for another service?
   - Which transports are approved?
   - Which reporting intervals are allowed by role?

7. **Notifications**
   - Who receives alerts?
   - Which channels?
   - Consent and retention rules?
   - Who configures recipients?

8. **Alarm workflow**
   - What event types create actionable attention items?
   - Acknowledge / resolve / comment / escalate?
   - Retention?

9. **Temperature conflicts / unusual values**
   - What should happen if the same UID/timestamp contains conflicting latest values?
   - Are unusual historical values valid readings or known bad data?

10. **Other seven metrics**
   - Is there another authoritative DB/API/device source?
   - If not, hide/remove them from production.

---

## 24. QUESTIONS ENGINEERING SHOULD STOP ASKING THE CLIENT

These are evidence-resolved enough for engineering:

- Current registered RTL directory? → `device_list`
- Continuous electrical metrics besides temperature in this DB? → no confirmed source
- Legacy `Online` = current state? → no
- `last_comms_ok` = current freshness? → no
- `comms_alarm` = current offline list? → no
- `vw_installed_rtls` safe as Fleet Overview authority? → no
- Its “Last Recorded Data” = telemetry time? → no
- Alarm acknowledgement/resolution in SQL Server? → no
- Retirement lifecycle in SQL Server? → no
- Threshold configuration in SQL Server? → no
- Transformer movement historically common? → yes
- Future mapping history required? → yes
- Historical reporting intervals 1h / 6h / 24h? → yes
- Programming history shows transformer code + interval changes? → yes
- TUG technically usable as transformer read directory? → yes, with filtering
- TUG as read-only hierarchy reference for current mapped RTLs? → yes (engineering, ADR-031)
- TUG proven client-authoritative asset master / lifecycle source? → not yet; never inferred
- Which transformer is an RTL's current one? → `trfr_list`; other sources only corroborate (ADR-031)
- Roles named Administrator / Technician / General User? → yes
- Legacy auth supplies usable production credentials? → no

---

## 25. SOURCE-OF-TRUTH APPLICATION READ ARCHITECTURE

```text
device_list
    |
    |-- current registered RTL population
    |
    +--> latest master_temperature
    |       - latest temperature
    |       - latest telemetry time
    |
    +--> trfr_list / hierarchy reference
    |       - current transformer candidate
    |       - OU / Zone / Sector / CNC / Feeder when available
    |
    +--> device_status
    |       - raw legacy diagnostic facts only
    |
    +--> settings_upload_log
    |       - historical reporting interval/configuration
    |
    +--> startup_msg_log
    |       - Check-in / Battery Low / historical Online
    |
    +--> alarm/event logs
            - High Temp
            - Sensor Error
            - Powerdown
```

Do not make `vw_installed_rtls` the application contract.

---

## 26. WRITE-SIDE TARGET PRINCIPLE

When SQL Server writes are eventually approved:

> Preserve existing client source structures where they fit; add only genuine missing application capability.

Existing source/history worth preserving:
- device registration
- telemetry
- event logs
- people/roles
- current mapping
- programming history

Likely new application-owned state:
- lifecycle
- assignment history
- auth
- acknowledgement/resolution
- audit
- thresholds
- command lifecycle
- notification lifecycle

All future schema proposals require a separate approval gate.

---

## 27. POSTGRESQL RETIREMENT RULE

Do not remove PostgreSQL merely because equivalent SQL Server data has been discovered.

Retire PostgreSQL capability only after:
1. SQL Server source is confirmed,
2. application read/write mapping exists,
3. client-required gaps are approved,
4. implementation passes,
5. migration is validated,
6. acceptance is complete.

Never migrate demo/development rows automatically.

---

## 28. AUDIT SOURCE INDEX

This knowledge base consolidates:

- REAL-DB-AUDIT-02
- REAL-DB-MAP-04
- SQLSERVER-TARGET-ARCH-01
- CLIENT-HIERARCHY-AUDIT-01
- VW-INSTALLED-RTLS-AUDIT-01
- CLIENT-SQLSERVER-DEEP-AUDIT-02
- RTL-LIFECYCLE-FORENSICS-03
- COMMUNICATION-SEMANTICS-04
- RTL-TRANSFORMER-HISTORY-05
- RTL-SETTINGS-PROGRAMMING-06
- RTL-ALARM-ENGINE-FORENSICS-07
- ACTIVE-FLEET-RECONSTRUCTION-08
- TUG-ASSET-MASTER-09
- LEGACY-APPLICATION-RECONSTRUCTION-10

These audits were performed read-only and repeatedly verified that database counts and repository state were unchanged.

---

## 29. FUTURE AGENT INSTRUCTION

Before Codex, Claude Code, DeepSeek, or another agent performs work involving the client database, instruct it:

> Read `docs/database/CLIENT_RTL_SQLSERVER_KNOWLEDGE_BASE.md` first. Treat it as the current authoritative client-database evidence, subject to the ADRs (ADR-029). Do not rediscover or contradict established findings without new evidence. Distinguish SOURCE FACT, ENGINEERING DERIVATION, CLIENT DECISION, and APPLICATION-OWNED STATE. Never modify client SQL Server unless the active gate explicitly authorizes the exact write/change.

---

## 30. CHANGE CONTROL

Update this file when (and it must be updated when an approved ADR or client decision changes a conclusion):
1. a new audit materially corrects or extends a fact;
2. the client answers a pending business decision;
3. an approved SQL Server schema change is implemented;
4. production integration reveals verified new evidence.

Every update should record:
- date,
- evidence/client decision,
- what changed,
- superseded statement if any,
- related gate/commit.

---

## FINAL MEMORY ANCHOR

1. **339 = current registered RTL directory, not active fleet.**
2. **111 = registered RTLs with dated operational evidence in 2026 to the available cutoff.**
3. **Temperature is the only confirmed continuous telemetry in the client database.**
4. **Client SQL Server contains valuable source/history data but lacks modern application lifecycle features.**
5. **Reuse the client data; add only approved missing capability—never rebuild or reinterpret it unnecessarily.**
