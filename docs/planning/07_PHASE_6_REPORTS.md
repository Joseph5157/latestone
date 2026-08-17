# Phase 6 — Report Center

## Objective

Create a frontend Report Center shell while keeping report types/formats/client delivery rules unresolved.

## Target route

`/reports`

## Important constraint

Current scope does not confirm:

- exact report types
- output format
- scheduled reports
- recipients
- regulatory requirements
- PDF/CSV/Excel expectations

Do not invent them.

## Page design

### Section A — Generate Report

Fields may include only generic frontend concepts:

- Report type — options marked TBD unless client-confirmed
- Asset scope — reuse hierarchy selection
- Date range — reuse existing date controls where practical

Primary action:

`Generate`

Until a real reporting service is available, this may create a frontend prototype result only.

### Section B — Recent Reports

A table/shell may show mock/demo rows only if clearly labeled demo.

Suggested columns:

- Report
- Scope
- Requested
- Status
- Action

Do not implement downloads of fake production reports.

## Reuse

- date range controls
- equipment selector patterns
- entity table
- status badges
- empty states
- loading/error states

## Tests

- route renders
- generic report form validation
- hierarchy/date controls work
- empty-state works
- no unsupported report types hard-coded as authoritative

## Acceptance criteria

- Report Center can be demonstrated.
- Unknown requirements remain visible as TBD.
- No scheduled jobs.
- No email/SMS report delivery.
- No backend generation service.
