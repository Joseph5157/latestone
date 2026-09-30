# CLIENT-DB-CLARIFICATION-01 Response Tracker

Internal working record, aligned with the rewritten `CLIENT_DB_CLARIFICATION_01.md` (gate SQLSERVER-EVIDENCE-CONSOLIDATION-11). It captures client answers and the decisions that follow; it is not a record of database-change approval. Client answers are never inferred: a row moves off `PENDING` only when the client actually answers.

Status values: `PENDING` · `ANSWERED` · `CLIENT CONFIRMATION NEEDED` (engineering evidence exists but the client has not confirmed it). Implementation impact is recorded per question below.

Verified facts and their sources: `docs/database/CLIENT_RTL_SQLSERVER_KNOWLEDGE_BASE.md`.

## Confirmed decisions

| ID | Decision | Status | Evidence / note |
|---|---|---|---|
| CONF-01 | Microsoft SQL Server is the final production database target; PostgreSQL is transitional. | ANSWERED | ADR-029 |
| CONF-02 | `device_list` is the registered RTL directory (339). Registered does not mean actively monitored. | ANSWERED | ADR-029; knowledge base §4 |
| CONF-03 | RTL source timestamps are SAST (UTC+2). | ANSWERED | ADR-029 |
| CONF-04 | Source temperature values are shown as received; unusual values are not silently changed or removed. | ANSWERED | ADR-029 |

## Clarifications awaiting client response

| ID | Question | Current evidence | Client answer | Status | Decision resulting from answer | Implementation impact | Database impact | Date answered |
|---|---|---|---|---|---|---|---|---|
| CDB-01 | Registered / monitored / historical RTL lifecycle: which RTLs are in service, which states and reasons exist, where is state held, retire rather than delete? | 339 registered; 185 mapped; 111 with 2026 operational evidence; the 154 unmapped have none in 2026. No lifecycle state stored. |  | PENDING |  | Fleet views may only distinguish registered vs operational evidence until answered. | Lifecycle storage would be application-owned and needs a separate approved proposal. |  |
| CDB-02 | Online / Late / Offline policy: accepted communication evidence, Late and Offline thresholds, interval dependence, power-down handling, recovery. | Legacy Online, `last_comms_ok` and `comms_alarm` are not reliable current state. Direction so far is "a few hours", hours unresolved. |  | PENDING |  | No authoritative Online/Offline shown until approved. | None expected (derived state). |  |
| CDB-03 | Is `tug_report` the approved transformer asset authority; is `location` a stable identifier; refresh method; decommissioned assets. | 70,738 rows; technically usable with filtering; `location` unique; authority not confirmed. |  | CLIENT CONFIRMATION NEEDED |  | Transformer/hierarchy enrichment carries a "reference, not confirmed" caveat. | Read-only use only; any master/history table needs a separate proposal. |  |
| CDB-04 | Authentication and account lifecycle for Administrator, Technician and General User. | `persons` (8) and `roles` (3) exist; no usable credentials stored. |  | PENDING |  | Production authentication remains a new application capability. | Auth storage, if any, needs a separate proposal. |  |
| CDB-05 | Technician assignment rules: cardinality, reassignment history, permitted actions. | `technician_assignments` empty; legacy `techmician_device_list` has 68 rows. |  | PENDING |  | Technician views and assignment admin blocked on the rules. | Likely adapt `technician_assignments` (start/end, actor); separate proposal. |  |
| CDB-06 | Does "Program RTL" transmit to the device or only record/request a change; approved transports; who may set which intervals. | `settings_upload_log` (3,400 rows) shows code/interval changes but no acknowledgement or result. |  | PENDING |  | Program RTL scope (send vs request) cannot be set. | Command lifecycle would be application-owned; separate proposal. |  |
| CDB-07 | Notification recipients, channels, consent, retention, who configures. | `persons`, `contact_list`, `message_forwarding_list` exist with no event or per-device linkage. |  | PENDING |  | No notification behaviour assumed. | Delivery/consent storage needs a separate proposal. |  |
| CDB-08 | Alarm workflow: which events need action; acknowledge / resolve / comment / escalate; retention. | 3,346 high-temperature events and other logs; no acknowledgement or resolution lifecycle. |  | PENDING |  | Events shown as "occurred", never as "currently unresolved", until answered. | Attention-episode storage would be application-owned; separate proposal. |  |
| CDB-09 | Rule for conflicting same-UID / same-timestamp temperature readings. | Historical conflicts exist; current latest snapshot has none. Handling preserves ambiguity and selects no value. |  | PENDING |  | Keep the ambiguity state. | None expected. |  |
| CDB-10 | Validity and handling of unusual source temperatures (0, 85, ≥160, max 493). | Sensor-error data did not prove these are error codes. Shown as received. |  | PENDING |  | Show raw; no filtering. | None. |  |
| CDB-11 | Authoritative source, if any, for voltage, current, active power, reactive power, power factor, frequency, energy. | Temperature is the only confirmed continuous telemetry. |  | PENDING |  | If none: hide/remove the seven metrics in production; never synthesise. | None unless a source is supplied. |  |

## Resolved by audit — not asked of the client

These are engineering conclusions, not client answers. Evidence: knowledge base §24.

| Topic | Conclusion |
|---|---|
| Registered RTL directory | `device_list` |
| Other continuous metrics in this database | None confirmed |
| Legacy `Online`, `last_comms_ok`, `comms_alarm` as current state | Not reliable |
| `vw_installed_rtls` as Fleet Overview authority | Unsafe; its "last recorded" time is not telemetry time |
| Acknowledgement, retirement, thresholds in SQL Server | Not present |
| Transformer movement and need for dated assignment history | Common; history required |
| Historical reporting intervals | 1h / 6h / 24h |
| Role names | Administrator, Technician, General User |
| Legacy authentication as production credentials | Not usable |
