# Local client RTL SQL Server database

## Purpose and safety boundary

`rtl_sqlserver` is a persistent, local Docker SQL Server 2022 service holding a restored copy of the client-supplied `RTL.bak` database. It is separate from the `postgres` service, which remains the application-owned PostgreSQL database.

> **THIS IS A LOCAL RESTORED COPY OF THE CLIENT DATABASE.**
>
> **THE APPLICATION MUST NEVER MIGRATE OR ALTER `RTL`.**

The backup stays read-only at `/var/opt/mssql/backup/RTL.bak`; it is not included in an image. Database files live only in Docker volume `plant-monitoring-arch_client_rtl_sqlserver_data`, not in the Git working tree. SQL Server is published only at `127.0.0.1:14333` by default.

## Configuration

The ignored local `.env` holds actual SQL Server secrets. `.env.example` contains placeholders only:

```text
RTL_SQLSERVER_CONTAINER_NAME=client_rtl_sqlserver
RTL_DB_HOST=localhost
RTL_DB_PORT=14333
RTL_DB_NAME=RTL
RTL_DB_USER=rtl_app_reader
RTL_DB_PASSWORD=<local reader password>
RTL_SQL_SA_PASSWORD=<local administration/restore password>
```

`RTL_SQL_SA_PASSWORD` is only for container administration and restoration. Do not use it in an application. `rtl_app_reader` is the intended inspection/future-application login and has database `SELECT` only; it has explicit `DENY INSERT, UPDATE, DELETE` and no `ALTER`, `CREATE`, `DROP`, or `CONTROL` grant.

## Start and stop

Start just the client database:

```powershell
docker compose up -d rtl_sqlserver
docker compose ps rtl_sqlserver
```

Stop it without removing its data:

```powershell
docker compose stop rtl_sqlserver
```

`docker compose restart rtl_sqlserver` and a Docker container restart retain the restored database because the named Docker volume persists.

## One-time restore procedure

The current managed volume already contains the verified restore from backup position 2 (the latest full backup, 2026-09-27). For an intentionally new empty volume only:

1. Confirm the supplied backup hash before restore:

   ```powershell
   Get-FileHash -LiteralPath RTL.bak -Algorithm SHA256
   # Expected: 31EF1C5CEC147BACDB736BDCDD8AEEAB601FE6C18E84EA188DAB45BB54DE6AD5
   ```

2. Start the service and load the local SA password from ignored `.env` without printing it:

   ```powershell
   docker compose up -d rtl_sqlserver
   $saPassword = ((Get-Content .env | Select-String '^RTL_SQL_SA_PASSWORD=').Line -replace '^RTL_SQL_SA_PASSWORD=','')
   ```

3. Inspect the logical files, verify backup set 2, then restore it to the Docker data directory:

   ```powershell
   docker exec client_rtl_sqlserver /opt/mssql-tools18/bin/sqlcmd -C -S localhost -U sa -P $saPassword -Q "RESTORE FILELISTONLY FROM DISK=N'/var/opt/mssql/backup/RTL.bak'; RESTORE VERIFYONLY FROM DISK=N'/var/opt/mssql/backup/RTL.bak' WITH FILE=2;"

   docker exec client_rtl_sqlserver /opt/mssql-tools18/bin/sqlcmd -C -b -S localhost -U sa -P $saPassword -Q "RESTORE DATABASE [RTL] FROM DISK=N'/var/opt/mssql/backup/RTL.bak' WITH FILE=2, MOVE N'RTL' TO N'/var/opt/mssql/data/RTL.mdf', MOVE N'RTL_log' TO N'/var/opt/mssql/data/RTL_log.ldf';"
   ```

4. Before locking the restored database read-only, create the narrow reader principal. This creates only required SQL Server security metadata; it does not alter client tables, columns, or data.

   ```powershell
   $readerPassword = ((Get-Content .env | Select-String '^RTL_DB_PASSWORD=').Line -replace '^RTL_DB_PASSWORD=','')
   $securitySql = "CREATE LOGIN [rtl_app_reader] WITH PASSWORD=N'$readerPassword', CHECK_POLICY=ON, CHECK_EXPIRATION=OFF; USE [RTL]; CREATE USER [rtl_app_reader] FOR LOGIN [rtl_app_reader]; GRANT SELECT TO [rtl_app_reader]; DENY INSERT, UPDATE, DELETE TO [rtl_app_reader]; ALTER DATABASE [RTL] SET READ_ONLY WITH ROLLBACK IMMEDIATE;"
   docker exec client_rtl_sqlserver /opt/mssql-tools18/bin/sqlcmd -C -b -S localhost -U sa -P $saPassword -Q $securitySql
   ```

Do not run Alembic, seeders, migrations, or DDL against `RTL`.

## Availability and integrity verification

Use the reader account, never SA, for normal availability checks:

```powershell
$readerPassword = ((Get-Content .env | Select-String '^RTL_DB_PASSWORD=').Line -replace '^RTL_DB_PASSWORD=','')
$sql = "SELECT DATABASEPROPERTYEX(N'RTL',N'Status') AS status, DATABASEPROPERTYEX(N'RTL',N'Updateability') AS updateability; SELECT (SELECT COUNT(*) FROM dbo.master_temperature) AS master_temperature_rows, (SELECT COUNT(DISTINCT device_uid) FROM dbo.master_temperature) AS telemetry_uids, (SELECT COUNT(*) FROM dbo.device_list) AS device_records, (SELECT COUNT(*) FROM dbo.trfr_list) AS transformer_mappings;"
docker exec client_rtl_sqlserver /opt/mssql-tools18/bin/sqlcmd -C -b -S localhost -U rtl_app_reader -P $readerPassword -d RTL -Q $sql -W -s "|"
```

Expected output:

| Check | Expected |
|---|---:|
| Status | `ONLINE` |
| Updateability | `READ_ONLY` |
| `master_temperature` rows | 2,456,901 |
| Distinct telemetry UIDs | 400 |
| `device_list` rows | 339 |
| `trfr_list` rows | 185 |

An attempted `UPDATE` or `INSERT` using `rtl_app_reader` must fail with a permission denial. This was verified when this environment was provisioned.

## Intentional rebuild only

Rebuilding destroys the **local Docker copy**, never the backup. Do this only when intentionally resetting the local environment:

```powershell
docker compose stop rtl_sqlserver
docker volume inspect plant-monitoring-arch_client_rtl_sqlserver_data
docker volume rm plant-monitoring-arch_client_rtl_sqlserver_data
docker compose up -d rtl_sqlserver
```

Then perform the one-time restore procedure above. Do not delete, move, rename, modify, or replace `RTL.bak`.

## Safety review

The current application remains PostgreSQL-oriented and no source file references `RTL_DB_*`, SQL Server, `pyodbc`, or `mssql` as an application connection. Existing Alembic migrations and application write SQL target the application-owned PostgreSQL configuration. The future integration risk is therefore architectural: any future SQL Server connector must use `RTL_DB_*` and `rtl_app_reader`, must never reuse the PostgreSQL/Alembic connection path, and must remain read-only.
