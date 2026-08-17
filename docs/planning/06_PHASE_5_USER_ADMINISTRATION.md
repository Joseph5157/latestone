# Phase 5 — User Administration

## Objective

Create a frontend user-management shell without inventing the production identity/role model.

## Important source constraint

PAD Sections 3.1 and 3.2 list business/project stakeholders.

Those names/roles are NOT automatically runtime application roles.

Do not convert Business Owner, Business Requester, Team Lead, SME, BA, Lead Architect, or Solution Architect into application permissions.

## Target route

`/admin/users`

## Page purpose

Provide a frontend framework for:

- user list
- user status
- future add/edit/deactivate actions
- future role assignment

## UI design

Toolbar:

- search
- status filter
- Add User

Table:

- User
- Identifier/email only if existing auth/domain model safely supports it
- Role: show `TBD`/unassigned if role model not confirmed
- Status
- Actions

## Tasks

### 1. Create a frontend user view model

Keep it independent of Microsoft Entra ID and client database.

### 2. Build user list page

Use existing table/layout patterns.

### 3. Add User/Edit User prototype

Only expose fields that are already supported by current local auth model or explicitly marked prototype.

### 4. Role handling

Do not create permission logic.

A role selector may be shown only as:

- disabled
- placeholder
- `Client role model required`

unless runtime roles have been formally confirmed.

### 5. Authentication separation

Do not alter login authentication flow in this phase except where necessary to expose navigation.

Do not implement Entra ID.

### 6. Tests

- page renders
- search/status filter
- no role-permission assumptions
- no authentication regression
- no direct production persistence

## Acceptance criteria

- `/admin/users` exists and is visually consistent.
- Role model remains unresolved rather than invented.
- Existing demo login still functions.
- No Entra ID implementation.
- No backend/database changes.
