"""VIB-CONFIG-1 callback authorization — the vibration contract panel must
authorize before any query or write, exactly like
callbacks/temperature_threshold.py's threshold panel (THRESH-CONFIG-1),
which this gate's capability (MANAGE_VIBRATION_CONTRACT) mirrors.

No database: the service functions are replaced with spies so these tests
prove the CALLBACK's authorization boundary, not the service/repository
layer (covered separately in tests/test_vibration_contract.py).
"""
from __future__ import annotations

import contextlib

import pytest
from dash import no_update
from dash._callback_context import context_value
from dash._utils import AttributeDict

from callbacks import vibration_contract
from components.vibration_contract_panel import CLEAR_BTN_ID, SET_BTN_ID
from services.authorization import ADMINISTRATOR, GENERAL, TECHNICIAN
from tests.auth_test_support import no_trusted_session, trusted_session

EVERY_ROLE = (ADMINISTRATOR, TECHNICIAN, GENERAL)
DENIED_ROLES = (TECHNICIAN, GENERAL)


@contextlib.contextmanager
def _triggered_by(prop_id: str):
    """Simulate `dash.callback_context.triggered` outside a real Dash
    request — `_handle_action` reads it to tell SET_BTN_ID apart from
    CLEAR_BTN_ID, the same two-Input-one-Output shape
    callbacks/temperature_threshold.py uses."""
    token = context_value.set(
        AttributeDict({"triggered_inputs": [{"prop_id": prop_id, "value": 1}]})
    )
    try:
        yield
    finally:
        context_value.reset(token)


class _CapturingApp:
    def __init__(self):
        self.functions = {}

    def callback(self, *args, **kwargs):
        def decorator(fn):
            self.functions[fn.__name__] = fn
            return fn

        return decorator


class _Spy:
    def __init__(self, return_value=None):
        self.calls = []
        self.return_value = return_value

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        return self.return_value


@pytest.fixture
def handlers(monkeypatch):
    get_all = _Spy(return_value={})
    set_answer = _Spy(return_value=None)
    clear_answer = _Spy(return_value=None)
    monkeypatch.setattr(vibration_contract.service, "get_all_answers", get_all)
    monkeypatch.setattr(vibration_contract.service, "set_answer", set_answer)
    monkeypatch.setattr(vibration_contract.service, "clear_answer", clear_answer)

    app = _CapturingApp()
    vibration_contract.register(app)
    return app.functions, get_all, set_answer, clear_answer


def _click_set(handler, question_key="unit", answer="mm/s"):
    with _triggered_by(f"{SET_BTN_ID}.n_clicks"):
        return handler(1, 0, question_key, answer)


def _click_clear(handler, question_key="unit", answer=""):
    with _triggered_by(f"{CLEAR_BTN_ID}.n_clicks"):
        return handler(0, 1, question_key, answer)


# ---------------------------------------------------------------------------
# Panel render — authorize before any query
# ---------------------------------------------------------------------------


class TestPanelRenderAuthorization:
    def test_wrong_route_never_queries(self, handlers):
        render, get_all, _set, _clear = handlers
        result = render["_render_panel"]({"route": "device"})
        assert get_all.calls == []
        assert result is no_update

    def test_administrator_renders_the_panel(self, handlers, monkeypatch):
        render, get_all, _set, _clear = handlers
        with trusted_session(monkeypatch, user_id=1, role=ADMINISTRATOR):
            result = render["_render_panel"]({"route": "overview"})
        assert get_all.calls, "an authorized render must query the answers"
        assert result is not None

    @pytest.mark.parametrize("role", DENIED_ROLES)
    def test_denied_roles_never_query_and_render_nothing(self, handlers, monkeypatch, role):
        render, get_all, _set, _clear = handlers
        with trusted_session(monkeypatch, user_id=1, role=role):
            result = render["_render_panel"]({"route": "overview"})
        assert get_all.calls == [], f"{role} must not reach the answers query"
        assert result is None

    def test_no_trusted_session_never_queries(self, handlers):
        render, get_all, _set, _clear = handlers
        with no_trusted_session():
            result = render["_render_panel"]({"route": "overview"})
        assert get_all.calls == []
        assert result is None


# ---------------------------------------------------------------------------
# Set/clear actions — authorize before any write
# ---------------------------------------------------------------------------


class TestActionAuthorization:
    def test_administrator_set_reaches_the_service(self, handlers, monkeypatch):
        functions, _get_all, set_answer, _clear_answer = handlers
        with trusted_session(monkeypatch, user_id=7, role=ADMINISTRATOR):
            _click_set(functions["_handle_action"])
        assert set_answer.calls, "administrator must reach set_answer"
        assert set_answer.calls[0]["actor_user_id"] == 7
        assert set_answer.calls[0]["question_key"] == "unit"
        assert set_answer.calls[0]["answer_text"] == "mm/s"

    def test_administrator_clear_reaches_the_service(self, handlers, monkeypatch):
        functions, _get_all, _set_answer, clear_answer = handlers
        with trusted_session(monkeypatch, user_id=7, role=ADMINISTRATOR):
            _click_clear(functions["_handle_action"])
        assert clear_answer.calls
        assert clear_answer.calls[0]["actor_user_id"] == 7
        assert clear_answer.calls[0]["question_key"] == "unit"

    @pytest.mark.parametrize("role", DENIED_ROLES)
    def test_denied_roles_never_reach_set(self, handlers, monkeypatch, role):
        functions, _get_all, set_answer, _clear_answer = handlers
        with trusted_session(monkeypatch, user_id=1, role=role):
            result = _click_set(functions["_handle_action"])
        assert set_answer.calls == [], f"{role} must not reach set_answer"
        assert result is not None  # a refusal notice, not a silent no-op

    @pytest.mark.parametrize("role", DENIED_ROLES)
    def test_denied_roles_never_reach_clear(self, handlers, monkeypatch, role):
        functions, _get_all, _set_answer, clear_answer = handlers
        with trusted_session(monkeypatch, user_id=1, role=role):
            _click_clear(functions["_handle_action"])
        assert clear_answer.calls == [], f"{role} must not reach clear_answer"

    def test_no_trusted_session_refuses_before_any_write(self, handlers):
        functions, _get_all, set_answer, _clear_answer = handlers
        with no_trusted_session():
            result = _click_set(functions["_handle_action"])
        assert set_answer.calls == []
        assert result is not None

    def test_no_question_selected_is_refused_before_any_write(self, handlers, monkeypatch):
        """A Set/Clear click with nothing selected in the dropdown must be
        a friendly refusal, not a call into the service with a falsy key."""
        functions, _get_all, set_answer, _clear_answer = handlers
        with trusted_session(monkeypatch, user_id=1, role=ADMINISTRATOR):
            result = _click_set(functions["_handle_action"], question_key=None)
        assert set_answer.calls == []
        assert result is not None
