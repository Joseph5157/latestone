"""The mutation callbacks go through the guard (ROLE-3 Task 11).

WHY THIS FILE MATTERS MORE THAN IT LOOKS. Today only administrators can reach
the Manage and Assign drawers, and administrators pass every check, so none of
these refusals can currently be triggered through the UI. That is precisely
why they need tests: the wiring is invisible in manual testing and would rot
silently until the day a technician-facing surface exists — which ROLE-3
invariant 10 forbids adding here.

These tests stay role-pure: administrator and general both resolve without an
assignment read, so no database is involved.
"""
from __future__ import annotations

import pytest

from callbacks import device_assign, device_manage, device_register
from services import hierarchy_service

ADMINISTRATOR_SESSION = {
    "authenticated": True,
    "user_id": 1,
    "username": "admin",
    "full_name": "Admin",
    "role": "administrator",
}

GENERAL_SESSION = {
    "authenticated": True,
    "user_id": 7,
    "username": "general",
    "full_name": "General",
    "role": "general",
}

TECHNICIAN_SESSION = {
    "authenticated": True,
    "user_id": 42,
    "username": "tech",
    "full_name": "Tech",
    "role": "technician",
}

#: The pre-ROLE-1 payload: authenticated, but carrying no usable identity.
STALE_SESSION = {"authenticated": True}

DEVICE_ID = "cb-d1"


class _CapturingApp:
    """Collects callbacks by function name instead of registering them."""

    def __init__(self):
        self.functions = {}

    def callback(self, *args, **kwargs):
        def decorator(fn):
            self.functions[fn.__name__] = fn
            return fn

        return decorator


def _handlers(module):
    app = _CapturingApp()
    module.register(app)
    return app.functions


def _is_refusal(result) -> bool:
    """A refusal renders the shared notice, never the success panel."""
    from components.status_panels import ACTION_REFUSED_CLASS

    return getattr(result, "className", "") == ACTION_REFUSED_CLASS


def _rendered_text(result) -> str:
    return str(result)


# --------------------------------------------------------------------------
# Program RTL (OPS-PROG-1: persisted pending request behind the guard)
# --------------------------------------------------------------------------


class _ProgrammingSpy:
    """Stands in for the programming service and records whether it ran."""

    def __init__(self):
        import types

        self.calls = []
        #: A persisted-looking row: the callback renders its request_id.
        self.result = types.SimpleNamespace(request_id=101)

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        return self.result


class TestProgramRtl:
    def _call(self, session):
        handler = _handlers(device_manage)["confirm_program_rtl"]
        return handler(1, DEVICE_ID, "uid-1", "t1", "0700000000", session)

    def test_administrator_reaches_the_service_with_session_identity(
        self, monkeypatch
    ):
        spy = _ProgrammingSpy()
        monkeypatch.setattr(
            device_manage.rtl_programming_service, "record_request", spy
        )

        self._call(ADMINISTRATOR_SESSION)

        assert spy.calls == [
            {
                "device_id": DEVICE_ID,
                "master_msisdn": "0700000000",
                "actor_user_id": ADMINISTRATOR_SESSION["user_id"],
            }
        ], "the request must be recorded against the acting session's identity"

    def test_general_is_refused_and_never_reaches_the_service(self, monkeypatch):
        spy = _ProgrammingSpy()
        monkeypatch.setattr(
            device_manage.rtl_programming_service, "record_request", spy
        )

        assert _is_refusal(self._call(GENERAL_SESSION))
        assert spy.calls == []

    @pytest.mark.parametrize("session", [STALE_SESSION, None], ids=["stale", "no-session"])
    def test_broken_sessions_are_refused_before_the_write(self, monkeypatch, session):
        spy = _ProgrammingSpy()
        monkeypatch.setattr(
            device_manage.rtl_programming_service, "record_request", spy
        )

        assert _is_refusal(self._call(session))
        assert spy.calls == []

    def test_the_refusal_names_no_policy_detail(self):
        """The panel states the outcome. It does not echo the role, the
        action or the device id back at the operator."""
        handler = _handlers(device_manage)["confirm_program_rtl"]
        text = _rendered_text(handler(1, DEVICE_ID, "uid-1", "t1", "0700000000", GENERAL_SESSION))
        assert "general" not in text.lower()
        assert DEVICE_ID not in text

    def test_service_failure_shows_friendly_panel_not_a_crash(self, monkeypatch):
        def explode(**kwargs):
            raise device_manage.rtl_programming_service.ProgrammingError("boom")

        monkeypatch.setattr(
            device_manage.rtl_programming_service, "record_request", explode
        )

        result = self._call(ADMINISTRATOR_SESSION)

        assert not _is_refusal(result)
        rendered = _rendered_text(result).lower()
        assert "not recorded" in rendered

    def test_confirmation_states_persistence_without_claiming_transport(
        self, monkeypatch
    ):
        """PROG-D7 honesty boundary: a recorded request must never be worded
        as though a command was queued/sent or the RTL was programmed."""
        spy = _ProgrammingSpy()
        monkeypatch.setattr(
            device_manage.rtl_programming_service, "record_request", spy
        )

        rendered = _rendered_text(self._call(ADMINISTRATOR_SESSION)).lower()

        assert "programming request recorded" in rendered
        assert "no command has yet been sent to the rtl master" in rendered
        assert "not confirmed programmed" in rendered
        for banned in ("command queued", "command sent", "prototype"):
            assert banned not in rendered


# --------------------------------------------------------------------------
# Message forwarding (OPS-FWD-1: persisted per-user behind the guard)
# --------------------------------------------------------------------------


class _ForwardingSpy:
    """Stands in for the forwarding service and records whether it ran."""

    def __init__(self):
        self.calls = []
        self.result = object()

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        return self.result


class TestMessageForwarding:
    def _call(self, session, device_id=DEVICE_ID, state="enabled"):
        handler = _handlers(device_manage)["confirm_message_forwarding"]
        return handler(1, device_id, state, session)

    def test_authorized_caller_reaches_the_service_with_session_identity(
        self, monkeypatch
    ):
        spy = _ForwardingSpy()
        monkeypatch.setattr(device_manage.message_forwarding_service, "set_forwarding", spy)

        self._call(ADMINISTRATOR_SESSION)

        assert spy.calls == [
            {"enabled": True, "actor_user_id": ADMINISTRATOR_SESSION["user_id"]}
        ], "the mutation must target the acting USER, never the device"

    def test_general_is_refused_and_never_reaches_the_service(self, monkeypatch):
        spy = _ForwardingSpy()
        monkeypatch.setattr(device_manage.message_forwarding_service, "set_forwarding", spy)

        assert _is_refusal(self._call(GENERAL_SESSION))
        assert spy.calls == []

    @pytest.mark.parametrize("session", [STALE_SESSION, None], ids=["stale", "no-session"])
    def test_broken_sessions_are_refused_before_the_write(self, monkeypatch, session):
        spy = _ForwardingSpy()
        monkeypatch.setattr(device_manage.message_forwarding_service, "set_forwarding", spy)

        assert _is_refusal(self._call(session))
        assert spy.calls == []

    def test_disable_reaches_the_service_as_false(self, monkeypatch):
        spy = _ForwardingSpy()
        monkeypatch.setattr(device_manage.message_forwarding_service, "set_forwarding", spy)

        self._call(ADMINISTRATOR_SESSION, state="disabled")

        assert spy.calls == [{"enabled": False, "actor_user_id": ADMINISTRATOR_SESSION["user_id"]}]

    def test_service_failure_shows_friendly_panel_not_a_crash(self, monkeypatch):
        def explode(**kwargs):
            raise device_manage.message_forwarding_service.ForwardingError("boom")

        monkeypatch.setattr(device_manage.message_forwarding_service, "set_forwarding", explode)

        result = self._call(ADMINISTRATOR_SESSION)

        assert not _is_refusal(result)
        assert "not saved" in _rendered_text(result).lower()

    def test_confirmation_does_not_claim_delivery_is_real(self, monkeypatch):
        """FWD-D8 honesty boundary: persisting a preference must never be
        worded as though messages are now actually being forwarded."""
        spy = _ForwardingSpy()
        monkeypatch.setattr(device_manage.message_forwarding_service, "set_forwarding", spy)

        rendered = _rendered_text(self._call(ADMINISTRATOR_SESSION)).lower()

        assert "delivery integration is not yet connected" in rendered
        assert "will now be forwarded" not in rendered


# --------------------------------------------------------------------------
# Deactivate
# --------------------------------------------------------------------------


class TestDeactivateRtl:
    def _call(self, session):
        handler = _handlers(device_manage)["confirm_deactivate_rtl"]
        return handler(1, DEVICE_ID, session)

    def test_administrator_succeeds(self):
        assert not _is_refusal(self._call(ADMINISTRATOR_SESSION))

    def test_general_is_refused(self):
        assert _is_refusal(self._call(GENERAL_SESSION))

    def test_no_session_is_refused(self):
        assert _is_refusal(self._call(None))


# --------------------------------------------------------------------------
# Assignment
# --------------------------------------------------------------------------


class TestConfirmAssignment:
    def _call(self, session, technician=None, transformer_id="t9"):
        handler = _handlers(device_assign)["confirm_assignment"]
        return handler(1, DEVICE_ID, "p1", transformer_id, technician, session)

    def test_general_is_refused_and_assigns_nothing(self, monkeypatch):
        calls = []
        monkeypatch.setattr(
            device_assign.prototype_assignments,
            "assign_technician",
            lambda *a, **k: calls.append(a),
        )
        device_assign.clear_mock_assignments()

        self._call(GENERAL_SESSION, technician="someone")

        assert calls == []
        assert device_assign.get_mock_assignment(DEVICE_ID) is None

    def test_technician_may_not_manage_assignment(self, monkeypatch):
        """Assignment is administrator-only even for a technician who holds
        the device: it is what grants their own authority."""
        calls = []
        monkeypatch.setattr(
            device_assign.prototype_assignments,
            "assign_technician",
            lambda *a, **k: calls.append(a),
        )
        # A technician is the one role whose authorization needs an
        # assignment read. Stub it so this file stays free of the database;
        # the real lookup is exercised in tests/test_action_guard_db.py.
        import services.action_guard as guard
        from services.device_scope import DeviceScope

        monkeypatch.setattr(guard, "scope_for", lambda user: DeviceScope(frozenset({DEVICE_ID})))
        device_assign.clear_mock_assignments()

        self._call(TECHNICIAN_SESSION, technician="someone")

        assert calls == []
        assert device_assign.get_mock_assignment(DEVICE_ID) is None

    def test_administrator_still_assigns(self, monkeypatch):
        calls = []
        monkeypatch.setattr(
            device_assign.prototype_assignments,
            "assign_technician",
            lambda *a, **k: calls.append(a),
        )
        device_assign.clear_mock_assignments()

        self._call(ADMINISTRATOR_SESSION, technician="someone")

        assert calls, "the administrator's assignment did not go through"
        assert device_assign.get_mock_assignment(DEVICE_ID) == "t9"

    def test_no_session_assigns_nothing(self, monkeypatch):
        calls = []
        monkeypatch.setattr(
            device_assign.prototype_assignments,
            "assign_technician",
            lambda *a, **k: calls.append(a),
        )
        device_assign.clear_mock_assignments()

        self._call(None, technician="someone")

        assert calls == []
        assert device_assign.get_mock_assignment(DEVICE_ID) is None


# --------------------------------------------------------------------------
# The rule is not reimplemented here
# --------------------------------------------------------------------------


class TestCallbacksDoNotContainTheRule:
    @pytest.mark.parametrize(
        "module", [device_manage, device_assign], ids=["device_manage", "device_assign"]
    )
    def test_no_role_string_comparison_in_the_callback_module(self, module):
        """A role literal in a callback means the matrix was partly copied
        out of the policy table — the start of two answers to one question."""
        import pathlib
        import re

        source = pathlib.Path(module.__file__).read_text(encoding="utf-8")
        offenders = [
            line.strip()
            for line in source.splitlines()
            if re.search(r'==\s*["\'](administrator|technician|general)["\']', line)
            or re.search(r'["\'](administrator|technician|general)["\']\s*==', line)
        ]
        assert offenders == [], offenders


# --------------------------------------------------------------------------
# Device registration — the device-less guard
# --------------------------------------------------------------------------


class _RegisterSpy:
    """Stands in for the registration service and records whether it ran.

    The assertion here IS "was the mutation reached", so the boundary itself
    is what has to be observed. A denied role must not get this far.
    """

    def __init__(self):
        self.calls = []

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return object()


def _silence_label_lookups(monkeypatch):
    """Stop the review-label reads from needing a database.

    Only used for the permitted case. A refused caller must not reach these
    at all, which is what leaving them un-patched proves.
    """
    monkeypatch.setattr(hierarchy_service, "list_plants", lambda **kw: [])
    monkeypatch.setattr(hierarchy_service, "list_transformers", lambda *a, **kw: [])


class TestDeviceRegistration:
    """The submit callback authorizes before it writes.

    ROUTE_POLICY already gates the page administrator-only, but the callback
    answers whoever invokes it and the session travels in a browser-side
    store. These tests call the handler directly — the path a caller
    bypassing the router takes — which is the only way this refusal is
    observable at all.
    """

    def _call(self, session):
        handler = _handlers(device_register)["_submit_registration"]
        return handler(1, "dv1", "plant-01", "plant-01-t1", "active", session)

    def test_administrator_reaches_the_registration_service(self, monkeypatch):
        spy = _RegisterSpy()
        _silence_label_lookups(monkeypatch)
        monkeypatch.setattr(device_register, "register_device", spy)

        self._call(ADMINISTRATOR_SESSION)

        assert spy.calls, "an administrator must reach register_device"

    @pytest.mark.parametrize(
        "session",
        [TECHNICIAN_SESSION, GENERAL_SESSION, STALE_SESSION, None],
        ids=["technician", "general", "stale", "no-session"],
    )
    def test_denied_callers_never_reach_the_database(self, monkeypatch, session):
        """No write, and no read either — the guard runs before the label
        lookups, so a refused caller touches the database not at all.

        The label lookups are deliberately NOT patched here: if the guard were
        placed after them this test would fail in the no-database suite.
        """
        spy = _RegisterSpy()
        monkeypatch.setattr(device_register, "register_device", spy)

        result = self._call(session)

        assert spy.calls == [], "a refused caller must not reach register_device"
        assert result[4] == {"display": "block"}, "the error slot must be shown"
        assert _is_refusal(result[5]), "the shared refusal notice must be rendered"

    def test_refusal_does_not_reveal_the_policy(self, monkeypatch):
        """The notice names no role, action or device."""
        monkeypatch.setattr(device_register, "register_device", _RegisterSpy())

        result = self._call(TECHNICIAN_SESSION)

        rendered = _rendered_text(result[5]).lower()
        for leak in ("technician", "register_device", "administrator"):
            assert leak not in rendered
