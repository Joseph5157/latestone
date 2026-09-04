"""Provider-neutral notification delivery contract (RTL-IF-4).

    existing persisted event
            v
    existing event semantics
            v
    existing Notification Center        [UNCHANGED — services/notification_service.py]

    future delivery caller
            v
    DeliveryRequest                     (this module)
            v
    NotificationDelivery interface      (this module)
            v
    MockNotificationDelivery now        (services/mock_notification_delivery.py)
    SMS / Email adapters later          (not this tranche)

**This module does not touch the in-app Notification Center.**
`services/notification_service.py`'s `NotificationRow`/`current_notifications()`
are the existing, unmodified projection/read model — an in-memory,
derived-on-read view built from `device_events`/reading data, not a
persisted delivery record. Nothing here reads from or writes to it, and no
caller in this tranche routes Notification Center rows through delivery.

`DeliveryRequest.recipient_endpoint` is always supplied by the caller —
never resolved inside this module or any adapter. RTL-IF-4 deliberately
implements no recipient-resolution policy: which users receive which
alarms by which channel is still a client-unknown decision (message
forwarding, delivery channel & recipient rules — `docs/context/
PROJECT_LEDGER.md` §8). Inventing that policy here would be exactly the
mistake `AGENTS.md`'s "absence is not permission" principle (via
`SOURCE_AUTHORITY.md`) exists to prevent. A caller (a test, or a future
recipient-resolution slice this tranche does not build) decides the
endpoint and passes it in.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

#: Internal channel vocabulary — only what RTL-IF-4 genuinely needs. No
#: WhatsApp, Teams, push, or any other channel invented ahead of a client
#: requirement for it.
CHANNEL_SMS = "SMS"
CHANNEL_EMAIL = "EMAIL"

SUPPORTED_CHANNELS = frozenset({CHANNEL_SMS, CHANNEL_EMAIL})

#: Normalized internal delivery outcomes. No retry scheduling, no
#: provider response ids, no provider-specific failure codes — those
#: belong to a future tranche that has a real provider to describe.
STATUS_DELIVERED = "DELIVERED"
STATUS_FAILED = "FAILED"


class UnsupportedChannelError(Exception):
    """A DeliveryRequest named a channel outside SUPPORTED_CHANNELS.

    Raised before any delivery attempt — an adapter refuses loudly rather
    than silently accepting (or worse, "delivering") a channel nobody has
    defined an adapter for.
    """


@dataclass(frozen=True)
class DeliveryRequest:
    """One provider-neutral request to deliver a message.

    No Flask/session object, no database session, no provider credentials,
    no Eskom/SMS vendor payload, no MQTT concept — a plain, JSON-shaped
    value. ``recipient_endpoint`` is the caller's responsibility (see
    module docstring); ``reference_id`` optionally ties the request back to
    whatever already-decided application fact it concerns (e.g. a
    ``device_events.event_id``) for the caller's own logging or test
    assertions — no adapter interprets or requires it.
    """

    channel: str
    recipient_endpoint: str
    body: str
    reference_id: str | None = None
    subject: str | None = None


@dataclass(frozen=True)
class DeliveryResult:
    """An adapter's report of what happened to one ``DeliveryRequest``.

    ``status`` is ``STATUS_DELIVERED``/``STATUS_FAILED`` — never a raw
    provider response code. ``detail`` is a normalized, safe-to-log
    internal message, never a credential or raw provider payload.
    """

    status: str
    detail: str | None = None


class NotificationDelivery(Protocol):
    """The smallest send contract a delivery adapter must implement.

    Receives a ``DeliveryRequest`` only. No role/session authorization
    happens here or in any adapter — authorization is the caller's job,
    entirely upstream, exactly like `services/device_transport.py`'s
    `DeviceTransport` (RTL-IF-2) has no authorization role either.
    """

    def deliver(self, request: DeliveryRequest) -> DeliveryResult:
        ...


__all__ = [
    "CHANNEL_EMAIL",
    "CHANNEL_SMS",
    "STATUS_DELIVERED",
    "STATUS_FAILED",
    "SUPPORTED_CHANNELS",
    "DeliveryRequest",
    "DeliveryResult",
    "NotificationDelivery",
    "UnsupportedChannelError",
]
