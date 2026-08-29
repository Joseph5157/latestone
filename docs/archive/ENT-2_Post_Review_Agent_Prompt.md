# ENT-2 — Post-Review Freeze / Commit Gate Agent Prompt

## Project

Power / Remote Temperature Logger (RTL)

Repository:

`C:\Users\sikha\Videos\power\powerplant-dashboard`

## Current project checkpoint

The last synchronized requirements checkpoint before ENT-2 was:

`89b3b9fffe0f2d4212778bacd53cf823768ebd0c`

ENT-2 is:

**Fleet Operations Overview / Exception Hierarchy**

A review has already been completed against `4e6d26c`.

Review verdict:

**APPROVED — no blocking findings.**

The touched tests were re-run locally and reported:

`85 passed`

Do not reopen the approved ENT-2 design unless repository evidence shows that the reviewed state is not actually present.

---

# 1. Your task

Inspect the repository state first and determine what `4e6d26c` represents in the current checkout.

Run:

```bash
git status --short
git branch --show-current
git rev-parse HEAD
git log --oneline -8
git show --stat --oneline 4e6d26c
```

Then follow the applicable path below.

---

# 2. If `4e6d26c` is already the ENT-2 commit

If HEAD is already `4e6d26c`, or the ENT-2 work is already committed in that commit:

1. Do **not** create another commit.
2. Do **not** amend or rewrite `4e6d26c`.
3. Confirm the working tree is clean.
4. Re-run the focused ENT-2 verification:

```bash
python -m pytest   tests/test_needs_attention.py   tests/test_fleet_overview.py   tests/test_freshness_policy.py   tests/test_freshness_aggregation.py   tests/test_listing_errors.py   tests/test_table_navigation.py -q
```

5. Run:

```bash
git diff --check
git status --short
```

6. Stop before push and return the verification report.

---

# 3. If ENT-2 is present but still uncommitted

If the reviewed ENT-2 changes are in the working tree and have not yet been committed:

## Frozen ENT-2 scope

The approved implementation is limited to:

### Fleet operations hierarchy

- Extend `FleetHealth` additively with the already-derived information required for exception drill-through.
- Preserve one telemetry/freshness fetch per Fleet render.
- Use the existing service layer for hierarchy metadata.
- Build a grouped exception queue:

```text
Plant
  Transformer
    RTL
```

- Only non-FRESH branches appear.
- RTL leaves are the actionable exceptions.
- Parent Plant/Transformer rows are context and do **not** consume the visible leaf cap.
- Cap by affected RTL leaves.
- Preserve truthful disclosure wording.
- Use only existing freshness semantics:
  - Fresh
  - Stale
  - No Data
- Do not introduce Warning/Critical/electrical-health semantics.

### Fleet page reading order

Keep:

```text
Operating Status
Systemic State
Needs Attention
Fleet Inventory
Administration
```

Administration must remain visually secondary to monitoring and exceptions.

### Navigation

- Transformer and RTL exception rows may deep-link to their existing real routes.
- Use a normal HTML anchor for `#fleet-plants`; do not use `dcc.Link` for the hash-only anchor.

### Responsive behaviour

Preserve the grouped hierarchy and visual parent/child relationship at desktop, tablet, and mobile widths.

### Explicitly excluded from ENT-2

Do **not** add or change:

- notification UX;
- report UX;
- report history;
- report formats;
- device-detail UX;
- drawer grammar;
- Device Management search/filter wiring;
- routing structure;
- nested device URLs;
- authorization;
- scope policy;
- repository SQL;
- schema/migrations;
- Eskom taxonomy assumptions;
- high-temperature/vibration semantics;
- notification acknowledgement/escalation;
- Data-column custom severity sorting (UXD-2 remains accepted debt).

---

# 4. Review findings already accepted

The following observations were reviewed and are **non-blocking**:

1. A non-FRESH transformer with no telemetry-backed RTL leaves may not appear as its own rendered child row. This is consistent with the frozen rule that RTL leaves are the actionable exceptions.
2. `sort_needs_attention_tree` may remain an identity/test-seam function. Do not create a second ordering authority.
3. Zero-leaf disclosure wording such as `"2 affected plants."` is cosmetically acceptable.
4. `hierarchy_code_index` may perform one full device metadata scan when exceptions exist. At the current 120-device development scale this is acceptable. Keep it to a single bulk hierarchy read; do not create N+1 reads.

Do not change code solely to address these observations in this tranche.

If an explanatory module/docstring comment is already present, keep it. Do not create an extra commit just for commentary unless required to explain behaviour that would otherwise be misleading.

---

# 5. Verification requirements before commit

Run the focused ENT-2 tests:

```bash
python -m pytest   tests/test_needs_attention.py   tests/test_fleet_overview.py   tests/test_freshness_policy.py   tests/test_freshness_aggregation.py   tests/test_listing_errors.py   tests/test_table_navigation.py -q
```

Then run the full suite:

```bash
python -m pytest -q
```

Then:

```bash
git diff --check
git status --short
```

The following architectural invariants must still hold:

- no SQL in callbacks/components;
- no new repository query for freshness;
- `get_fleet_health(...)` called exactly once per Fleet render;
- hierarchy metadata resolved through services;
- no invented severity semantics;
- no schema/migration change;
- no authorization/scope change;
- exception cap counts RTL leaves, not parent headers;
- parent context is automatically included;
- existing row IDs/navigation remain stable.

---

# 6. Commit gate

If all verification passes and ENT-2 is still uncommitted, commit the exact reviewed tranche.

Preferred commit message:

```text
feat(ui): strengthen fleet exception hierarchy
```

After commit, run:

```bash
git rev-parse HEAD
git status --short
git show --stat --oneline HEAD
```

Do **not push**.

---

# 7. Do not perform tomorrow/follow-up work in this run

The following are separate future checkpoints and must not be folded into ENT-2:

- 768 px / 390 px screenshot acceptance if not already performed;
- `services/report_service.py` timezone defect;
- UX-1 / viewport cleanup;
- ENT-3 RTL Detail Density & Condition Workspace;
- ENT-4 Notification Operations;
- ENT-5 Operational Workflow Consistency;
- ENT-6 Reporting / Cross-App Industrial Polish.

---

# 8. Return format

Return:

1. Current HEAD before action.
2. Whether `4e6d26c` was already committed or the work was uncommitted.
3. Files in the ENT-2 tranche.
4. Focused test result.
5. Full-suite result.
6. `git diff --check` result.
7. Final commit hash, if a commit was created.
8. Final `git status --short`.
9. Explicit statement:

```text
Push not performed.
```

Stop there for the human review/push gate.
