# Phase 7 — Notification Center

## Objective

Create a frontend notification/attention center without implementing delivery infrastructure.

## Target route

`/notifications`

## Scope boundary

Do not implement:

- SMS sending
- email sending
- Exchange integration
- push notifications
- alert threshold engines
- RabbitMQ
- Maximo notifications

## What the frontend may support

A generic inbox/list experience for events already known to the frontend.

Possible safe examples:

- stale data
- no data
- communication restored, only if existing logic can establish it

Do not invent high-temperature or vibration alarms unless those states are already supported by the current application.

## UI design

Filters:

- All
- Unread
- Device
- Transformer

Only expose filters that map to real frontend data.

Table/list:

- Time
- Entity
- Message
- Read/unread state

Acknowledgment should NOT be implemented unless client workflow confirms it.

## Data provider

Use a notification view model and mock/local provider.

Do not bind notification UI directly to future delivery infrastructure.

## Tests

- route renders
- empty state
- filters
- stale/no-data messages are semantically truthful
- no unsupported alarm types
- no delivery integration

## Acceptance criteria

- Notification Center exists as a frontend shell.
- It does not claim SMS/email was sent.
- It does not invent alarm thresholds.
- It reuses current freshness semantics.
