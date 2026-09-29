# REAL-DB-AUDIT-02 — Identifier analysis

| Identifier | Type / origin | Cardinality and enforcement | Used by | Relationship status |
|---|---|---|---|---|
| `device_uid` | `int`; device/RTL identifier | 339 registered UIDs in `device_list`, uniquely constrained; 400 in telemetry | device list/status, mappings, readings, most logs, assignment tables | Declared only for `technician_assignments → device_list`; all other use is inferred |
| `trfr` | `nvarchar(20)` in core tables; transformer code | 185 distinct mapping codes; 1,732 labels in telemetry | mapping, status, readings, logs | No declared FK or unique constraint; pair/UID matching only |
| `trfr_list.id` | identity `int` | 185 PK values | mapping table | Surrogate only; no one references it |
| `device_status.device_uid` | `int` | 339 PK values | current-status table | Strong inferred one-to-one with registered UID |
| `tug_report.id` | identity `int` | 70,738 PK values | asset/hierarchy source | No direct reference |
| first description token | derived string | 178 view-join hits | `tug_report` to `trfr_list` | Inferred string rule in view, not a schema relationship |
| person/role IDs | identity `int` | persons 8; roles 3 | identity/permissions | Declared FKs as catalogued |

## Count mismatch, explicitly not forced into a mapping

| Population | Count | Reconciliation |
|---|---:|---|
| Telemetry UIDs | 400 | 319 overlap with registered device UIDs; 81 telemetry UIDs have no `device_list` record |
| Registered devices / current statuses | 339 / 339 | Same UID set by observed one-to-one match; 20 registered UIDs have no telemetry row |
| Transformer mappings | 185 | All 185 mapping UIDs occur in telemetry and in `device_list`; 183 exact `(UID,trfr)` pairs occur in telemetry |
| Telemetry transformer labels | 1,732 | Far exceeds the 185 mapping codes; labels must not be silently normalized to the mapping table |
| Telemetry UID/transformer pairs | 2,072 | Shows that a UID may appear with multiple transformer labels |

The 81 telemetry-only UIDs and 20 registered-without-telemetry UIDs are reported as unmapped/orphan populations, not assigned to another entity. Two mapping pairs do not match an exact telemetry `(UID,trfr)` pair despite all mapped UIDs appearing in telemetry. The database evidence cannot establish whether this is historical reassignment, data-quality drift, or intended semantics.
