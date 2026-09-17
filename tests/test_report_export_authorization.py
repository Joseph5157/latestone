"""Report export authorization, at the capability boundary (FIX-1B / ADR-013).

`download_report_csv` called `require_action(user, EXPORT_DATA)` while
`require_action` requires a keyword-only `device_id`, so the download raised
`TypeError` before any row was fetched — and the surrounding
`except AuthorizationError` could not catch it. The callback was written
three days after the signature changed, so this path has never worked in any
commit.

`device_id` was never meaningful here: a report spans zero, one, or many
devices, and `EXPORT_DATA`'s `ACTION_POLICY` entry paired every role with an
EMPTY assigned-only set, so no role's export permission ever depended on an
assignment. ADR-013 moves it to `CAPABILITY_POLICY`.

THE POINT OF THE SCOPE TESTS. The guard was never what kept a technician
inside their assigned devices — `installed_rtls_rows` receives a `DeviceScope`
and the repository ANDs `allowed_device_ids` into the query. Migrating the
guard must not disturb that, so it is asserted here directly rather than
assumed.

No database: the row builders and session scope are replaced.
"""
from __future__ import annotations

import types

import pytest

from callbacks import report_center
from services import action_guard
from services.authorization import (
    ADMINISTRATOR,
    AuthorizationError,
    EXPORT_DATA,
    GENERAL,
    TECHNICIAN,
    may_perform_capability,
)
from services.auth_service import AuthenticatedUser
from services.device_scope import DeviceScope
from tests.auth_test_support import no_trusted_session, trusted_session

EVERY_ROLE = (ADMINISTRATOR, TECHNICIAN, GENERAL)


def _user(role: str, user_id: int = 1) -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=user_id, username="someone", full_name="Some One", role=role
    )


def _session(role: str, user_id: int = 1) -> dict:
    return {
        "authenticated": True,
        "user_id": user_id,
        "username": "someone",
        "full_name": "Some One",
        "role": role,
    }


#: Authenticated flag, no usable identity.
STALE_SESSION = {"authenticated": True}

#: A technician who may see exactly one device.
ASSIGNED_SCOPE = DeviceScope(frozenset({"d-assigned"}))


# --------------------------------------------------------------------------
# A. Capability authorization
# --------------------------------------------------------------------------


@pytest.mark.parametrize("role", EVERY_ROLE)
def test_every_confirmed_role_may_export(role):
    """Same role set as the ACTION_POLICY entry it replaces: no widening,
    no narrowing."""
    assert may_perform_capability(role, EXPORT_DATA) is True
    action_guard.require_capability(_user(role), EXPORT_DATA)  # must not raise


def test_absent_identity_is_refused():
    with pytest.raises(AuthorizationError):
        action_guard.require_capability(None, EXPORT_DATA)


def test_unknown_role_may_not_export():
    with pytest.raises(AuthorizationError):
        action_guard.require_capability(_user("intruder"), EXPORT_DATA)


def test_export_needs_no_device_and_reads_no_assignment(monkeypatch):
    """The reason this is a capability at all. `require_capability` is pure;
    if the migration ever regressed to an assignment read, this would fail."""
    calls = []
    monkeypatch.setattr(
        action_guard, "scope_for", lambda user: calls.append(user) or DeviceScope(None)
    )

    action_guard.require_capability(_user(TECHNICIAN), EXPORT_DATA)

    assert calls == [], "the capability guard must never resolve an assignment"


# --------------------------------------------------------------------------
# B and C. The callback, and the scope it must keep passing through
# --------------------------------------------------------------------------


class _CapturingApp:
    def __init__(self):
        self.functions = {}

    def callback(self, *args, **kwargs):
        def decorator(fn):
            self.functions[fn.__name__] = fn
            return fn

        return decorator


class _RowsSpy:
    """Stands in for the report row builder and records the scope it got."""

    def __init__(self):
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        return []


@pytest.fixture
def download(monkeypatch):
    """The download callback, wired to spies instead of the database.

    AUTH-HARDEN-1: identity and scope now come from `current_identity()` /
    `current_device_scope()`, never from the `auth_data` argument the callback
    still accepts (kept only so it re-fires on login/logout). Each test below
    establishes a REAL (fake-backed) trusted session for the role under test
    via `trusted_session`, rather than handing the callback a session dict.
    """
    rows = _RowsSpy()
    maxtemp_rows = _RowsSpy()
    monkeypatch.setattr(report_center, "installed_rtls_rows", rows)
    monkeypatch.setattr(report_center, "max_temperature_rows", maxtemp_rows)
    monkeypatch.setattr(
        report_center, "current_device_scope", lambda: ASSIGNED_SCOPE
    )
    # Resolves plant/transformer names for the document header, which is a
    # database read and not what these tests are about.
    monkeypatch.setattr(
        report_center, "_scope_label", lambda *a, **k: "Test scope"
    )

    app = _CapturingApp()
    report_center.register(app)
    return app.functions["download_report_csv"], rows, maxtemp_rows


def _click(handler, asset_scope="plant", report_key="installed_rtls", export_format="csv"):
    return handler(
        1, report_key, asset_scope, "p1", None, None,
        None, None, None, export_format, None,
    )


def test_download_does_not_raise_type_error(download, monkeypatch):
    """The defect itself: this raised TypeError before any row was fetched."""
    handler, _rows, _maxtemp_rows = download

    with trusted_session(monkeypatch, user_id=1, role=ADMINISTRATOR):
        payload, _status, _style = _click(handler)

    assert payload is not None


@pytest.mark.parametrize("role", EVERY_ROLE)
def test_permitted_roles_reach_export_generation(download, monkeypatch, role):
    handler, rows, maxtemp_rows = download

    with trusted_session(monkeypatch, user_id=1, role=role):
        payload, status, style = _click(handler)

    assert rows.calls, f"{role} must reach row construction"
    assert isinstance(payload, dict) and payload.get("filename"), (
        "an allowed export must return a downloadable payload"
    )
    assert style == {"display": "block"}
    assert status is not None


def test_refusal_happens_before_any_row_work(download):
    """R4-D3's one surviving requirement: refuse before rows are fetched.

    No trusted session at all — the AUTH-HARDEN-1 equivalent of the old
    pre-ROLE-1 STALE_SESSION payload: authenticated flag or not, there is
    nobody the server recognises.
    """
    handler, rows, maxtemp_rows = download

    with no_trusted_session():
        payload, status, _style = _click(handler)

    assert rows.calls == [], "a refused export must not query anything"
    assert payload is not None  # a no_update sentinel, not a file
    assert "not permitted" in str(status)


def test_technician_export_stays_inside_the_assigned_scope(download, monkeypatch):
    """The guard is not what constrains this — the DeviceScope threaded into
    row construction is. Migrating the guard must not change that."""
    handler, rows, maxtemp_rows = download

    with trusted_session(monkeypatch, user_id=1, role=TECHNICIAN):
        _click(handler)

    assert rows.calls, "the technician must reach row construction"
    assert rows.calls[0]["device_scope"] is ASSIGNED_SCOPE, (
        "the session's device scope must reach the repository filter unchanged"
    )
    assert rows.calls[0]["device_scope"].device_ids == frozenset({"d-assigned"})


def test_out_of_scope_devices_cannot_be_reached_through_export(download, monkeypatch):
    """No scope widening: the export passes the caller's scope, and never a
    broader one, whatever asset scope was chosen in the form."""
    handler, rows, maxtemp_rows = download

    with trusted_session(monkeypatch, user_id=1, role=TECHNICIAN):
        _click(handler, asset_scope="device")

    scope = rows.calls[0]["device_scope"]
    assert scope.allows("d-assigned") is True
    assert scope.allows("d-somebody-elses") is False


# --------------------------------------------------------------------------
# D. REPORT-EXPORT-1: Maximum Temperature export and the format choice
# --------------------------------------------------------------------------


def test_max_temperature_export_reaches_row_construction_and_stays_scoped(
    download, monkeypatch,
):
    """The newly-exportable third report goes through the identical
    guard-then-scope path as the other two — not a separate, weaker one."""
    handler, _rows, maxtemp_rows = download

    with trusted_session(monkeypatch, user_id=1, role=TECHNICIAN):
        _click(handler, report_key="max_temperature")

    assert maxtemp_rows.calls, "max_temperature must reach row construction"
    assert maxtemp_rows.calls[0]["device_scope"] is ASSIGNED_SCOPE


def test_max_temperature_refusal_happens_before_any_row_work(download):
    """Authorization must occur before fetching rows, for every report —
    not only the two that existed before this gate."""
    handler, _rows, maxtemp_rows = download

    with no_trusted_session():
        payload, status, _style = _click(handler, report_key="max_temperature")

    assert maxtemp_rows.calls == [], "a refused export must not query anything"
    assert payload is not None
    assert "not permitted" in str(status)


@pytest.mark.parametrize(
    "export_format,expected_extension",
    [("csv", ".csv"), ("pdf", ".pdf"), ("xlsx", ".xlsx")],
)
def test_both_export_formats_reach_generation_with_the_right_extension(
    download, monkeypatch, export_format, expected_extension,
):
    handler, rows, _maxtemp_rows = download

    with trusted_session(monkeypatch, user_id=1, role=ADMINISTRATOR):
        payload, status, style = _click(handler, export_format=export_format)

    assert rows.calls, f"{export_format} must still reach row construction"
    assert payload["filename"].endswith(expected_extension)
    assert style == {"display": "block"}
    assert status is not None


def test_missing_export_format_state_defaults_to_csv(download, monkeypatch):
    """A component that has not fired yet can hand the callback `None` for
    `report-export-format`; that must not crash or silently drop the
    export — it defaults to the CSV development default."""
    handler, rows, _maxtemp_rows = download

    with trusted_session(monkeypatch, user_id=1, role=ADMINISTRATOR):
        payload, _status, _style = handler(
            1, "installed_rtls", "plant", "p1", None, None,
            None, None, None, None, None,
        )

    assert rows.calls
    assert payload["filename"].endswith(".csv")
