"""ADR-033: the User Administration lifecycle callbacks (pure, no database).

The account service is replaced by a spy; identity is a real trusted session
backed by a patched `get_user_by_id`, exactly like `test_user_admin_callbacks`.
What is proven here is the callback boundary: only an Administrator reaches the
service, the one-time link is rendered once and discarded on close, and nothing
credential-shaped reaches the browser other than that link.
"""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from callbacks import user_admin
from components.status_panels import ACTION_REFUSED_CLASS
from services import account_service
from tests.auth_test_support import no_trusted_session, trusted_session

ADMIN_ID = 1


class _Capturing:
    def __init__(self):
        self.functions = {}

    def callback(self, *a, **k):
        def deco(fn):
            self.functions[fn.__name__] = fn
            return fn

        return deco


@pytest.fixture
def handlers():
    app = _Capturing()
    user_admin.register(app)
    return app.functions


@pytest.fixture
def service(monkeypatch):
    calls = []
    fresh = {"status": "pending_activation"}

    def record(name):
        def _f(**kwargs):
            calls.append((name, kwargs))
            return SimpleNamespace(status=fresh["status"])

        return _f

    link = account_service.IssuedLink(
        url="http://localhost:8050/set-password?token=RAWTOKEN", purpose="setup",
        expires_at=datetime(2030, 1, 1, tzinfo=timezone.utc), username="tech.one",
    )
    monkeypatch.setattr(account_service, "issue_link", lambda **k: calls.append(("issue", k)) or link)
    monkeypatch.setattr(account_service, "disable_account", record("disable"))
    monkeypatch.setattr(account_service, "enable_account", record("enable"))
    monkeypatch.setattr(
        account_service, "list_accounts",
        lambda actor_user_id: [SimpleNamespace(user_id=42, username="tech.one")],
    )
    monkeypatch.setattr(
        user_admin, "get_user",
        lambda name: {"username": name, "status": fresh["status"], "role": "technician"},
    )
    return calls, fresh


def _click(handlers, button):
    """Invoke `account_lifecycle` as if `button` was the trigger."""
    import dash

    ctx = SimpleNamespace(triggered=[{"prop_id": f"{button}.n_clicks"}])
    original = dash.callback_context
    dash.callback_context = ctx
    try:
        clicks = [1 if b == button else 0 for b in (ISSUE, DISABLE, ENABLE)]
        return handlers["account_lifecycle"](*clicks, "tech.one", 3)
    finally:
        dash.callback_context = original


ISSUE = "user-form-issue-btn"
DISABLE = "user-form-disable-btn"
ENABLE = "user-form-enable-btn"


class TestAdministratorOnly:
    @pytest.mark.parametrize("role", ["technician", "general"])
    def test_a_non_administrator_reaches_no_service_call(self, handlers, service, monkeypatch, role):
        calls, _ = service
        with trusted_session(monkeypatch, user_id=50, role=role):
            for button in (ISSUE, DISABLE, ENABLE):
                result = _click(handlers, button)
                assert getattr(result[0], "className", "") == ACTION_REFUSED_CLASS
        assert calls == []

    def test_no_session_fails_closed(self, handlers, service):
        calls, _ = service
        with no_trusted_session():
            result = _click(handlers, ISSUE)
        assert getattr(result[0], "className", "") == ACTION_REFUSED_CLASS and calls == []

    @pytest.mark.parametrize("role", ["technician", "general"])
    def test_a_non_administrator_cannot_load_the_roster(self, handlers, monkeypatch, role):
        with trusted_session(monkeypatch, user_id=50, role=role):
            rows, columns, error, summary = handlers["populate_user_admin"](
                {"route": "admin_users"}, "", "all", "all", 0
            )
        assert rows == [] and columns == [] and error is not None and summary == ""


class TestOneTimeLink:
    def test_issuing_renders_the_link_once_with_a_handover_note(self, handlers, service, monkeypatch):
        calls, _ = service
        with trusted_session(monkeypatch, user_id=ADMIN_ID, role="administrator"):
            panel, status, issue_label, _dis, _en, refresh = _click(handlers, ISSUE)
        assert calls == [("issue", {"actor_user_id": ADMIN_ID, "user_id": 42})]
        text = str(panel)
        assert "RAWTOKEN" in text and "no email or SMS was sent" in text and "shown once" in text
        assert refresh == 4

    def test_closing_the_drawer_discards_the_link(self, handlers):
        style, result, active_cell = handlers["close_user_drawer"](1, 0, 0)
        assert style == {"display": "none"} and result == ""
        assert active_cell is None, "the row must be re-openable"

    def test_opening_the_drawer_clears_any_previous_link(self, handlers, monkeypatch):
        import dash

        original = dash.callback_context
        with trusted_session(monkeypatch, user_id=ADMIN_ID, role="administrator"):
            dash.callback_context = SimpleNamespace(
                triggered=[{"prop_id": "user-admin-add-btn.n_clicks"}]
            )
            try:
                outputs = handlers["open_user_drawer"](1, None, [])
            finally:
                dash.callback_context = original
        # Result slot is the 15th output of open_user_drawer and is reset to "".
        assert outputs[14] == "" and outputs[2] == "Add User"

    def test_the_service_error_is_shown_not_swallowed(self, handlers, service, monkeypatch):
        def refuse(**k):
            raise account_service.AccountError("Link this Technician to a client person first.")

        monkeypatch.setattr(account_service, "issue_link", refuse)
        with trusted_session(monkeypatch, user_id=ADMIN_ID, role="administrator"):
            result = _click(handlers, ISSUE)
        assert "Link this Technician" in str(result[0])


class TestDisableEnable:
    def test_disable_and_enable_call_the_service_and_refresh_the_table(self, handlers, service, monkeypatch):
        calls, fresh = service
        with trusted_session(monkeypatch, user_id=ADMIN_ID, role="administrator"):
            fresh["status"] = "disabled"
            panel, status, _issue, dis_style, en_style, refresh = _click(handlers, DISABLE)
            assert status == "Disabled" and dis_style == {"display": "none"}
            assert en_style == {"display": "inline-block"} and refresh == 4
            fresh["status"] = "pending_activation"
            _click(handlers, ENABLE)
        assert [c[0] for c in calls] == ["disable", "enable"]


class TestRowsAndForm:
    def test_rows_show_status_label_and_client_person_and_no_credential_fields(self):
        rows = user_admin._build_user_rows([
            {"username": "a", "identifier": "", "role": "technician", "status": "pending_activation",
             "full_name": "A Person", "client_person_id": 4, "has_password": False},
            {"username": "b", "identifier": "b@x", "role": "general", "status": "disabled",
             "full_name": "B", "client_person_id": None, "has_password": True},
        ])
        assert [r["status"] for r in rows] == ["Pending activation", "Disabled"]
        assert [r["client_person"] for r in rows] == ["Person 4", "—"]
        blob = str(rows).lower()
        assert "hash" not in blob and "password" not in blob and "token" not in blob

    @pytest.mark.parametrize("raw,expected", [
        (None, (None, None)), ("", (None, None)), ("  ", (None, None)), (5, (5, None)), ("6", (6, None)),
    ])
    def test_client_person_id_parsing(self, raw, expected):
        assert user_admin._parse_person_id(raw) == expected

    @pytest.mark.parametrize("raw", ["abc", 0, -3])
    def test_bad_client_person_ids_are_refused(self, raw):
        value, error = user_admin._parse_person_id(raw)
        assert value is None and error
