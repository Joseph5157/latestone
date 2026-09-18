# Repository and Deployment Map

Status: **AGREED WORKING BASELINE**
Date recorded: 2026-09-14
Last updated: 2026-09-18 — added the Railway demo deployment (§4a)

This document records the agreed repository, machine, and delivery boundaries for the RTL project so future work does not confuse development, client delivery, and the client's Azure integration area.

## 1. Main development environment

Primary development happens on the development PC.

Local checkout:

`C:\Users\sikha\Videos\power\powerplant-dashboard`

Main development repository:

`https://github.com/Joseph5157/powerplant-monitoring`

Rules:

- New application features are developed and tested here first.
- This repository is the authoritative development source.
- Project context, implementation gates, and development history belong here.

## 2. Client delivery repository

Client delivery repository:

`https://github.com/Joseph5157/powerplant-dashboard-client`

Rules:

- Accepted development milestones are synchronized here for client delivery.
- This repository is not the primary development source.
- The normal client delivery branch is still a deliberate decision to be finalized; do not assume a permanent branch policy until recorded separately.

## 3. Client laptop application checkout

Verified client-laptop application path:

`C:\Users\Admin\Videos\power\powerplant-dashboard-client-main\powerplant-dashboard-client-main`

Purpose:

- Client demo and acceptance environment.
- Pulls accepted application code from the client delivery repository.
- Local `.env`, `.venv`, credentials, backups, logs, and other machine-local state must not be copied into Git.

## 4. Client Azure integration repository/folder

The client created a separate Azure-oriented repository/folder on the client laptop:

`C:\Users\Admin\Videos\power\powerplant-dashboard-client-main\Remote_Temperature_Logger`

Current WebApp destination provided by the client:

`C:\Users\Admin\Videos\power\powerplant-dashboard-client-main\Remote_Temperature_Logger\projects\webapp`

Important ownership boundary:

- Azure development is owned by the client, not by this development team.
- The client controls Azure pipelines, Kubernetes, App Service/startup configuration, database platform choice, credentials/secrets, and deployment execution.
- Our responsibility is to provide or copy the accepted WebApp application code into the client-provided WebApp area when requested.
- We must not infer or redesign the client's Azure infrastructure unless explicitly asked.
- We currently do not know whether the deployed Azure WebApp will use PostgreSQL or SQL Server; this remains a client-side integration decision.

## 4a. Railway demo deployment

A hosted showcase of the development application for the client, separate
from both the client laptop and the client's Azure area. It is a demo
environment, not the client's production system.

- Railway project `powerplant-monitoring`, environment `production`, with
  three services: `dashboard` (this application), `live-simulator`
  (`db/live_simulator.py`, appends synthetic readings on a timer so data
  stays fresh) and `Postgres`.
- `dashboard` deploys automatically on every push to `main` of the
  development repository, using the checked-in `railway.json`.
- Every deploy runs `python -m alembic upgrade head` as Railway's
  `preDeployCommand` before new instances go live (added 2026-09-18,
  `ce42a36`). Before that, the Railway database silently stayed at
  `007_audit_log` while code moved on, and Command Center returned HTTP 500.
  A failing migration now fails the deploy instead of shipping mismatched
  code.
- The Railway database host (`postgres.railway.internal`) resolves only
  inside Railway. One-off database commands run through
  `railway ssh` into the `dashboard` service, not from a development machine.
- The live simulator writes readings only, never `device_events`, so the
  Railway demo shows all RTLs Fresh and an empty Recent Operational Events
  list. That differs from local development data (older readings plus seeded
  events) by design, not because of a code difference.
- Credentials live in Railway service variables and are never committed.

This automatic migration applies to Railway only. It does not change the
§6 rule for the client's Azure deployment.

## 5. Agreed delivery flow

The agreed working flow is:

```text
Development PC
C:\Users\sikha\Videos\power\powerplant-dashboard
        |
        | develop + test
        v
GitHub development repo
Joseph5157/powerplant-monitoring
        |
        | accepted milestone
        v
GitHub client delivery repo
Joseph5157/powerplant-dashboard-client
        |
        | client laptop pulls
        v
Client laptop verified application
C:\Users\Admin\Videos\power\powerplant-dashboard-client-main\powerplant-dashboard-client-main
        |
        | controlled application-code transfer when requested
        v
Client Azure integration area
Remote_Temperature_Logger\projects\webapp
        |
        v
Client handles Azure deployment/integration
```

## 6. Safety rules

- Do not treat `Remote_Temperature_Logger` as the main application-development repository.
- Do not treat Azure deployment configuration as owned by this project team.
- Do not copy `.env`, `.venv`, credentials, database dumps, local logs, `__pycache__`, or other machine-local state between repositories.
- Do not perform whole-directory mirroring into the Azure repository without a reviewed file-level plan.
- Application database migrations for Azure must not be executed merely because migration files are copied; migration execution requires a separate approved deployment step.
- Simulator/demo functionality must remain clearly separated from real RTL communication and must be explicitly identified as simulated when enabled.

## 7. Open decisions

The following remain intentionally unresolved and must not be invented:

- Which branch in `powerplant-dashboard-client` should become the normal client update/release branch.
- The client's Azure WebApp build/startup/deployment mechanism.
- The client's Azure database platform and connection contract.
- Who will execute production/Azure database migrations.
- Exact simulator scope and whether the simulator should run only on the client laptop, in Azure, or both.
