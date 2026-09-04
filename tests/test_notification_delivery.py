"""RTL-IF-4 notification delivery abstraction tests.

Proves services/notification_delivery.py + services/mock_notification_delivery.py
are a provider-neutral boundary that never touches the existing in-app
Notification Center (services/notification_service.py) and never resolves
its own recipients. Pure/structural tests need no database; a handful of
db-marked tests only use the database to obtain a real, already-existing
user contact endpoint to pass in explicitly (RTL-IF-4 section 5's "tests
may supply an explicit recipient endpoint directly").
"""
from __future__ import annotations

import socket

import pytest
from sqlalchemy import text

from db.engine import session_scope
from repositories import plant_monitoring_repository as repo
from services.mock_notification_delivery import MockNotificationDelivery
from services.notification_delivery import (
    CHANNEL_EMAIL,
    CHANNEL_SMS,
    STATUS_DELIVERED,
    STATUS_FAILED,
    DeliveryRequest,
    DeliveryResult,
    NotificationDelivery,
    UnsupportedChannelError,
)


class TestDeliveryRequestIsProviderNeutral:
    """B. The same request shape serves both channels — no per-channel
    subclass, no per-provider field."""

    def test_sms_and_email_requests_share_the_same_dataclass_shape(self):
        sms = DeliveryRequest(
            channel=CHANNEL_SMS, recipient_endpoint="+27821234567",
            body="Battery Low on device x",
        )
        email = DeliveryRequest(
            channel=CHANNEL_EMAIL, recipient_endpoint="ops@example.test",
            body="Battery Low on device x", subject="Alert",
        )
        assert type(sms) is type(email) is DeliveryRequest
        assert sms.channel != email.channel

    def test_request_carries_no_flask_session_or_db_object(self):
        """G. Only plain, JSON-shaped fields exist on the contract."""
        import dataclasses

        fields = {f.name for f in dataclasses.fields(DeliveryRequest)}
        assert fields == {
            "channel", "recipient_endpoint", "body", "reference_id",
            "subject",
        }
        for name in fields:
            assert "session" not in name.lower()
            assert "flask" not in name.lower()
            assert "user_id" not in name.lower()  # no trusted identity carried

    def test_delivery_result_carries_no_provider_response_id(self):
        """No retry_count, next_attempt_at, or provider response id exists
        on the normalized outcome (RTL-IF-4 section 9)."""
        import dataclasses

        fields = {f.name for f in dataclasses.fields(DeliveryResult)}
        assert fields == {"status", "detail"}


class TestMockDeliveryIsDeterministic:
    def test_c_mock_sms_success_is_deterministic(self):
        adapter = MockNotificationDelivery(succeed=True)
        request = DeliveryRequest(
            channel=CHANNEL_SMS, recipient_endpoint="+27821234567",
            body="Battery Low",
        )

        result = adapter.deliver(request)

        assert result.status == STATUS_DELIVERED
        assert adapter.sent == [request]

    def test_d_mock_email_success_is_deterministic(self):
        adapter = MockNotificationDelivery(succeed=True)
        request = DeliveryRequest(
            channel=CHANNEL_EMAIL, recipient_endpoint="ops@example.test",
            body="Battery Low", subject="Alert",
        )

        result = adapter.deliver(request)

        assert result.status == STATUS_DELIVERED
        assert adapter.sent == [request]

    def test_e_mock_failure_is_deterministic(self):
        adapter = MockNotificationDelivery(succeed=False)
        request = DeliveryRequest(
            channel=CHANNEL_SMS, recipient_endpoint="+27821234567",
            body="Battery Low",
        )

        result = adapter.deliver(request)

        assert result.status == STATUS_FAILED
        # A configured-failure request is still recorded as "sent" —
        # sent means "reached the adapter", not "reached the recipient".
        assert adapter.sent == [request]

    def test_repeated_delivery_accumulates_every_request_in_order(self):
        adapter = MockNotificationDelivery(succeed=True)
        first = DeliveryRequest(channel=CHANNEL_SMS, recipient_endpoint="a", body="1")
        second = DeliveryRequest(channel=CHANNEL_EMAIL, recipient_endpoint="b", body="2")

        adapter.deliver(first)
        adapter.deliver(second)

        assert adapter.sent == [first, second]

    def test_i_unsupported_channel_fails_safely(self):
        """I. Refused before being recorded as sent — never silently
        'delivered' through an undefined channel."""
        adapter = MockNotificationDelivery(succeed=True)
        request = DeliveryRequest(
            channel="WHATSAPP", recipient_endpoint="+27821234567", body="x",
        )

        with pytest.raises(UnsupportedChannelError):
            adapter.deliver(request)

        assert adapter.sent == []

    def test_h_no_network_call_is_made(self, monkeypatch):
        """H."""

        def _explode(*args, **kwargs):
            raise AssertionError("MockNotificationDelivery attempted a network call")

        monkeypatch.setattr(socket, "socket", _explode)

        adapter = MockNotificationDelivery(succeed=True)
        result = adapter.deliver(
            DeliveryRequest(
                channel=CHANNEL_SMS, recipient_endpoint="+27821234567", body="x",
            )
        )
        assert result.status == STATUS_DELIVERED

    def test_mock_conforms_to_the_notification_delivery_protocol(self):
        adapter: NotificationDelivery = MockNotificationDelivery()
        assert hasattr(adapter, "deliver")


@pytest.mark.db
@pytest.mark.usefixtures("isolated_schema")
class TestExplicitServerSideRecipientEndpoint:
    """F. The adapter receives a recipient endpoint the caller resolved and
    supplied explicitly — this module resolves nothing itself."""

    def setup_method(self):
        with session_scope() as session:
            for table in ("audit_log", "users"):
                session.execute(text(f"DELETE FROM {repo._SCHEMA}.{table}"))

    def test_caller_supplied_endpoint_reaches_the_adapter_unmodified(self):
        user = repo.create_or_update_user(
            username="notif-recipient", full_name="Notif Recipient",
            role="administrator", status="active",
            email_address="recipient@example.test",
            mobile_number="+27821112222",
        )

        # The caller (a test here; a future recipient-resolution slice in
        # production) reads the endpoint and passes it in explicitly — this
        # module never queries `users` itself.
        reloaded = repo.get_user_by_id(user.user_id)
        request = DeliveryRequest(
            channel=CHANNEL_SMS,
            recipient_endpoint=reloaded.mobile_number,
            body="Battery Low on assigned device",
            reference_id="event:12345",
        )

        adapter = MockNotificationDelivery(succeed=True)
        result = adapter.deliver(request)

        assert result.status == STATUS_DELIVERED
        assert adapter.sent[0].recipient_endpoint == "+27821112222"


class TestNotificationCenterIsUnchangedAndUncoupled:
    """A. The existing in-app Notification Center is not routed through
    delivery — proven structurally, not merely by absence of a diff."""

    def test_notification_service_does_not_import_delivery_modules(self):
        import pathlib

        source = pathlib.Path(
            "services/notification_service.py"
        ).read_text(encoding="utf-8")
        assert "notification_delivery" not in source
        assert "mock_notification_delivery" not in source

    def test_event_semantics_does_not_import_delivery_modules(self):
        """J, structurally: event classification stays delivery-unaware."""
        import pathlib

        source = pathlib.Path("services/event_semantics.py").read_text(
            encoding="utf-8"
        )
        assert "notification_delivery" not in source
        assert "mock_notification_delivery" not in source

    def test_delivery_modules_do_not_import_notification_service(self):
        """The dependency does not run the other way either — delivery is
        a sibling boundary, not a consumer that reaches back into the
        in-app projection. Checks actual import statements, not prose —
        both modules' docstrings legitimately reference
        notification_service.py by name to explain the boundary."""
        import ast
        import pathlib

        for path in (
            "services/notification_delivery.py",
            "services/mock_notification_delivery.py",
        ):
            tree = ast.parse(pathlib.Path(path).read_text(encoding="utf-8"))
            imported_modules = {
                alias.name
                for node in ast.walk(tree)
                if isinstance(node, ast.Import)
                for alias in node.names
            } | {
                node.module
                for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom) and node.module
            }
            assert not any(
                "notification_service" in m for m in imported_modules
            ), (path, imported_modules)

    def test_no_callback_or_page_imports_delivery_modules(self):
        """No browser-facing wiring exists yet — same structural proof
        RTL-IF-2/RTL-IF-3 used for their own simulator modules."""
        import pathlib

        project_root = pathlib.Path(__file__).resolve().parent.parent
        for package in ("callbacks", "pages", "components"):
            for path in (project_root / package).rglob("*.py"):
                text_content = path.read_text(encoding="utf-8")
                assert "notification_delivery" not in text_content, path
                assert "mock_notification_delivery" not in text_content, path
