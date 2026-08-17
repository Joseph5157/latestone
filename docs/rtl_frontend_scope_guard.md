# RTL Frontend Scope Guard

*Phase 0 deliverable — created 2026-08-17.*
*Authoritative inputs: `docs/planning/00_README.md`, `docs/planning/01_PHASE_0_BASELINE_AND_GUARDRAILS.md`, `docs/PAD_SECTIONS_1_TO_3_4_AUDIT.md`.*

## Purpose

This document records the fixed scope boundary for the RTL frontend work that
follows. It exists so that later phases can be checked against an explicit,
written boundary instead of an evolving recollection of the plan. If a proposed
change conflicts with any statement below, the conflict must be reported and
resolved before implementation proceeds.

## Scope statements

1. **Current client scope is PAD Sections 1–3.4 only.**
   Client instruction is to work from PAD Sections 1 through 3.4 (Business
   Architecture) for now. Requirements found only in later PAD sections may be
   read for context but must not expand current implementation scope.

2. **Current work is frontend-focused.**
   The goal of the phase plan is to preserve the strong existing monitoring
   application and close the frontend gaps implied by the current business
   process scope. This is a frontend-focused RTL application effort.

3. **Existing database is development/mock infrastructure.**
   The `plant_monitoring` schema (30 plants, 71 transformers, 120 devices,
   ~1.38M synthetic readings) is our development model. It is not the client's
   production schema. Client production appears to use a schema such as
   `trfr_temperature` with tables named like `aa12_29017` (transformer_device)
   and approximately 2,112 tables.

4. **Production database schema is not confirmed.**
   No client production schema is available yet. Do not design frontend
   behaviour around assumptions about the production data model. The repository
   layer is the single seam through which a later production schema can be
   introduced without touching UI code.

5. **Backend ownership is not confirmed.**
   It is not established whether this application owns the backend/API, or
   whether it consumes a separately owned backend. Do not expand into backend,
   API, integration, cloud, or security work on this project's authority.

6. **No later PAD technical architecture is to be implemented yet.**
   The following are out of scope for these phases: new backend/API services,
   FastAPI or another backend framework, production database schema changes,
   MQTT or RabbitMQ, Maximo integration, Microsoft Entra ID production
   integration, Kubernetes or Azure deployment, SMS/email delivery integrations,
   ML/anomaly engines, and alarm thresholds not supplied by the client.

7. **New UI must use services/repositories or mock interfaces rather than
   direct new SQL from pages.**
   The architecture rule holds: UI, page and component code never executes SQL.
   Only `repositories/plant_monitoring_repository.py` builds SQL. New frontend
   workflows must obtain data through services or through clearly marked mock
   interfaces — never by adding SQL to page, component or callback code.

## Consequence for later phases

Every later phase must be consistent with the statements above. In particular,
when a phase implies data a service/repository cannot currently provide, the
phase plan must say whether it will extend the repository within the
development schema, introduce a mock interface, or be deferred — and that
decision must be reported to the human before implementation.