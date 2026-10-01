# REPORTS-REALIGNMENT-01 — Retire the Report Center "Recent Reports" demo block

Gate: REPORTS-REALIGNMENT-01
Status: implemented — awaiting owner review (commit/push NOT GRANTED)
Baseline (starting SHA): `c0a434bd6b6870fbf30cae354de45090246e14be`
Authority: `docs/context/ACTIVE_GATE.md` (this gate). **No ADR** — this gate
changes no architecture, no data model and no scope model; it removes the last
synthetic/mock UX residue on the reports surface, left standing after
LEGACY-SYNTHETIC-UX-CLEANUP-01.

This gate is **cleanup only**. Report generation, preview and export are
untouched, and the asset-scope filter (synthetic `DeviceScope` +
Plant→Transformer→Device cascade) is deliberately left in place for the
separate REPORTS-REALIGNMENT-02 gate.

---

## 1. What was removed

The Report Center's **"Recent Reports"** section rendered `_mock_recent_reports`
— hard-coded demo entries explicitly labelled *"Demo data … mock entries for UI
demonstration only."* No report-history feature exists behind it, so the section
was deleted outright rather than stubbed (owner decision 2026-10-01).

| File | Change |
|---|---|
| `pages/report_center.py` | Deleted the "Section B — Recent Reports" `html.Section` (heading, the "Demo data" status panel, and the `recent-reports-table` `entity_table`); dropped the now-unused `entity_table` import. |
| `callbacks/report_center.py` | Deleted `_mock_recent_reports`, `_seed_mock_reports()`, its call in `register()`, and the `populate_recent_reports` callback; corrected the module docstring. The `entity_table` import is retained — still used by the data-backed report tables. |
| `assets/app.css` | Removed the `#recent-reports-table` responsive card rules (the `::before` labels and the two grid-column selectors). The shared `.entity-table-wrapper--responsive` rules are left intact. |
| `tests/test_report_center.py` | Removed the recent-reports/mock tests (`test_layout_has_recent_section`, `test_layout_has_recent_reports_table`, the `TestMockRecentReports` class, `test_recent_reports_table_responsive`, `test_demo_status_rendered_muted_not_freshness_green`) and the dead `_mock_recent_reports`/`entity_table` imports. Added `test_layout_has_no_recent_reports_demo_block` as a guard. |

Diff against baseline (gate-owned files only): **11 insertions, 185 deletions**
across the four files above.

## 2. Guard test

`tests/test_report_center.py::TestReportCenterLayout::test_layout_has_no_recent_reports_demo_block`
asserts the retired block cannot reappear: the layout string contains neither
`"Recent Reports"` nor `"Demo data"`, and the collected component ids do not
contain `recent-reports-table`.

## 3. Residue check

A repository search across `pages/`, `callbacks/`, `tests/` and `assets/` for
`_mock_recent_reports`, `_seed_mock_reports`, `populate_recent_reports`,
`Recent Reports`, `recent-reports-table` and the "mock entries for UI" label
returns matches **only inside the guard test** (which asserts their absence).
No production code references the retired block.

## 4. Non-goals honoured

- No scope-model change — the synthetic `DeviceScope` + Plant/Transformer/Device
  asset-scope selector is unchanged (REPORTS-REALIGNMENT-02's job).
- No change to the three data-backed reports (Installed RTLs, RTL Alarms
  (30 Days), Maximum Temperature), their definitions, preview, generation or
  export.
- No edits to historical/planning docs that mention recent reports.
- No DB changes; SQL Server stays READ_ONLY; PostgreSQL unchanged.

## 5. Test evidence

- Focused: `python -m pytest -m "not db" tests/test_report_center.py -v`
  → **63 passed, 4 deselected**.
- Full non-DB suite: `python -m pytest -m "not db"`
  → **3681 passed, 3 skipped, 807 deselected**.
- The 7 known PostgreSQL seed/data-drift failures in the DB suite are out of
  scope and unaffected by this gate (no DB-marked test is touched).
- Context pack: `python scripts/build_context_pack.py` → **CLEAN** (baseline
  run before implementation; re-run at gate close).

Browser acceptance is not a stated precondition of this gate's commit
permission (the gate names only the two pytest commands). It can be captured on
request before the reviewed commit.

## 6. Commit/push

**NOT GRANTED.** Per `ACTIVE_GATE.md`: implement and test, then stop for owner
review before commit/push. Pattern when granted follows the prior gate:
`latestone/main` only, staging gate-owned files and preserving the unrelated
dirty files already in the tree.
