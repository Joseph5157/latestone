# Client Release Notes

Operational release notes for the client deployment repository
(`rtl-monitoring-platform`). One entry per approved release. Each release is a
deterministic filtered Git-tree export from an exact development SHA (ADR-034).

## Unreleased — first client deployment (prepared, not yet pushed)

- **Source development SHA:** `881e522e6bd1a9ce7239fd2f6d23b5099092540a`
  (`rtl-monitoring-platform-dev`, branch `main`).
- **Proposed release tag:** `client-v0.1.0` (see tag strategy below).
- **Status:** prepared under CLIENT-LAPTOP-DEPLOYMENT-PREP-01; **not yet
  pushed** to the deployment repository (push authorization pending owner
  review).

### What this release contains
- The RTL monitoring application: Registered RTLs, RTL detail and temperature
  history, Network, Historical Events, Technician Assignments, Reports, Users
  and authentication, Settings.
- Application database migrations through `017_local_auth_hardening`.
- Read-only client SQL Server integration for RTL temperature data.
- Local/dev quickstart (`GETTING_STARTED.md`) and the production install guide
  (`CLIENT_INSTALLATION.md`).

### What this release excludes
- All internal engineering material (context, decisions, audits, plans, client
  correspondence, agent tooling), development-only scripts, secrets and the
  client database backup. See the include/exclude contract in ADR-034 and
  `scripts/check_client_release.py`.

### Install / upgrade
- Fresh install: follow `docs/CLIENT_INSTALLATION.md` (new folder).
- The previous installation and `RTL-Legacy` remain available for rollback.

### Known notes
- Windows production start command: `waitress-serve --listen=0.0.0.0:8050 app:server`
  (Gunicorn is Linux/Railway only). See `CLIENT_INSTALLATION.md` step 10.
