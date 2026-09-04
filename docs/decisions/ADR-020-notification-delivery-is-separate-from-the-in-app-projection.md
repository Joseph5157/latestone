# ADR-020: Notification delivery is a separate boundary from the in-app Notification Center

Status: Approved
Date: 2026-09-04
Evidence: `services/notification_delivery.py` (`DeliveryRequest`,
`DeliveryResult`, `NotificationDelivery`); `services/mock_notification_delivery.py`
(`MockNotificationDelivery`); `services/notification_service.py` (unchanged
— `NotificationRow`, `current_notifications()`); `services/event_semantics.py`
(unchanged); `services/message_forwarding_service.py` (unchanged);
`tests/test_notification_delivery.py`
Implemented-by: not yet
Supersedes: nothing — extends the ADR-018/ADR-019 simulator lineage
(outgoing command transport, incoming event ingestion) with a third,
independent boundary (outgoing notification delivery) without changing
either.

## Context

`services/notification_service.py`'s `NotificationRow`/`current_notifications()`
is a **derived, in-memory projection**: built on every read from
`device_events` (via `event_semantics.py`'s mapping) and latest-reading
data, with no delivery, acknowledgement, or persistence concept of its own
— it is what the Notification Center table renders, nothing more.
Message forwarding (`message_forwarding_service.py`) persists a per-user
*preference* (OPS-FWD-1) but explicitly does not send anything (FWD-D9).
Neither module has ever sent an SMS or email, and neither should quietly
grow that responsibility as a side effect of adding one.

RTL-IF-4 needed a place for a *future* SMS/email adapter to plug into,
without which was already a decision the client had not made: which users
receive which alarms, on which channel, through which recipient rule.
Recipient policy is still one of `docs/context/PROJECT_LEDGER.md` §8's
open external dependencies — building it now would repeat the exact
mistake `SOURCE_AUTHORITY.md`'s "absence is not permission" rule exists to
prevent (the same rule that keeps `services/event_semantics.py` free of
invented high-temperature/vibration thresholds).

## Decision

**Delivery is a separate module, consumed by nobody yet, resolving nothing
itself:**

```
existing persisted event -> existing event semantics -> existing Notification Center   [UNCHANGED]

future delivery caller -> DeliveryRequest -> NotificationDelivery -> MockNotificationDelivery now
                                                                    -> SMS/Email adapters later
```

`services/notification_delivery.py` defines `DeliveryRequest`/
`DeliveryResult`/`NotificationDelivery` — a provider-neutral contract with
no Flask/session object, no database session, no provider credentials, no
Eskom/SMS vendor payload (mirroring `services/device_transport.py`'s
`DeviceTransport`, RTL-IF-2, field for field in spirit). `DeliveryRequest.
recipient_endpoint` is always supplied by the caller; this module contains
no code path that queries `users`, `user_device_assignments`, or any other
table to decide who receives what. `services/mock_notification_delivery.py`
implements the contract deterministically, exactly as
`SimulatorTransport`/`simulated_event_source.py` did for their own
directions — no network, no credentials, no sleep/thread.

**Nothing routes the Notification Center through this boundary.**
`notification_service.py` is unmodified, imports nothing from either new
module, and neither new module imports it back
(`tests/test_notification_delivery.py::TestNotificationCenterIsUnchangedAndUncoupled`
checks actual `import` statements via `ast`, not merely the absence of a
code diff). A notification row rendering in-app and a message being
delivered externally remain two different facts about two different
systems; conflating them was never this tranche's job.

## Why no recipient-resolution policy exists

Section 5 of the RTL-IF-4 task explicitly permitted "a small
recipient-resolution interface/seam" if useful, but also explicitly forbade
inventing production policy (all Administrators receive all alarms,
General Users receive alarms, one RTL has exactly one recipient, SMS-vs-
email precedence). No such interface was built. The one thing this
tranche's tests use is `repo.get_user_by_id().mobile_number`/
`.email_address` — columns `alembic/versions/003_users.py` already
documents as "nullable and NOT unique: uniqueness for either is a
plausible future rule but is not a confirmed business rule" — read
directly by the **test**, then passed to `DeliveryRequest` explicitly.
That is a data lookup a caller performs, not a policy this module
implements; `services/notification_delivery.py` itself contains no
reference to `users`, `user_device_assignments`, or `message_forwarding`
at all.

## Why no schema migration

`DeliveryResult`/adapter runs are not persisted anywhere. No
`notification_deliveries` table, no delivery history, no acknowledgement,
no escalation, no retry/retry-count/next-attempt-at. Client decisions for
recipient policy, delivery lifecycle, acknowledgement, escalation,
retention, and retry semantics are all still open (§8); persisting
delivery attempts against an undecided lifecycle would either invent that
lifecycle or produce rows nobody yet knows how to interpret. A future
tranche that has those decisions adds the table then.

## What this does not claim

Message forwarding is not "completed" by this tranche. Enabling forwarding
still sends nothing (FWD-D9, unchanged) — this ADR does not connect the
two, because no existing behavior defines what forwarding's recipient/
message contract would even be. No real SMS or email exists; `Mock
NotificationDelivery` is exactly what its name says. No production
recipient-routing policy exists. High-temperature/vibration events are
still structurally absent from `event_semantics.py`, unrelated to and
unaffected by this ADR.
