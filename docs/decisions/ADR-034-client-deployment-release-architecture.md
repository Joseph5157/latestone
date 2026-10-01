# ADR-034: Client deployment is a filtered Git-tree release, not a working-tree copy

Status: Approved
Date: 2026-10-01
Evidence: `scripts/check_client_release.py`; `scripts/build_client_release.py`;
`docs/context/REPOSITORY_AND_DEPLOYMENT_MAP.md`;
`docs/context/ACTIVE_GATE.md` (CLIENT-LAPTOP-DEPLOYMENT-PREP-01); `.gitignore`;
`docker-compose.yml`; `railway.json`; `.env.example`
Implemented-by: not yet (CLIENT-LAPTOP-DEPLOYMENT-PREP-01; commit/push NOT GRANTED at gate open)

## Context

The project now uses four repositories with distinct roles (recorded in
`REPOSITORY_AND_DEPLOYMENT_MAP.md`):

- `rtl-monitoring-platform-dev` (local remote `latestone`) — active engineering source.
- `rtl-monitoring-platform` (local remote `deployment`) — client deployment/release.
- `RTL-Legacy` (local remote `client`) — old client installation, rollback/reference only.
- `rtl-monitoring-platform-dev-legacy` (local remote `origin`) — historical development reference.

The previous client-delivery mechanism was a hand-curated `client-release`
orphan branch (`docs/CLIENT_DELIVERY.md`). Hand curation is not a control:
CLIENT-SYNC-2A and CLIENT-SYNC-5 each found internal material tracked on the
delivery path that only stayed unshipped because the manual copy happened to
be conservative. The development working tree also contains material that must
never reach a client release — a 424 MB `RTL.bak` client database backup, a
real `.env`, `.test-tmp/`, scratch and agent tooling — all of which are
`.gitignore`d but would be swept in by any "copy the folder" approach.

## Decision

1. **The development repository is the authoritative engineering source.** All
   features, gates, ADRs and context live in `rtl-monitoring-platform-dev`.

2. **The deployment repository holds approved release snapshots only.** It is
   never a feature-development target. Work is not pushed there outside an
   explicit client-release/deployment gate.

3. **A release originates from one exact development commit SHA.** The release
   is identified by that SHA (and a release tag), never by "current working
   copy" or "latest main at the time someone ran it."

4. **Release content is generated from tracked Git-tree content, not the
   working directory.** Generation reads `git` objects at the approved SHA
   (`git ls-tree` / `git show` / `git archive`). Untracked and `.gitignore`d
   files are therefore structurally impossible to include — `.env`, `*.bak`,
   `.test-tmp/`, scratch and agent tooling can never leak by construction.

5. **Explicit include/exclude validation is mandatory before any push.** The
   exclusion contract has a single source of truth,
   `scripts/check_client_release.py`. The deterministic exporter
   (`scripts/build_client_release.py`) reuses that same rule set, so the build
   and the check can never drift. A release that fails validation is not
   pushed.

6. **The client laptop clones/pulls only from the deployment repository.** It
   never pulls from a development or legacy repository.

7. **Legacy repositories remain rollback/reference only.** `RTL-Legacy` and
   `rtl-monitoring-platform-dev-legacy` are not modified and not deleted until
   the new installation is verified in production.

## Release exclusion contract (enforced by `check_client_release.py`)

Excluded from every release: `docs/audit/**`, `docs/context/**`,
`docs/decisions/**`, `docs/archive/**`, `docs/planning/**`, `docs/superpowers/**`,
`command center/`, `.claude/**`, internal planning/roadmap docs, `AGENTS.md`,
`CLAUDE.md`, the REQ matrices, `SQL_QUERIES.sql`, the client PAD PDF and its
text extracts, `railway.json`, `check_databases.py`, the context-pack and
release tooling, the workflow-PDF generators, `*.bak`, `*.log`, `*.dump`,
`*.sql.gz`, and every `.env*` except `.env.example`. The general `tests/` tree
is not shipped (ADR-034 §TESTS below).

## Consequences

- Releases are reproducible: the same SHA yields the same tree.
- Secrets and client evidence cannot be shipped by accident.
- A new gate (not this one) authorizes the first actual push to `deployment`.
- `docs/CLIENT_DELIVERY.md` orphan-branch guidance is superseded as the final
  delivery architecture by this ADR; it remains a historical record.

## TESTS

The development `tests/` tree is not part of a client release. If installation
verification needs a check, it is a small, clearly client-safe deployment
verification step documented in `docs/CLIENT_INSTALLATION.md`
(`python -m scripts.auth_preflight --force`, migration-head check, a browser
acceptance pass), not the development suite — which depends on fixtures and
tooling that are themselves not delivered.
