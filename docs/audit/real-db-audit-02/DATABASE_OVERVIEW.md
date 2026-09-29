# REAL-DB-AUDIT-02 — Database overview

Status: complete — inspection only.
Source: `RTL.bak`, supplied by the client as the current authoritative database artifact.
Audit execution date: 2026-09-29. No application or PostgreSQL database was accessed or changed.

## Backup and restore evidence

| Item | Result |
|---|---|
| Backup artifact | `RTL.bak`, 424,401,408 bytes; mounted read-only in the inspection container |
| Backup database name | `RTL` |
| Backup sets | Two full database backups (positions 1 and 2) |
| Restored set | Position 2, the latest: 2026-09-27 15:58:53 to 15:58:54 |
| Backup type / recovery | Full database / SIMPLE recovery model |
| Backup source | `ARUN\\SQLEXPRESS`, SQL Server major version 16, database compatibility level 160 |
| Source SQL metadata | SQL Server 2022 (16.0.1000) indicated by backup fields; source collation `SQL_Latin1_General_CP1_CI_AS` |
| Backup size | Position 1: 228,281,344 bytes; position 2: 196,103,168 bytes (not compressed) |
| `RESTORE VERIFYONLY` | Passed for both position 1 and position 2 |
| Logical data file | `RTL`, original path `C:\\Program Files\\Microsoft SQL Server\\MSSQL16.SQLEXPRESS\\MSSQL\\DATA\\RTL.mdf`, 276,824,064 bytes |
| Logical log file | `RTL_log`, original path `C:\\Program Files\\Microsoft SQL Server\\MSSQL16.SQLEXPRESS\\MSSQL\\DATA\\RTL_log.ldf`, 209,715,200 bytes |
| Local restore | `RTL_AUDIT_02`, separate Docker volume, restored successfully from position 2 |
| Inspection state | `ONLINE`, `READ_ONLY`, no host port published |

The audit server was a separate local SQL Server 2022 Developer container (16.0.4295.3 on Linux). The supplied backup was never written to or copied into the working tree.

## Database shape

There is one schema containing client application objects: `dbo`. SQL Server also has the normal `guest`, `INFORMATION_SCHEMA`, `sys`, and nine database-role schemas; those contain no client tables considered in this audit.

| Object class | Count |
|---|---:|
| User tables | 19 |
| Views | 4 |
| Stored procedures | 0 |
| Functions | 0 |
| DML triggers | 0 |
| Sequences | 0 |
| Synonyms | 0 |
| Check constraints | 0 |
| Declared foreign keys | 3 |

The central historical measurements table is `dbo.master_temperature` with 2,456,901 rows. The database is a SQL Server RTL/transformer-temperature operational database, not the legacy PostgreSQL `trfr_temperature` system described in earlier repository documents.

## Scope and data handling

All inspection queries were read-only after restoring the disposable copy. Documentation records metadata, counts, aggregate observations, object definitions, and value-free representative row shapes. Names, telephone numbers, email addresses, API keys, password hashes, and other sensitive values were not copied into this repository.

See [FINAL_DATABASE_AUDIT.md](FINAL_DATABASE_AUDIT.md) for the consolidated model and the linked catalogues for the detailed evidence.
