# PROJECT-AUDIT-1 — Results and Next Actions

This is a navigation and decision document. It summarizes a completed
audit so an agent can orient in minutes instead of reading the full
15-file evidence pack first. It is not a replacement for that pack — every
claim below cites the result file that carries its evidence, and a load-
bearing decision should still be checked against that file, not just this
summary.

## Audit status

- Status: **CLOSED — integrity PASS**
- Audited baseline SHA: `21e7ecd25efd462220a62bd2e70fe67866e317c7`
- Audit prompt coverage: **15/15 complete**
- All Prompt 01–14 result files are present, non-empty, correctly
  sequenced and headered (`Audit: PROJECT-AUDIT-1`, `Prompt`, `Audited
  baseline SHA`, `Execution date`, `Result status`), verified by direct
  grep across the full pack during Prompt 15, not assumed.
- No contradictions, secrets, mutations, missing result files, duplicate
  files, or misnamed files were found.
- **PASS means the audit evidence is internally sound — it does not mean
  every requested product capability is complete.** See the requirement
  status snapshot below; MISSING, DEFECT, BLOCKED_CLIENT and
  BLOCKED_EXTERNAL are all real, non-zero categories in a passing audit.

Note on the audit's own gate record: `PROJECT_AUDIT_GATE_2026-09-24.md`'s
header field still reads `Status: OPEN — AUDIT EXECUTION ONLY`. This is a
field that was never flipped after closeout, not a substantive
contradiction — the gate's own stated completion condition ("ready for
review only when Prompt 15 passes") is met, and `AUDIT_PACK_MANIFEST.md`
(Prompt 15) records integrity PASS. `docs/context/ACTIVE_GATE.md` (the
repository's normal single active-gate record) does not mention
PROJECT-AUDIT-1 at all — the audit ran as a separate, self-contained gate
file rather than through the usual `ACTIVE_GATE.md` flow. Treat this
document and the result pack under `results/` as authoritative for the
audit's own status; `ACTIVE_GATE.md` still correctly reflects that no
*implementation* gate is currently open.

## Requirement status snapshot

| Status | Count | Meaning |
|---|---:|---|
| COMPLETE | 33 | Built and evidenced |
| PARTIAL | 24 | Some implementation exists, but the requirement is not fully complete |
| MISSING | 16 | Not built |
| DEFECT | 7 | Known issue needing correction |
| BLOCKED_CLIENT | 5 | Cannot safely proceed without client/Eskom clarification |
| BLOCKED_EXTERNAL | 3 | Requires real device, provider, or enterprise-system integration |
| NOT_APPLICABLE | 1 | Not relevant to the current scope |

Total assessed status entries: **89**.

This is the corrected table: Prompt 13 reclassified UI-04 and UI-07 from
NOT_APPLICABLE to MISSING against Prompt 12's original matrix (both
describe development-team-deferred, not client-blocked, situations — the
same category as UI-06, which was already MISSING). MISSING moved 14→16
and NOT_APPLICABLE moved 3→1; every other count is unchanged from Prompt
12. See `results/AUDIT_PACK_MANIFEST.md` "Corrections/supersessions" and
`results/13_CONTRADICTION_VERIFICATION.md`.

## Confirmed defects

| Defect | Where | Nature |
|---|---|---|
| Event-semantics test-fixture date drift | `tests/test_event_semantics.py::TestAlarmEventProjections` (6 tests) | Test-only |
| TABLE-SORT-TEXT-1 | `components/entity_table.py:145` | User-visible, operational |
| `action_guard.py` docstring drift | `services/action_guard.py` | Documentation only |
| `SOURCE_AUTHORITY.md` dead citation | `docs/context/SOURCE_AUTHORITY.md:45` | Documentation only |
| PAD audit doc stale/self-superseded | `docs/PAD_SECTIONS_1_TO_3_4_AUDIT.md` | Documentation only |
| RTL functional-spec tracker stale | `docs/RTL_FUNCTIONAL_SPEC_COMPLETION_TRACKER.md` | Documentation only |

**Event-semantics test-fixture date drift.** Six tests in
`TestAlarmEventProjections` hardcode an August 2026 `NOW` fixture but do
not thread it via `now=` into 6 of 9 call sites; live wall-clock is now
more than 30 days past that fixture date, so the 30-day report window
silently excludes every fixture event and the assertions fail. This
reproduced identically in this session's own baseline run (6 failed, 3133
passed, 731 deselected). **This is a test-only defect.** The function
under test, `alarm_event_projections()`, has zero callers anywhere in the
application — independently confirmed by Results 06, 07, 10 and 13 via
import-level checks and callsite greps. The live RTL Alarms (30 Days)
report uses an entirely separate, unaffected implementation. Do not read
this as a production dashboard or alarm failure.

**TABLE-SORT-TEXT-1.** `components/entity_table.py:145` sets
`sort_action="native"`, which sorts the "Last reading" and "Data" columns
as literal text rather than by age or severity — e.g. a 5-day-old reading
can sort above an 8-minute-old one. This is an operational-safety risk:
an Administrator or Technician triaging by "most stale" or "worst first"
via the column header gets a visibly wrong order, not just a cosmetic
one. Found via browser review 2026-09-19, confirmed still present by code
inspection during this audit, user-deferred and unscheduled.

**`action_guard.py` docstring drift.** The module docstring states three
of four gated actions "have no domain service at all"; false at this
baseline — all three now call real, persisting domain services. The
guard's actual runtime behavior is correct; only the comment is wrong.

**`SOURCE_AUTHORITY.md` dead citation.** Line 45 cites
`components/fleet_condition.py`, deleted at `2cfad36`. The claim it
supports (two no-data buckets, not three) remains true under different
files; only the file citation is dead.

**PAD audit document marked stale/self-superseded.**
`docs/PAD_SECTIONS_1_TO_3_4_AUDIT.md` describes authentication as "single
hardcoded credential pair," superseded by the ROLE-4A credential-map
widening; the document already self-labels itself superseded.

**RTL functional-spec completion tracker stale.**
`docs/RTL_FUNCTIONAL_SPEC_COMPLETION_TRACKER.md` is roughly 169 commits
and 5+ days stale relative to the audited baseline; its UI-side PARTIAL
rows were not re-confirmed against the 2026-09-19 Overview/Command Center
redesign until this audit did so directly against current code.

**One defect, two framings.** The event-semantics fixture drift is
counted once in the matrix above but appears under two audit framings in
the detailed evidence (a DEFECT row in the requirement matrix, and its
own root-cause writeup in Result 10's test/quality audit). It is one
underlying defect, not two.

## Known missing or deferred capability areas

- **Deliberately deferred internal features** (development-team decision,
  "raise only if the client does," none built): Auto Update (UI-04),
  weekly alarm report by email (UI-06), cloud storage archiving (UI-07).
- **Production/operational readiness gaps**: no production identity
  provider (Entra or otherwise — `auth_service.py` is explicitly
  placeholder/demo, isolated for swap-out), and no automated
  backup/disaster-recovery mechanism (only manual, operator-run
  discipline exists today).
- **Real device/enterprise integrations** — zero code-level seam exists
  for any of these, and the client's own Functional Specification is
  silent on all five enterprise systems: RTL Master/telemetry transport,
  SMS/email delivery provider, Microsoft Entra ID, SAP HR, IBM Maximo
  (AssetDetails inbound, AssetCondition outbound to Maximo/eDNA/PowerOn).
- No external integration should ever be simulated or treated as
  complete without a real endpoint and explicit client approval. The
  repository's existing `DeviceTransport`/`SimulatorTransport` seam and
  `NotificationDelivery` interface are real, tested, and *ready* for a
  production adapter — they are not themselves that adapter, and audit
  language that says "the seam exists" should never be read as "this is
  connected to a real system."

## Client-decision dependencies

Several requirements are **deliberately blocked** by unanswered client
decisions — this is correct discipline, not an oversight, and none of
these should be built past an honest placeholder before the client
answers.

- **C-05 — communication method between the application, RTL Master and
  RTL devices.** The single broadest blocker in this audit: it gates real
  command dispatch, real message forwarding, the SMS Gateway integration,
  and the retry-policy work simultaneously.
- **C-02 — vibration metric contract and anomaly thresholds.** Carried
  forward from `REQ-3I_Clarification_Register.md`; a development baseline
  (administrator-configurable framework, never hardcoded) exists for
  *shape only* — the actual Eskom vibration sensor contract and threshold
  values remain unconfirmed.
- **C-10 — recipient policy, retry, retention and escalation for real
  notification delivery.** Gates the entire delivery chain downstream of
  the existing `NotificationDelivery` seam; without it, notification
  delivery cannot move past an honest placeholder.
- Also open: C-01, C-03, C-04, C-06, C-07, C-09, C-11 through C-14, C-16,
  C-17, and presentation-facing Q6, Q8, Q9 (Plant/Feeder naming, Power
  Down's alarm category, and the meaning of "actual notifications").

`docs/context/CLIENT_QUESTIONS.md` is the authority for these — it in
turn names `REQ-3I_Clarification_Register.md` as the repository's
authoritative clarification register for full numbering and detail. Do
not invent or assume an answer to any of the above from this document or
any other audit file; if a decision is needed, read `CLIENT_QUESTIONS.md`
directly.

## Recommended sequencing

1. **EVENT-SEMANTICS-TESTFIX-1** — restore a green non-DB baseline.
   Scope: `tests/test_event_semantics.py` only. No production code
   changes (the function under test has zero production callers).
2. **TABLE-SORT-TEXT-1** — the next user-visible, self-contained
   operational-safety fix, once the baseline is green.
3. **Documentation reconciliation** — refresh the stale tracker/citations/
   audit-document references above, and correct any audit-matrix rows if
   `12_REQUIREMENT_IMPLEMENTATION_MATRIX.md` is ever regenerated.
4. **Client clarification session** — resolve C-02 and the other open
   dependency questions before new Eskom-facing behaviour is built.
5. **Build approved, unblocked features only** — see
   `results/FINAL_AUDIT_SUMMARY.md` §10 for the full, unranked candidate
   list, grouped by whether it needs no client answer, a client answer,
   external access, or production/deployment work.

## Sources and authority

- `results/AUDIT_PACK_MANIFEST.md` — Prompt 15 integrity closeout;
  corrections applied against Prompt 12; repository mutation statement.
- `results/FINAL_AUDIT_SUMMARY.md` — Prompt 14 synthesis; the fullest
  narrative version of every section above, with file/line/test evidence
  pointers back into Results 01–13.
- `docs/context/CLIENT_QUESTIONS.md` — authoritative source for every
  open client decision; never answer one from this document.
- `docs/context/ACTIVE_GATE.md` — the only *implementation* gate
  currently in scope (none, as of this writing — see the note above).
- `docs/context/CURRENT_STATE.md` — generated test/branch snapshot; note
  its test count (3139 passed, 0 failed) is stale on this one fact and
  should not be trusted for the current count until regenerated (see
  "Audit status" above for the correct current figure).
