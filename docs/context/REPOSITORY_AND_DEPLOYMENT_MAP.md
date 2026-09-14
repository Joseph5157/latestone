# Repository and Deployment Map

Status: **AGREED WORKING BASELINE**
Date recorded: 2026-09-14

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
