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
| CDB-03 | TUG business facts only: is `location` a permanent identifier; how is TUG refreshed; how are decommissioned transformers represented. (Technical table authority is no longer asked: engineering uses TUG as read-only hierarchy reference for current mapped RTLs, ADR-031.) | 70,738 rows; `location` unique; no asset status stored. |  | PENDING |  | The Network view shows hierarchy from TUG for current mapped RTLs, labelled as reference. No transformer active/decommissioned state is shown or inferred. | Read-only use only; any master/history table needs a separate proposal. |  |
| CDB-04 | Authentication and account lifecycle for Administrator, Technician and General User. | `persons` (8) and `roles` (3) exist; no usable credentials stored. |  | PENDING |  | Production authentication remains a new application capability. | Auth storage, if any, needs a separate proposal. |  |
| CDB-05 | Technician assignment policy: assigned-only visibility/work, simultaneous multiple Technicians, who assigns/reassigns, retained history/reason, programming/event scope, and treatment of unassigned registered RTLs. | Forensics found exact identity matches and 68 unique pairs: 64 current registered UIDs (19 mapped, 45 unmapped), 4 historical/unregistered, no conflicts. Coverage is only 64/339; no assignment history exists; settings activity includes 7 rows on 3 non-assigned current UIDs. | Approved policy (recorded in gate TECHNICIAN-REAL-RTL-ACCESS-01): (1) a Technician sees and works with only RTLs assigned to them - YES; (2) simultaneous Technicians on one RTL - NO, one current Technician per RTL; (3) assignment authority - Administrator only (assign, reassign, end); (4) assignment history retained - YES (a mandatory reason is not part of the approved policy and is not implemented); (5) Program RTL limited to assigned RTLs - YES, recorded for the later programming gate; (6) Historical Events limited to assigned RTLs - YES; (7) registered RTLs with no Technician - Unassigned, an Administrator-only assignment pool. | ANSWERED | ADR-032. The 64 currently registered legacy assignments are adopted once as transitional positive evidence; the four historical/unregistered UIDs and every other registered RTL stay unassigned. | Implemented in TECHNICIAN-REAL-RTL-ACCESS-01: Technician Fleet/Detail/Network/Events/dashboard scoped to current assignments; Administrator assignment page. Programming remains unimplemented (CDB-06). | None to SQL Server (stays READ_ONLY). Application-owned PostgreSQL store `rtl_technician_assignments`; any SQL Server assignment write needs a separate approved gate. | 2026-09-30 |
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
