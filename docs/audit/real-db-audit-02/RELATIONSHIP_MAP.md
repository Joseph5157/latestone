# REAL-DB-AUDIT-02 — Relationship model

## Declared relationships

```text
dbo.roles (3)
   └── dbo.persons (8)               persons.role_id → roles.role_id

dbo.persons (8) ──────┐
                      ├── dbo.technician_assignments (0)
dbo.device_list (339) ┘    person_id → persons; device_uid → device_list
```

These are the database's only three foreign keys. There are no declared FKs from telemetry, logs, current status, transformer mapping, or organisation data.

## Inferred operational relationships

```text
dbo.device_list (339 registered UIDs)
   └─ same device_uid, not FK ── dbo.device_status (339; current status)
                                     │
dbo.trfr_list (185 transformer UID mappings) ─ same device_uid, not FK ─┘
   │
   ├─ 183 exact (UID, transformer) pairs occur in master_temperature
   └─ all 185 mapped UIDs occur in master_temperature

dbo.master_temperature (2,456,901 readings)
   └─ device_uid and trfr values, no FK/PK/index
      └─ logs use the same named columns: alarm, startup, powerdown,
         sensor-error, invalid-UID, communications, and settings uploads

dbo.tug_report (70,738 asset/hierarchy records)
   └─ view-only inferred join:
      LEFT(tug_report.description, CHARINDEX(' ', description)-1) = trfr_list.trfr
      └─ 178 joined rows for the 185 mappings
```

`vw_transformer_org_hierarchy` implements the final inferred relationship, and the other views consume it. It is **not** an FK and its string-token rule must not be treated as a guaranteed identifier relationship.

## Terminology discovered from database evidence

| Term | Evidence | Conclusion |
|---|---|---|
| Transformer | `trfr` appears in mapping, readings, status and event tables; `trfr_list` maps it to UID | A short transformer code, not a declared entity key |
| Device / RTL | `device_uid` is the key in `device_list`, `device_status`, telemetry and logs; views label it `UID` and are named `rtl` | Database uses device UID as the closest RTL/device identifier |
| Site / station / substation | `tug_report` has `ohl_substation_description`, location, voltage and class fields | Asset/hierarchy source, linked only by an inferred transformer-code string rule |
| Organisation hierarchy | `operating_unit`, `zone`, `sector`, `cnc` in `tug_report`; exposed by views as OU/Zone/Sector/CNC | Actual hierarchy vocabulary; not a plant hierarchy |
| Plant | No table/column/object found using plant terminology | NOT FOUND |
| Logger / sensor | No separate logger or sensor master entity found; event table names identify message/sensor conditions | AMBIGUOUS; could be the RTL/device itself |

The database does not contain a declared device-to-transformer FK. `trfr_list` is the strongest mapping evidence; `device_status` repeats an optional transformer value, and readings repeat both values without referential constraints.
