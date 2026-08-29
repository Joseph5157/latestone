# REPORT-2 — Read-Only Planning Prompt (run against baseline)

**Phase:** REPORT-2 — Installed RTLs: first real report backend
**Mode:** READ-ONLY PLANNING FIRST; implementation only after reviewer sign-off
**Baseline:** `main` @ `c69c51b` (AUD-1 commit)
**Client gates honoured:** CSV-vs-PDF delivery format, retention/history semantics stay OUT OF SCOPE until client answers (REQ-1B §16 register)

## Objective

Make **Installed RTLs** (`config/reports.py::REPORTS[1]`, key `installed_rtls`) the first report whose Generate button produces a real, data-backed table from PostgreSQL — while the other two reports keep their honest prototype panels.

## Verified current state (do not re-litigate)

- Column contract (client-confirmed): OU | Zone | Sector | CNC | Feeder Name | Transformer | UID | Timestamp of Last Recorded Data | Last Recorded Temperature (°C) | RTL Status
- UI already treats `installed_rtls` specially: date-range hidden, generate enabled (`callbacks/report_center.py:225–233`)
- Generation callback currently returns an explicit "Prototype Only" panel (:368–412); recent-reports table is seeded mock (:21–57)
- Repository already has the proven query SHAPE to copy: `latest_metric_readings` / `latest_reading_times` use `LEFT JOIN LATERAL (... ORDER BY reading_ts DESC LIMIT 1)` — bounded index seek per device, ~14 ms warm vs 3332 ms for DISTINCT ON at 1.38M rows. Copy this shape; never introduce a range scan.
- `latest_metric_readings` deliberately REQUIRES plant_id/transformer_id (no-unbounded-reading-query rule, :644–649). The report's "Entire Fleet" asset scope therefore needs its own purpose-built repository function, not a widening of this one.
- OU/Zone/Sector/CNC/Feeder have NO data mapping (REQ-1B §8: CLIENT CLARIFICATION REQUIRED). REQ-1A forbids inventing the taxonomy mapping.

## Field mapping (frozen pending review)

| Report column | Source |
|---|---|
| OU / Zone / Sector / CNC / Feeder Name | none yet → literal `"—"` placeholder (honest gap, preserves contract layout) |
| Transformer | `transformers.transformer_code` |
| UID | `devices.device_code` |
| Timestamp of Last Recorded Data | newest `readings.reading_ts` of ANY metric for the device |
| Last Recorded Temperature (°C) | newest `temperature` value |
| RTL Status | `devices.status` |

## Design questions the plan must answer

1. New repository function (e.g. `installed_rtls_report_rows`): exact signature — asset-scope params (plant_id/transformer_id/device_id), `allowed_device_ids` scope clause, `include_inactive=False`. One round trip: join hierarchy + two LATERALs (any-metric last ts; temperature last value+ts). Devices that never reported must still appear with NULLs.
2. Service layer `services/report_service.py`: typed row dataclass, placeholder insertion, sorting (transformer then UID?), None→"—" rendering policy, error contract.
3. Scope semantics: session DeviceScope AND asset-scope selection intersect; technician sees only assigned devices.
4. UI: replace prototype panel with a DataTable for installed_rtls only; definition-status honesty notice updated (data-backed vs layout-only); recent-reports mock stays (history is client-gated).
5. Tests: pure (row shaping, placeholder policy) + db-marked (seeded readings incl. never-reported device; scope filtering; empty result honesty).

## Deliverable

Plan only, per §4 structure of AUD-1P: verification header, call-chain map, design answers, file-by-file steps, test plan, risks/open questions, no-modification statement.
