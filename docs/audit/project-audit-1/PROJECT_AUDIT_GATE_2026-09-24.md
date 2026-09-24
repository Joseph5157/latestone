# PROJECT-AUDIT-1 — Structured Full-Project Audit Gate

Status: OPEN — AUDIT EXECUTION ONLY
Opened: 2026-09-24
Planning baseline: `41c81c0e91f17c601f54116f74d5b782a3758244`
Repository: `Joseph5157/powerplant-monitoring`
Target branch for audit evidence: `main`

## Purpose

Establish an evidence-backed, repository-native statement of what the Power / Eskom RTL application has implemented, what is partial, what is missing, what is blocked by client decisions or external integration, and what should be considered for the next implementation gate.

This is an AUDIT gate, not an implementation gate.

## Hard rules for every prompt

1. Inspect before concluding. Do not infer implementation from plans, filenames, old chat context, branch names, or commit messages alone.
2. Repository code, tests, migrations, ADRs, current context files, client requirement documents and accepted client-feedback records are evidence. Distinguish current code truth from plans and historical statements.
3. Do NOT modify application code, tests, migrations, runtime configuration, Railway, secrets, dependencies, client delivery branches, or production data.
4. Do NOT fix defects discovered during the audit.
5. Do NOT invent Eskom requirements, thresholds, protocols, hierarchy mappings, notification semantics, reporting cadence, or integration contracts.
6. Classify each material requirement/findings as exactly one primary status:
   - COMPLETE
   - PARTIAL
   - MISSING
   - BLOCKED_CLIENT
   - BLOCKED_EXTERNAL
   - DEFECT
   - NOT_APPLICABLE
7. Every COMPLETE/PARTIAL/DEFECT finding must cite concrete repository evidence: file paths and symbols/tests where practical. Use commit/ADR/client evidence when it materially establishes intent or acceptance.
8. Separate simulator/mock capability from production integration. A deterministic simulator is not proof of a real Eskom integration.
9. Separate UI presence from end-to-end behavior. A screen/button alone is not COMPLETE.
10. Preserve uncertainty. If evidence conflicts, record the conflict instead of choosing silently.
11. Never expose credentials, secrets, tokens, connection strings or personal data in audit files.
12. Execute prompts strictly in numerical order. Finish and save the required result file before starting the next prompt.
13. Do not commit/push after each prompt unless the operator explicitly asks. The intended workflow is to complete the result pack, validate it, then make one audit-results commit/push.
14. Do not alter this gate file while executing prompts. Record corrections in the relevant result file and final synthesis.

## Evidence priority

When sources disagree, use this order while recording the disagreement:
1. Current executable code + migrations + tests.
2. Accepted/current ADRs and authoritative requirement documents.
3. Current gate/context/ledger records.
4. Client feedback/clarification records with dates.
5. Historical plans and old branches.
6. Comments/TODOs/naming assumptions.

Implementation truth and requirement truth are different: code proves what exists; authoritative requirements/accepted decisions prove what is required.

## Required result directory

Create:
`docs/audit/project-audit-1/results/`

Each prompt below creates exactly the named Markdown result. Keep findings concise but evidence-rich.

---

## PROMPT 01 — Freeze and verify the audit baseline

Read this entire gate first.

Audit repository identity and baseline only. Verify current branch, HEAD, origin/main if available locally, working-tree state, relevant remotes without printing credentials, active context status, test commands documented by the repo, and whether any local uncommitted files could contaminate the audit.

Do not run destructive commands. Do not modify anything except the required result file.

Record:
- repository/branch/HEAD
- origin/main comparison
- working-tree entries, categorized as tracked/untracked
- current active gate state
- authoritative context/decision/requirement documents discovered
- known delivery/client branches and whether they are intentionally separate
- exact audit baseline SHA to which later findings apply
- any baseline risk that must be carried through the audit

Output only to:
`docs/audit/project-audit-1/results/01_BASELINE_AND_SOURCE_AUTHORITY.md`

---

## PROMPT 02 — Requirements and traceability inventory

Using Prompt 01's frozen baseline, inventory the authoritative requirements and accepted client decisions. Inspect the Functional Specification/PAD material available in the repository, ADRs, CLIENT_QUESTIONS, clarification pack, feedback audit, master plan, project ledger and other current requirement records.

Build a requirement inventory with stable IDs where existing IDs are available. Do not judge implementation deeply yet.

For each requirement record:
- source
- requirement/decision
- authority status (confirmed / interim / unanswered / superseded)
- affected subsystem
- whether a client/external answer is still required
- conflicts or superseded assumptions

Pay special attention to hierarchy terminology, RTL Master responsibilities, thresholds, freshness/reporting cadence, notifications, report formats, roles, real transport, identity, Maximo/SAP/Entra and delivery semantics.

Output only to:
`docs/audit/project-audit-1/results/02_REQUIREMENTS_TRACEABILITY.md`

---

## PROMPT 03 — Architecture, data model and lifecycle audit

Inspect current architecture and data model end to end: database models/migrations, repository/service boundaries, Plant/Transformer/RTL hierarchy, device identity/UID, active state, assignment, programming request lifecycle, deactivation, audit records, normalized events, notification delivery model, report data paths and simulator boundaries.

Identify:
- implemented lifecycle paths
- data-model assumptions that are temporary
- orphan/dead/duplicate models or competing authorities
- schema fields that preserve generic power-plant concepts
- missing production mappings
- migrations or persistence gaps
- places where UI/service semantics diverge from stored truth

Classify every material finding using the gate statuses.

Output only to:
`docs/audit/project-audit-1/results/03_ARCHITECTURE_DATA_LIFECYCLE.md`

---

## PROMPT 04 — Authentication, authorization and role workflow audit

Audit Administrator, Technician and General User from login/session through route visibility, data scope and server-side action authorization.

Explicitly verify Technician duties:
- see only authorized/assigned RTL scope where required
- program assigned RTLs
- deactivate assigned RTLs
- receive/view alarms/notifications for assigned RTLs
- acknowledge alarms if intended by current requirements

Verify Administrator and General User boundaries, cross-role leakage protections, session identity, production identity boundary, and whether UI hiding is backed by server authorization.

Do not treat mock/demo authentication as production Entra completion.

Output only to:
`docs/audit/project-audit-1/results/04_ROLES_AUTH_SECURITY.md`

---

## PROMPT 05 — Fleet Overview, Command Center and investigation UX audit

Audit Fleet Overview/Fleet Condition, RTLs requiring attention, Command Center and drill-down/investigation flows against accepted client feedback and current requirements.

Verify actual behavior for:
- fleet condition/status
- freshness/no-data
- Warning/Critical temperature conditions
- Power Down
- Battery Low/Alarm
- Sensor Error
- affected RTL lists
- location/Plant/Transformer/RTL navigation
- event occurrence vs current-state semantics
- ranking/priority investigation
- click/filter affordances
- empty/error/loading states where relevant
- removal of Fuel/Capacity from user-facing operational views

Record UX gaps separately from semantic/data gaps.

Output only to:
`docs/audit/project-audit-1/results/05_FLEET_COMMAND_CENTER_UX.md`

---

## PROMPT 06 — Notifications, alarms and forwarding audit

Trace notifications and alarms from source event/derived condition through ingestion, classification, persistence, role scoping, Notification Center projection, acknowledgement, forwarding preferences and provider-neutral delivery.

Explicitly distinguish:
- persisted device event
- derived no-data notification
- in-app Notification Center row
- NotificationDelivery record/contract
- simulated/mock delivery
- real SMS/email delivery

Check BR008/BR009/current ADR semantics, 18:30 forwarding ownership, alarm categories, Power Down categorization, recipients, retries, retention/escalation and unresolved meaning of client phrase "actual notifications".

Output only to:
`docs/audit/project-audit-1/results/06_NOTIFICATIONS_ALARMS_FORWARDING.md`

---

## PROMPT 07 — Reports and export audit

Audit all report requirements and actual report implementations end to end.

Cover at minimum:
- RTL Alarms
- Installed RTLs
- Maximum Temperature
- current asset-scope filters
- date/range behavior
- CSV/PDF/XLSX exports
- authorization/scope
- required hierarchy columns
- data provenance and empty/error behavior
- any mismatch between Plant and Feeder/Network terminology
- any placeholder/unmapped OU/Zone/Sector/CNC/Feeder fields

Do not call a report COMPLETE merely because an export button exists; verify query/data/output behavior and tests.

Output only to:
`docs/audit/project-audit-1/results/07_REPORTS_EXPORTS.md`

---

## PROMPT 08 — RTL interfaces, simulator and production integration boundary

Audit the protocol-neutral RTL interface, command lifecycle, simulator transport, simulated incoming events, live simulator and production integration seams.

Create a clear boundary matrix for:
- implemented domain/application behavior
- deterministic simulator/mock behavior
- missing real Eskom/RTL Master behavior
- unknown client protocol decisions

Inspect specifically for MQTT/RabbitMQ/SMS/API assumptions, topics/endpoints, payload schema, TLS/auth, ACK/result handling, QoS/session/reconnect, retry/idempotency/duplicate/late ACK semantics, real programming and real event production.

Never infer a production protocol from simulator names or unused dependencies.

Output only to:
`docs/audit/project-audit-1/results/08_RTL_INTERFACES_AND_INTEGRATIONS.md`

---

## PROMPT 09 — Enterprise/external systems and deployment readiness

Audit external/enterprise integration and production deployment readiness without changing any environment.

Cover:
- Microsoft Entra ID
- SAP HR/user source
- Maximo AssetDetails
- AssetCondition outputs to Maximo/eDNA/PowerOn if required
- SMS Gateway
- Microsoft Exchange/email
- PostgreSQL/runtime assumptions
- Railway as current demo/development deployment vs target Eskom architecture
- Azure/Kubernetes/private APN/network/firewall/ExpressRoute/secrets/backups/observability/security acceptance where requirements mention them
- environment/configuration validation and secret-handling patterns

Classify "integration seam exists" separately from "production integration complete".

Output only to:
`docs/audit/project-audit-1/results/09_ENTERPRISE_DEPLOYMENT_READINESS.md`

---

## PROMPT 10 — Test, quality, defect and technical-debt audit

Inspect the test suite and quality controls. Run only safe, repository-documented local verification that the current environment supports; do not mutate external systems.

Audit:
- unit/service/repository/component tests
- DB-marked tests and their prerequisites
- role/security tests
- report/export tests
- browser/acceptance coverage
- integration/simulator coverage
- current known defects
- TODO/FIXME/placeholder/mock markers
- skipped/xfail tests
- stale branches or dead code only where they create audit risk
- generated context accuracy versus current HEAD

Explicitly verify TABLE-SORT-TEXT-1 and search for additional user-visible defects that have evidence.

Output only to:
`docs/audit/project-audit-1/results/10_TESTS_DEFECTS_TECH_DEBT.md`

---

## PROMPT 11 — Client feedback closure audit

Take every actionable item in the repository's accepted client feedback/video-review records and map it to current code behavior and evidence.

For each item classify:
- COMPLETE
- PARTIAL
- MISSING
- BLOCKED_CLIENT
- BLOCKED_EXTERNAL
- DEFECT
- NOT_APPLICABLE

Pay special attention to:
- Fleet Condition
- Command Center drill-down
- Power Down/Battery Low
- condition-click affordance
- Notification Center recent/actual notifications
- No Data prominence
- reports and asset scope
- freshness/cadence
- Feeder/Network naming
- Fuel/Capacity removal

Do not use old screenshots/builds as proof of current main unless the repository identifies them as current acceptance evidence.

Output only to:
`docs/audit/project-audit-1/results/11_CLIENT_FEEDBACK_CLOSURE.md`

---

## PROMPT 12 — Full requirement-to-implementation matrix

Now synthesize Prompts 01–11 into one traceability matrix. Re-check source code where results conflict; do not merely copy earlier conclusions.

For every material requirement include:
- requirement ID/name
- source
- status
- current implementation evidence
- test/acceptance evidence
- missing portion
- dependency/blocker
- client question ID where applicable

Also summarize counts by status, but do not turn counts into a readiness percentage or score.

Output only to:
`docs/audit/project-audit-1/results/12_REQUIREMENT_IMPLEMENTATION_MATRIX.md`

---

## PROMPT 13 — Contradiction and stale-context verification

Act as an independent verifier of the accumulated audit.

Read all result files 01–12 plus current code/context. Search for:
- contradictions between result files
- claims based only on stale plans
- features marked COMPLETE despite mock-only behavior
- requirements marked MISSING that are actually implemented
- superseded client decisions
- duplicate gaps under different names
- current-state files whose generated baseline predates audit HEAD
- statements that confuse client delivery branches with development main

Correct errors in this result by explicitly listing the authoritative resolution and affected earlier result file; do not rewrite earlier files silently.

Output only to:
`docs/audit/project-audit-1/results/13_CONTRADICTION_VERIFICATION.md`

---

## PROMPT 14 — Final audit synthesis and candidate next work

Produce the final evidence-based audit summary. This is still audit work, not implementation planning.

Include:
1. Frozen audited SHA.
2. What is demonstrably COMPLETE.
3. What is PARTIAL.
4. What is MISSING.
5. What is BLOCKED_CLIENT.
6. What is BLOCKED_EXTERNAL.
7. Confirmed DEFECTS.
8. Production-readiness gaps.
9. Client-demo/readiness observations.
10. A short set of candidate next work items grouped as:
   - unblocked application work
   - client-answer-dependent work
   - external integration work
   - production/deployment work

Do not rank candidates, choose the next implementation gate, estimate completion percentages, or implement anything. ChatGPT/user will review this evidence after it is pushed.

Output only to:
`docs/audit/project-audit-1/results/FINAL_AUDIT_SUMMARY.md`

---

## PROMPT 15 — Audit pack integrity check and closeout preparation

Perform a final mechanical/evidence integrity check.

Verify:
- all 14 required result files exist
- no result file contains secrets/credentials
- baseline SHA is consistent
- status vocabulary is valid
- evidence paths referenced actually exist
- unresolved client/external dependencies are not represented as completed
- no application/runtime files were modified during the audit
- git diff contains only approved audit documentation changes (plus any pre-existing unrelated local changes, which must remain untouched)

Create:
`docs/audit/project-audit-1/results/AUDIT_PACK_MANIFEST.md`

The manifest must list every result file, its purpose, PASS/FAIL integrity state, and any unresolved audit-quality issue.

If integrity passes, state:
`AUDIT EXECUTION COMPLETE — READY FOR HUMAN/CHATGPT REVIEW`

If it fails, state:
`AUDIT EXECUTION NOT CLOSED`
and identify exactly what must be corrected before commit/push.

Do not commit or push unless the operator explicitly instructs you to do so.

## Audit completion condition

The audit is ready for review only when Prompt 15 passes and all required result files are present. The audit does not authorize any implementation work.

After the completed result pack is committed and pushed, return to ChatGPT and request review of the GitHub audit pack. The next implementation gate must be chosen only after that review.
