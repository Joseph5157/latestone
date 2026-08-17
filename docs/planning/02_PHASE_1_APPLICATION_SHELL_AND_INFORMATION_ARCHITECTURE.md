# Phase 1 — Application Shell and Information Architecture

## Objective

Separate application navigation from equipment navigation without breaking the current monitoring hierarchy.

## Current problem

The current user journey is primarily:

`Login → Fleet → Plant → Transformer → Device`

This is excellent for monitoring drill-down, but future frontend business workflows need top-level destinations such as Devices, Reports, Notifications, and Administration.

The existing Plant → Transformer → Device selector must remain an equipment-navigation tool, not become the entire application navigation system.

## Target concept

Application navigation:

- Overview
- Monitoring
- Devices
- Reports
- Notifications
- Administration

Equipment navigation remains available inside monitoring context:

- Plant
- Transformer
- Device

## Scope

Implement the application shell/navigation structure only.

Do not build the full destination pages yet.

## Tasks

### 1. Inspect current global layout

Find the current mounting point for:

- app header
- equipment selector
- page content
- auth state
- route location

Preserve the requirement that the equipment selector remains globally mounted if callbacks depend on permanent targets.

### 2. Define route constants

Add only the minimal route definitions needed for:

- `/plants` or existing overview route
- `/admin/devices`
- `/reports`
- `/notifications`
- `/admin/users`

Do not add role-management or alarm-configuration routes yet unless already required by current code.

### 3. Create top-level app navigation

Add a reusable application navigation component.

Requirements:

- enterprise/full-width style
- visually compact
- accessible keyboard focus
- active-page indication
- does not duplicate breadcrumbs
- does not replace the equipment selector
- hidden on login
- responsive behavior consistent with existing CSS
- no new external UI framework unless already used

### 4. Add safe placeholder destinations

For routes not implemented yet, create minimal placeholder pages containing:

- page title
- one-sentence purpose
- “Design/implementation pending client-approved frontend scope” message

Do not invent forms, fields, roles, report types, or notifications.

### 5. Preserve existing monitoring routes

Existing deep links must continue to work:

- Fleet
- Plant
- Transformer
- Device

### 6. Tests

Add tests for:

- route parsing/building if route helpers exist
- top-level nav visible only when authenticated
- active navigation state
- placeholder route rendering
- no regression to existing monitoring routes

## Acceptance criteria

- Existing monitoring navigation is unchanged.
- Top-level app navigation is visually distinct from the equipment selector.
- Login has no application navigation.
- All new nav links resolve without 404/error.
- No backend/database changes.
- No new business fields invented.
- Existing test suite remains green.

## Explicit non-goals

- Side effects
- CRUD
- user permissions
- role enforcement
- report generation
- notification behavior
- API calls
