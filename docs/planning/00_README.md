# RTL Frontend Phase-by-Phase Implementation Pack

## Purpose

This pack is designed to let OpenCode implement the RTL frontend in controlled phases without asking the model to redesign the project from scratch.

The current client instruction is to work only from PAD Sections 1 through 3.4 for now.

The existing monitoring application is already strong. The goal of these phases is to preserve that work, close the frontend gaps implied by the current business-process scope, and avoid accidental expansion into backend, database, integration, cloud, or security work.

## Authoritative inputs

1. Client PAD: `DEM-2788838 Digital Incubator - RTL PAD v0.7`
2. Repository audit: `PAD_SECTIONS_1_TO_3_4_AUDIT.md`
3. Existing repository code and tests
4. RTL Functional Specification: `docs/specs/RTL_FUNCTIONAL_SPEC_EXTRACT.md`

If the repository conflicts with an assumption in these plans, OpenCode must report the conflict before implementing it.

## Non-negotiable scope boundary

For these phases, do NOT implement:

- New backend/API services
- FastAPI or another backend framework
- Production database schema changes
- MQTT or RabbitMQ
- Maximo integration
- Microsoft Entra ID production integration
- Kubernetes or Azure deployment
- SMS/email delivery integrations
- ML/anomaly engines
- Alarm thresholds not supplied by the client
- Any requirement taken only from PAD sections after 3.4

Later PAD sections may be read only for context if needed, but must not be used to expand current implementation scope.

## Existing assets to preserve

The audit identifies these as strong and reusable:

- `routes.py`
- `callbacks/routing.py`
- `services/auth_service.py`
- `callbacks/auth.py`
- `services/hierarchy_service.py`
- `services/monitoring_service.py`
- `repositories/plant_monitoring_repository.py`
- `config/metrics.py`
- `pages/device_dashboard.py`
- `callbacks/device.py`
- `components/entity_table.py`
- `components/equipment_selector.py`
- existing freshness components
- existing KPI/chart/table components
- `assets/app.css`
- existing tests and design specifications

Do not rewrite these areas unless a phase explicitly requires a narrow change.

## Phase Status

### Core phases

| Phase | Description | Status |
|-------|-------------|--------|
| Phase 0 | Baseline and guardrails | COMPLETE |
| Phase 1 | Application shell and information architecture | COMPLETE |
| Phase 1A | Navigation refinement | COMPLETE |
| Phase 2 | Overview / Needs Attention | COMPLETE |
| Phase 3 | Device Administration | COMPLETE |
| Phase 4 | Device Registration and Assignment UX | COMPLETE |
| Phase 5 | User Administration | COMPLETE |
| Phase 6 | Reports | COMPLETE |

### Requirements-alignment phases

| Phase | Description | Status |
|-------|-------------|--------|
| Phase 5A | Role Alignment | COMPLETE |
| Phase 4A | Device Workflow Alignment | COMPLETE |
| Phase 6A | Report Definition Alignment | COMPLETE |
| Phase 7R | Revised Notification Center | COMPLETE |

### Upcoming phases

| Phase | Description | Status |
|-------|-------------|--------|
| Phase 8 | Metric / Vibration Readiness | NOT STARTED |
| Phase 9 | Client Review Gate | NOT STARTED |

**Note:** The original Phase 7 plan (Notification Center shell) was superseded by Phase 7R, because the client Functional Specification later confirmed formal notification requirements that differed from the original freshness-based approach.

## Execution order

Run one phase at a time.

Do not give OpenCode the whole pack and say "implement everything."

For each phase:

1. Give OpenCode the phase file.
2. Ask it to inspect the repository before editing.
3. Require a short implementation plan.
4. Let it implement only that phase.
5. Run the acceptance checks/tests.
6. Review the result before moving to the next phase.

## Definition of success

At the end of the current scope, the project should remain a frontend-focused RTL application with:

- preserved monitoring functionality
- clearer application-level navigation
- improved overview/exception visibility
- frontend designs/workflows for device operations
- frontend designs/workflows for users
- report center with confirmed RTL report definitions
- notification center with confirmed business notification categories
- vibration-ready UI structure without fabricating unsupported backend/data behavior

The implementation must remain compatible with later client-provided database/backend decisions.
