"""Pure tests for the protocol-neutral dispatch safety boundary."""
from __future__ import annotations

import pytest

from config.commands import DEFAULT_DISPATCH_POLICY, DispatchPolicy
from services import rtl_command_dispatch_service as dispatch
from services.device_transport import is_transport_configured


class TestDispatchPolicy:
    def test_safe_default_is_timeout_with_retries_disabled(self):
        assert DEFAULT_DISPATCH_POLICY.timeout_seconds == 30.0
        assert DEFAULT_DISPATCH_POLICY.max_retries == 0
        assert DEFAULT_DISPATCH_POLICY.retries_enabled is False

    def test_policy_can_be_configured_without_protocol_details(self):
        policy = DispatchPolicy(timeout_seconds=12.5, max_retries=0, retry_delay_seconds=2.0)
        assert policy.timeout_seconds == 12.5
        assert policy.retry_delay_seconds == 2.0

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"timeout_seconds": 0},
            {"timeout_seconds": -1},
            {"max_retries": -1},
            {"retry_delay_seconds": -1},
        ],
    )
    def test_invalid_values_fail_closed(self, kwargs):
        with pytest.raises(ValueError):
            DispatchPolicy(**kwargs)

    def test_retries_require_explicit_future_client_policy(self):
        policy = DispatchPolicy(max_retries=1)
        class Transport:
            def send(self, command, request):
                raise AssertionError("should not be reached")

        with pytest.raises(dispatch.CommandNotDispatchableError, match="client-approved"):
            dispatch.dispatch_command(1, Transport(), policy=policy)


class TestMissingTransport:
    def test_none_transport_is_refused_before_command_lookup(self, monkeypatch):
        calls = []
        monkeypatch.setattr(
            dispatch.rtl_command_service,
            "get_command",
            lambda command_id: calls.append(command_id),
        )
        with pytest.raises(
            dispatch.ProductionTransportNotConfiguredError,
            match="remains queued",
        ):
            dispatch.dispatch_command(42)
        assert calls == []

    def test_invalid_transport_object_is_not_treated_as_delivery(self):
        assert is_transport_configured(None) is False
        assert is_transport_configured(object()) is False

    def test_transport_with_send_is_configured(self):
        class FutureTransport:
            def send(self, command, request):
                raise AssertionError("not called by this predicate")

        assert is_transport_configured(FutureTransport()) is True
