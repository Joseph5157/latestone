"""MockNotificationDelivery (RTL-IF-4) — a deterministic, in-process stand-in
for a real SMS/email provider.

**This is an internal test/demo fixture, not a real provider.** It never
makes a network call, requires no credentials, and does not model any real
SMS/email vendor's API, response format, or failure codes. A future SMS or
Email adapter implements `services/notification_delivery.NotificationDelivery`
on its own terms; it does not extend or wrap this class — same relationship
`services/simulator_transport.SimulatorTransport` (RTL-IF-2) has to a
future real `DeviceTransport`.

No network calls, sleeps, threads, or background loops. The configured
outcome (`succeed=True`/`False`, fixed at construction) is returned
synchronously for every `deliver()` call on a given instance.
"""
from __future__ import annotations

from services.notification_delivery import (
    DeliveryRequest,
    DeliveryResult,
    STATUS_DELIVERED,
    STATUS_FAILED,
    SUPPORTED_CHANNELS,
    UnsupportedChannelError,
)


class MockNotificationDelivery:
    """A `NotificationDelivery` whose outcome is fixed at construction.

    Every `deliver()` call on one instance returns the same configured
    outcome for any supported channel — it does not inspect the request
    body/recipient to decide. ``sent`` accumulates every request that
    reached an outcome (success or mock failure), in order, so a test can
    assert exactly what would have been delivered — the channel, the
    recipient endpoint, the body, the subject, the reference id.

    An unsupported channel raises before the request is recorded in
    ``sent`` at all: refusing loudly, never silently "delivering" a
    channel nobody defined an adapter for.
    """

    def __init__(self, *, succeed: bool = True) -> None:
        self._succeed = succeed
        self.sent: list[DeliveryRequest] = []

    def deliver(self, request: DeliveryRequest) -> DeliveryResult:
        if request.channel not in SUPPORTED_CHANNELS:
            raise UnsupportedChannelError(
                f"{request.channel!r} is not a supported delivery channel; "
                f"choose one of {sorted(SUPPORTED_CHANNELS)!r}."
            )

        self.sent.append(request)

        if self._succeed:
            return DeliveryResult(
                status=STATUS_DELIVERED,
                detail=f"Mock delivery accepted for channel {request.channel}.",
            )
        return DeliveryResult(
            status=STATUS_FAILED,
            detail="Mock delivery configured to fail (test fixture).",
        )


__all__ = ["MockNotificationDelivery"]
