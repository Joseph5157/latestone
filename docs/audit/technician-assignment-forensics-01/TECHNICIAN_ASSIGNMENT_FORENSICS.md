# TECHNICIAN-ASSIGNMENT-FORENSICS-01

Status: **CLOSED / PASS — read-only evidence and planning only**

Date: 2026-09-30

Repository baseline: `0a8d26dab36d35e7b8d452e830b1bb16a23ed30c`

Database: local restored client SQL Server `RTL`, queried with `rtl_app_reader`

## 1. Executive summary

The legacy `dbo.techmician_device_list` is usable as a **transitional,
read-only assignment source (classification B)**, but it is not a complete or
authoritative authorization source.

The evidence is unusually clean at the identity/pair level: its 68 rows are 68
distinct Technician/UID pairs; all five names match exactly, including case and
spacing, to exactly one of the five `persons` whose role is `Technician`; all
five Technician persons occur; no Administrator occurs; there are no duplicate
pairs and no UID has more than one Technician. Sixty-four assigned UIDs are
currently registered and four are historical/unregistered. None is invalid or
unresolvable.

Coverage is the limiting fact. Only **64/339 (18.9%)** registered RTLs have a
legacy assignment. Only **19/185 (10.3%)** mapped RTLs are assigned; 45/154
unmapped RTLs are assigned. Of the 64 current assigned RTLs, 48 have temperature
data, 19 are mapped, 17 have resolved hierarchy, and only 6 have dated 2026
operational evidence under the already-audited temperature-or-Check-in rule.
The table has no assignment time, actor, end time or history, so it cannot say
whether its rows are current, reconstruct reassignment, or explain gaps.

Programming is corroboration only. Three Technicians have attributed settings
rows; one of them programmed three currently registered UIDs outside that
person's legacy assignment set. This proves the legacy set did not universally
describe programming reach at the snapshot being compared. It does not prove
what assignment or programming policy applied at the event time.

The empty, constrained `technician_assignments` table is structurally consistent
with a newer current-assignment table, but the schema does not prove developer
intent. It is not yet adequate for history or authorization. The next safe gate
is a policy decision gate, not an implementation gate.

## 2. Method and safety

All database work used static `SELECT` statements against data and SQL Server
catalog views. No PostgreSQL connection was opened. At the beginning and end of
the audit SQL Server reported:

| Check | Result |
|---|---:|
| `DATABASEPROPERTYEX(DB_NAME(), 'Updateability')` | `READ_ONLY` |
| reader `UPDATE` permission | 0 |
| reader `INSERT` permission | 0 |
| reader `ALTER` permission | 0 |
| `techmician_device_list` rows | 68 |
| `technician_assignments` rows | 0 |
| `device_list` rows | 339 |
| `settings_upload_log` rows | 3,400 |

Classification used here:

- **A — currently registered:** UID occurs in `device_list`.
- **B — historical/unregistered:** absent from `device_list`, but present in at
  least one independent operational/current source (`master_temperature`,
  `device_status`, `trfr_list`, settings/startup/alarm/sensor/powerdown/comms
  logs).
- **C — invalid/unresolvable:** absent from both populations.

Operational evidence in 2026 follows the existing audited definition: a 2026
`master_temperature` reading or a 2026 `startup_msg_log` `Check-in`. It is not
an Online/Offline or lifecycle classification.

## 3. Technician identity mapping

| Person ID | `persons.full_name` | Role | Legacy name match | Legacy rows |
|---:|---|---|---|---:|
| 2 | Senzo Mpungose | Technician | exact binary match | 23 |
| 3 | Reginald Tshabalala | Technician | exact binary match | 16 |
| 4 | Nhlakanipho Ndwandwe | Technician | exact binary match | 25 |
| 5 | Shawn Papi | Technician | exact binary match | 3 |
| 6 | Linda Gerotek | Technician | exact binary match | 1 |

Identity-quality findings:

- Each legacy name has exactly one exact person match and exactly one
  Technician match.
- Case-folding and trimming produce the same match set; **no normalization is
  required**. For every name, visible character length equals stored character
  length, so no trailing-space repair is hidden by the comparison.
- There are no duplicate `persons.full_name` values.
- There are no orphan legacy names.
- There are no Technician persons absent from the legacy table.
- No non-Technician person appears in the legacy table.
- Matching remains name-based evidence only. A future model must store
  `person_id`, not a copied name.

## 4. Legacy assignment inventory

| Measure | Count |
|---|---:|
| Rows | 68 |
| Distinct Technician names | 5 |
| Distinct RTL UIDs | 68 |
| Distinct Technician + UID pairs | 68 |
| Duplicate pairs | 0 |
| UIDs with multiple Technicians | 0 |
| Null/blank names | 0 |
| Null UIDs | 0 |
| Invalid/unresolvable UIDs | 0 |

`device_uid` is a non-null SQL Server `int`, so malformed textual values cannot
occur in this table shape. It has a primary key on identity column `id`, but no
FK from name to `persons`, no FK from UID to `device_list`, and no unique
constraint on name/UID. The clean snapshot is therefore observed quality, not
an enforced invariant.

## 5. Current registered intersection and per-Technician assignments

| Technician | All legacy UIDs | Registered (A) | Historical/unregistered (B) | Invalid (C) |
|---|---:|---:|---:|---:|
| Linda Gerotek | 1 | 1 | 0 | 0 |
| Nhlakanipho Ndwandwe | 25 | 25 | 0 | 0 |
| Reginald Tshabalala | 16 | 16 | 0 | 0 |
| Senzo Mpungose | 23 | 19 | 4 | 0 |
| Shawn Papi | 3 | 3 | 0 | 0 |
| **Total** | **68** | **64** | **4** | **0** |

Current registered UIDs that can be associated by exact legacy evidence:

- **Linda Gerotek:** 29858
- **Nhlakanipho Ndwandwe:** 29049, 29542, 29545, 29550, 29559, 29562,
  29569, 29573, 29576, 29580, 29581, 29583, 29585, 29595, 29596, 29597,
  29598, 29608, 29609, 29611, 29625, 29626, 29639, 29641, 29668
- **Reginald Tshabalala:** 29623, 29624, 29627, 29650, 29652, 29653,
  29654, 29664, 29665, 29666, 29667, 29669, 29679, 29680, 29682, 29683
- **Senzo Mpungose:** 29021, 29025, 29037, 29039, 29042, 29059, 29075,
  29091, 29530, 29532, 29536, 29538, 29539, 29543, 29577, 29586, 29594,
  29612, 29651
- **Shawn Papi:** 29855, 29856, 29857

The four historical/unregistered UIDs are 29024, 29046, 29071 and 29544, all
associated with Senzo Mpungose. They have independent historical evidence.
They are not called inactive or retired.

## 6. Current assignment coverage

| Current registration group | Assigned | Unassigned | Total | Assigned coverage |
|---|---:|---:|---:|---:|
| Mapped | 19 | 166 | 185 | 10.3% |
| Unmapped | 45 | 109 | 154 | 29.2% |
| **All registered RTLs** | **64** | **275** | **339** | **18.9%** |

This is too incomplete to turn absence of a legacy row into a new denial rule
without explicit business approval. An unassigned registered RTL may be a real
gap, outside the legacy workflow, or deliberately unassigned; the database
does not distinguish those cases.

## 7. Multiple-Technician/conflict cases

There are **no current or historical UIDs assigned to more than one legacy
Technician**, and no duplicate Technician/UID pair. Therefore this snapshot
contains no case from which legitimate many-to-many, duplicate data, or
sequential reassignment can be inferred. It also cannot prove that multiple
Technicians were forbidden: the table has no constraint enforcing that rule
and no history.

## 8. Mapping, hierarchy, temperature and operational coverage

These counts apply only to the 64 currently registered assigned UIDs.

| Technician | Registered | Mapped | Unmapped | Hierarchy resolved | Hierarchy unavailable on mapped | Temperature data | No temperature | 2026 operational evidence |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Linda Gerotek | 1 | 0 | 1 | 0 | 0 | 1 | 0 | 0 |
| Nhlakanipho Ndwandwe | 25 | 18 | 7 | 16 | 2 | 25 | 0 | 6 |
| Reginald Tshabalala | 16 | 0 | 16 | 0 | 0 | 0 | 16 | 0 |
| Senzo Mpungose | 19 | 1 | 18 | 1 | 0 | 19 | 0 | 0 |
| Shawn Papi | 3 | 0 | 3 | 0 | 0 | 3 | 0 | 0 |
| **Total** | **64** | **19** | **45** | **17** | **2** | **48** | **16** | **6** |

“Hierarchy resolved” requires a current `trfr_list` mapping and nonblank OU,
Zone, Sector, CNC and Feeder values from the exact current hierarchy row. The
two unavailable cases are mapped but lack a complete hierarchy path.

## 9. Programming/operator correlation

`settings_upload_log` is supporting evidence, not assignment evidence. Exact
person-name matches were used; no fuzzy match was made.

| Technician | Programming rows (UIDs) | On legacy-assigned UIDs | On non-assigned UIDs | On registered UIDs | On historical/unregistered UIDs |
|---|---:|---:|---:|---:|---:|
| Linda Gerotek | 0 (0) | 0 (0) | 0 (0) | 0 (0) | 0 (0) |
| Nhlakanipho Ndwandwe | 53 (22) | 53 (22) | 0 (0) | 53 (22) | 0 (0) |
| Reginald Tshabalala | 2 (1) | 2 (1) | 0 (0) | 2 (1) | 0 (0) |
| Senzo Mpungose | 37 (18) | 30 (15) | 7 (3) | 32 (16) | 5 (2) |
| Shawn Papi | 0 (0) | 0 (0) | 0 (0) | 0 (0) | 0 (0) |
| **Total** | **92 (41 person/UID sets)** | **85 (38)** | **7 (3)** | **87 (39)** | **5 (2)** |

Senzo's three non-assigned, currently registered UIDs are:

| UID | Rows | First / last settings event |
|---:|---:|---|
| 29017 | 2 | 2021-09-14 11:38:17 / 2021-10-20 09:44:29 |
| 29045 | 4 | 2021-10-20 10:01:31 / 2021-10-20 11:20:30 |
| 29570 | 1 | 2021-10-20 10:24:32 |

This verifies that the legacy assignment snapshot does not universally contain
every UID a named Technician programmed. Because assignment history is absent,
it does **not** prove that programming historically ignored assignment, that
the Technician was unauthorized, or that these UIDs were never assigned.

## 10. Assignment-history findings

- `techmician_device_list` has only `id`, `full_name` and `device_uid`.
- It has no assigned timestamp, `assigned_by`, end/unassigned timestamp,
  status/current marker, reason, or prior-row link.
- Identity `id` is not a timestamp and cannot safely order business events.
- `technician_assignments` is empty, so its `assigned_date` contains no history.
- `settings_upload_log` has actor name, UID and time, but records settings work,
  not assignment or unassignment.
- The only database objects whose names refer to Technician/assignment are the
  two tables above; no assignment view or assignment audit/history object was
  found. Operational event logs do not record assignment changes.

**Verdict:** reassignment sequence cannot be reconstructed safely. The legacy
table is an undated current-state-like snapshot; whether it was actually kept
current is unproven.

## 11. `technician_assignments` schema assessment

Live catalog evidence:

| Column | Shape |
|---|---|
| `assignment_id` | `int NOT NULL`, identity, primary key |
| `person_id` | `int NOT NULL`, FK to `persons.person_id` |
| `device_uid` | `int NOT NULL`, FK to `device_list.device_uid` |
| `assigned_date` | `datetime2(7) NOT NULL`, default constraint present |

There is a unique constraint on `(person_id, device_uid)` and zero rows. The
reader can see the default constraint but not its expression; the previously
audited DDL records `sysdatetime()`.

The structure is consistent with a newer current-assignment table: it replaces
copied names with keys and enforces both references. It does not prove original
developer intent. Its FK does not itself require that `person_id` have the
Technician role. It lacks `assigned_by`, end time, current status, reason and
history semantics. The unique pair also prevents a later second assignment of
the same Technician to the same RTL if history is stored as multiple rows.

## 12. Suitability verdict

| Candidate use | Verdict | Reason |
|---|---|---|
| A. Authoritative current authorization source | **No** | Only 18.9% current coverage; no lifecycle/history; no enforced references; absence is ambiguous. |
| B. Transitional read-only assignment source | **Yes, with guardrails** | Exact identities, unique clean pairs, 64 current registered intersections and no conflicts make positive associations usable. |
| C. Historical reference only | **Too weak a classification** | Four rows are historical-only, but 64 still intersect the current directory; the snapshot may carry current value even though currentness is unproven. |
| D. Unsuitable | **No** | The positive evidence is coherent and useful if never overextended into an absence-based policy. |

Transitional use means: expose the 64 positive current intersections only,
label provenance, never copy them automatically, never treat 275 missing rows
as denied/irrelevant by default, and obtain policy approval before using the
set as an authorization boundary.

## 13. Recommended target assignment model

### MUST HAVE

- immutable assignment identity;
- Technician `person_id`, validated as a Technician as well as FK-valid;
- registered RTL `device_uid` FK;
- `assigned_at` and `assigned_by`;
- `ended_at`/`unassigned_at`, with current derived from an open-ended row;
- retained assignment history rather than overwriting current state;
- multiple RTLs per Technician (the source already shows up to 25);
- constraints preventing duplicate simultaneous open person/UID assignments;
- auditable assignment/unassignment actor and time;
- an explicit import/provenance marker if legacy rows are ever adopted.

### NICE TO HAVE

- reason/comment for assignment and ending;
- link to the preceding assignment or change request;
- source/import batch and client-approved migration note;
- optimistic concurrency/version field for an administration UI.

### CLIENT BUSINESS DECISION

- whether one RTL may have multiple simultaneous Technicians;
- whether assigned RTLs define Technician visibility or only workload;
- who may assign/reassign/end assignments;
- whether a reason is mandatory;
- whether programming and historical events are restricted to assigned RTLs;
- treatment of registered RTLs with no assignment.

A separate stored `status` flag is not required if `ended_at IS NULL` is the
single current marker. If the business needs planned/suspended states, define
them explicitly rather than combining a boolean with contradictory dates.

## 14. Authorization implications

The rule “Technician may access assigned registered RTLs only” is **a
reasonable new product rule requiring explicit client/business approval**. It
is not established historical policy. Existing data supports building a
positive transitional set for 64 RTLs, but programming correlation and missing
history do not prove that assignments historically gated access or actions.

If approved, the application could consistently scope:

- `/rtls` to assigned registered UIDs;
- `/rtls/<uid>` to an assigned UID;
- `/rtls/network` to hierarchy containing assigned UIDs;
- `/events` to assigned UIDs.

Every route and callback would need the same server-side UID scope; filtering
navigation alone is not authorization. Today these real-data routes explicitly
exclude Technicians (`services/authorization.py:64,87,91,95`), while the
Technician's `/devices` route uses PostgreSQL synthetic assignment scope
(`callbacks/technician_devices.py:82-88`). No authorization is changed here.

Programming remains separately blocked by CDB-06 even if assignment scoping is
approved. Assignment must not silently grant command authority.

## 15. Legacy Technician Command Center replacement map

Technicians currently land on the Command Center
(`callbacks/routing.py:134,160-164`). It renders status, problems, hottest
temperature, alarm trend and activity panels plus the shared management drawer
(`pages/command_center.py:27-33,94-112`) from the PostgreSQL
`attention_service` snapshot and synthetic device scope
(`callbacks/command_center.py:41,51,106`). The separate `/devices` page shows
synthetic Plant/Transformer rows and management actions
(`pages/technician_devices.py:30-35,48,74`).

| Current feature | Gate disposition | Factual target |
|---|---|---|
| Technician landing / Command Center shell | **Keep temporarily** | Replace only after an approved real Technician landing exists. |
| Synthetic Plant → Transformer → Device identity | **Retire from client-facing Technician path** | Assigned registered RTL UID list and current client network context. |
| Synthetic status/freshness and working/problem gauges | **Retire** | No approved client Online/Offline rule; do not translate them. |
| Needs Attention ranking | **Replace / decision-blocked** | Assigned-UID historical events only; actionable/current attention waits for CDB-08. |
| Hottest/synthetic temperature | **Replace** | Real `master_temperature` detail via `/rtls/<uid>` with existing ambiguity/raw-value rules. |
| Programming action/activity | **Blocked by decision** | Settings history may be factual; live programming waits for CDB-06 and assignment-action policy. |
| Assignment display | **Replace** | Positive current intersections from the approved assignment source; administration workflow needs policy/history model. |
| Manage/deactivate/message-forwarding actions | **Blocked by decision** | Do not carry synthetic actions onto real RTLs automatically. |
| Navigation | **Replace after policy approval** | Dashboard → Assigned RTLs → RTL Details / filtered Network / filtered Historical Events. |

## 16. Genuine client business questions (CDB-05)

Engineering has resolved the table names, exact people/name matches, current
UID intersection, conflicts and coverage. The client should be asked only:

1. Should a Technician be able to view and work with only the RTLs assigned to
   them, or may they view other registered RTLs too?
2. May one RTL be assigned to more than one Technician at the same time?
3. Who may assign, reassign and end a Technician assignment?
4. Must reassignment history be retained, and must a reason be recorded?
5. May a Technician program only assigned RTLs, assuming programming is later
   approved at all?
6. May a Technician view historical events only for assigned RTLs?
7. How should currently registered RTLs with no Technician assignment be
   handled?

No client question mentions either database table.

## 17. Proposed next gate

Exactly one next gate is nominated:

**`TECHNICIAN-ASSIGNMENT-POLICY-01` — Client policy and transition decision**

Purpose: obtain and record the CDB-05 answers above; decide whether the 64
positive legacy/current intersections may be used as a temporary read-only
scope; define treatment of the 275 unassigned registered RTLs; approve
cardinality, actor/history and action boundaries; and produce the smallest
client-approved persistence/migration proposal. No application access change,
SQL Server write, PostgreSQL migration, or Command Center retirement belongs in
that gate.

`TECHNICIAN-REAL-RTL-ACCESS-01` should follow only if this policy gate approves
assigned-UID authorization and the transition population.

## 18. Risks and guardrails

- SQL Server remains read-only; do not populate `technician_assignments` or
  copy the legacy rows without a separate approved write/migration gate.
- Positive association is evidence; missing association is not a lifecycle or
  denial fact.
- Historical/unregistered does not mean inactive or retired.
- Do not use name matching in the target model or fuzzy-match future rows.
- Do not infer assignment timing from identity IDs or settings events.
- Do not infer current authorization policy from the absence of conflicts.
- Preserve the current default-deny real-route boundary until policy is
  approved and every data callback is server-side scoped.
- Keep programming, notification, deactivation and event-workflow permissions
  separate from visibility assignment.
- Never expose contact, credential or cellular fields while resolving identity.
