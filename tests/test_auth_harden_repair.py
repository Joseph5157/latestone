"""AUTH-HARDEN-1R — repairing the three blockers independent verification found.

AUTH-HARDEN-1 closed the browser-trust boundary for identity and for the
device-scoped MUTATION callbacks. It missed three READ paths that resolve
real names/metadata from browser-supplied ids without revalidating them
against the CURRENT trusted scope first:

  1. Device registration's plant/transformer loaders and review step
     (callbacks/device_register.py) ran with no authorization check at all —
     administrator-only content reachable by anyone who could invoke the
     callback directly, not only someone who navigated through the
     (administrator-only) route.
  2. Plant/transformer detail (callbacks/listings.py) resolved
     country/fuel/capacity and transformer/device counts for whatever
     plant_id/transformer_id `page-context` named, without checking that id
     against `current_device_scope()` — the same class of bypass P0-3 closed
     for device telemetry, just not applied here too.
  3. Report scope labels (callbacks/report_center.py::_scope_label) resolved
     real plant/transformer/device NAMES from browser-supplied filter ids
     before confirming those ids were in scope, even though the report ROWS
     themselves were already correctly scoped.

Every test below invokes the REAL registered callback with a REAL (fake- or
DB-backed) trusted session — never by hand-building an identity and asserting
the obvious.
"""
from __future__ import annotations

import base64
import types

import pytest

from callbacks import auth as auth_callbacks
from callbacks import device_admin, device_manage, device_register, listings, report_center
from repositories import plant_monitoring_repository as repo
from services import auth_service, hierarchy_service
from services.authorization import EXPORT_DATA, REGISTER_DEVICE
from tests.auth_test_support import fake_user_row, no_trusted_session, trusted_session

# ---------------------------------------------------------------------------
# Shared plumbing
# ---------------------------------------------------------------------------


class _CapturingApp:
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


#: A small fake hierarchy: Plant Alpha (assigned) / Plant Beta (not).
PLANT_A, PLANT_A_NAME = "plant-a", "Plant Alpha"
PLANT_B, PLANT_B_NAME = "plant-b", "Plant Beta"
TRANSFORMER_A, TRANSFORMER_A_CODE = "ta1", "TA1"
TRANSFORMER_B, TRANSFORMER_B_CODE = "tb1", "TB1"
DEVICE_A, DEVICE_A_CODE = "da1", "DA1"  # assigned to the technician
DEVICE_B, DEVICE_B_CODE = "db1", "DB1"  # not assigned to anyone in these tests


class _Plant:
    def __init__(self, plant_id, name):
        self.plant_id = plant_id
        self.name = name
        self.country = "Testland"
        self.primary_fuel = "Gas"
        self.capacity_mw = 100
        self.status = "active"


class _Transformer:
    def __init__(self, transformer_id, plant_id, code):
        self.transformer_id = transformer_id
        self.plant_id = plant_id
        self.transformer_code = code
        self.status = "active"


class _Device:
    def __init__(self, device_id, transformer_id, code):
        self.device_id = device_id
        self.transformer_id = transformer_id
        self.device_code = code
        self.status = "active"


class _DevicePath:
    """Stands in for hierarchy_service.get_device_context's DevicePath."""

    def __init__(self, device_id, device_code, transformer_id, plant_id):
        self.device_id = device_id
        self.device_code = device_code
        self.transformer_id = transformer_id
        self.transformer_code = TRANSFORMER_A_CODE if transformer_id == TRANSFORMER_A else TRANSFORMER_B_CODE
        self.plant_id = plant_id
        self.plant_name = PLANT_A_NAME if plant_id == PLANT_A else PLANT_B_NAME
        self.device_status = "active"


PLANTS = {PLANT_A: _Plant(PLANT_A, PLANT_A_NAME), PLANT_B: _Plant(PLANT_B, PLANT_B_NAME)}
TRANSFORMERS = {
    TRANSFORMER_A: _Transformer(TRANSFORMER_A, PLANT_A, TRANSFORMER_A_CODE),
    TRANSFORMER_B: _Transformer(TRANSFORMER_B, PLANT_B, TRANSFORMER_B_CODE),
}
DEVICES = {
    DEVICE_A: _Device(DEVICE_A, TRANSFORMER_A, DEVICE_A_CODE),
    DEVICE_B: _Device(DEVICE_B, TRANSFORMER_B, DEVICE_B_CODE),
}


@pytest.fixture
def fake_hierarchy(monkeypatch):
    """Wires `services.hierarchy_service` to the fake Plant A / Plant B tree
    above, scope-respecting exactly like the real repository-backed
    functions: `list_transformers`/`list_devices` filter by
    `scope.device_ids` when the scope is not unrestricted."""

    def list_plants(*, scope, include_inactive=False):
        if scope.is_unrestricted:
            return list(PLANTS.values())
        visible_plants = {DEVICES[d].transformer_id for d in scope.device_ids}
        visible_plants = {TRANSFORMERS[t].plant_id for t in visible_plants}
        return [p for p in PLANTS.values() if p.plant_id in visible_plants]

    def list_transformers(plant_id, *, scope, include_inactive=False):
        candidates = [t for t in TRANSFORMERS.values() if t.plant_id == plant_id]
        if scope.is_unrestricted:
            return candidates
        visible = {DEVICES[d].transformer_id for d in scope.device_ids}
        return [t for t in candidates if t.transformer_id in visible]

    def list_devices(transformer_id, *, scope, include_inactive=False):
        candidates = [d for d in DEVICES.values() if d.transformer_id == transformer_id]
        if scope.is_unrestricted:
            return candidates
        return [d for d in candidates if d.device_id in scope.device_ids]

    def get_plant_or_none(plant_id):
        return PLANTS.get(plant_id)

    def get_device_context(device_id):
        device = DEVICES.get(device_id)
        if device is None:
            return None
        return _DevicePath(device.device_id, device.device_code, device.transformer_id, TRANSFORMERS[device.transformer_id].plant_id)

    monkeypatch.setattr(hierarchy_service, "list_plants", list_plants)
    monkeypatch.setattr(hierarchy_service, "list_transformers", list_transformers)
    monkeypatch.setattr(hierarchy_service, "list_devices", list_devices)
    monkeypatch.setattr(hierarchy_service, "get_plant_or_none", get_plant_or_none)
    monkeypatch.setattr(hierarchy_service, "get_device_context", get_device_context)


@pytest.fixture
def technician_assigned_to_a(monkeypatch, fake_hierarchy):
    """A real (fake-backed) technician trusted session, assigned to DEVICE_A
    only — so Plant A / Transformer A are in scope, Plant B / Transformer B
    are not."""
    monkeypatch.setattr(
        repo, "list_active_device_ids_for_user",
        lambda user_id: frozenset({DEVICE_A}),
    )
    with trusted_session(monkeypatch, user_id=104, role="technician"):
        yield


# ---------------------------------------------------------------------------
# Blocker 1 — AUTH-HARDEN-R01..R05, R13: registration loaders
# ---------------------------------------------------------------------------


class TestRegistrationLoaders:
    def _plants_handler(self):
        return _handlers(device_register)["_populate_plants"]

    def _transformers_handler(self):
        return _handlers(device_register)["_populate_transformers"]

    def _review_handler(self):
        return _handlers(device_register)["_show_review"]

    # -- R01: unauthenticated --
    def test_r01_unauthenticated_plant_loader_returns_nothing(self, fake_hierarchy):
        with no_trusted_session():
            result = self._plants_handler()("device-register-plant")
        assert result == []

    # -- R02: technician --
    def test_r02_technician_plant_loader_is_denied(self, monkeypatch, fake_hierarchy):
        with trusted_session(monkeypatch, user_id=104, role="technician"):
            result = self._plants_handler()("device-register-plant")
        assert result == []

    # -- R03: general --
    def test_r03_general_plant_loader_is_denied(self, monkeypatch, fake_hierarchy):
        with trusted_session(monkeypatch, user_id=7, role="general"):
            result = self._plants_handler()("device-register-plant")
        assert result == []

    # -- R04: technician, transformer loader --
    def test_r04_technician_transformer_loader_is_denied(self, monkeypatch, fake_hierarchy):
        with trusted_session(monkeypatch, user_id=104, role="technician"):
            options, disabled = self._transformers_handler()(PLANT_B)
        assert options == []
        assert disabled is True

    def test_r04b_unauthenticated_transformer_loader_is_denied(self, fake_hierarchy):
        with no_trusted_session():
            options, disabled = self._transformers_handler()(PLANT_B)
        assert options == []
        assert disabled is True

    def test_r04c_general_transformer_loader_is_denied(self, monkeypatch, fake_hierarchy):
        with trusted_session(monkeypatch, user_id=7, role="general"):
            options, disabled = self._transformers_handler()(PLANT_B)
        assert options == []
        assert disabled is True

    # -- R05: technician, review with arbitrary plant/transformer ids --
    def test_r05_technician_review_is_denied_no_metadata_leak(self, monkeypatch, fake_hierarchy):
        from components.status_panels import ACTION_REFUSED_CLASS

        with trusted_session(monkeypatch, user_id=104, role="technician"):
            result = self._review_handler()(
                1, "dv-forged", PLANT_B, TRANSFORMER_B, "active"
            )

        # code-error, plant-error, transformer-error, form-style, review-style,
        # review-summary, error-style, error-children
        assert result[4] is None or result[4] != {"display": "block"}, (
            "the review panel must not be shown for a refused caller"
        )
        assert result[6] == {"display": "block"}, "the error slot must be shown"
        assert getattr(result[7], "className", "") == ACTION_REFUSED_CLASS
        rendered = str(result[7])
        assert PLANT_B_NAME not in rendered
        assert TRANSFORMER_B_CODE not in rendered

    def test_r05b_general_review_is_denied_no_metadata_leak(self, monkeypatch, fake_hierarchy):
        from components.status_panels import ACTION_REFUSED_CLASS

        with trusted_session(monkeypatch, user_id=7, role="general"):
            result = self._review_handler()(
                1, "dv-forged", PLANT_B, TRANSFORMER_B, "active"
            )

        assert result[6] == {"display": "block"}
        assert getattr(result[7], "className", "") == ACTION_REFUSED_CLASS
        rendered = str(result[7])
        assert PLANT_B_NAME not in rendered
        assert TRANSFORMER_B_CODE not in rendered

    def test_r05c_unauthenticated_review_is_denied_no_metadata_leak(self, fake_hierarchy):
        from components.status_panels import ACTION_REFUSED_CLASS

        with no_trusted_session():
            result = self._review_handler()(
                1, "dv-forged", PLANT_B, TRANSFORMER_B, "active"
            )

        assert result[6] == {"display": "block"}
        assert getattr(result[7], "className", "") == ACTION_REFUSED_CLASS
        rendered = str(result[7])
        assert PLANT_B_NAME not in rendered
        assert TRANSFORMER_B_CODE not in rendered

    # -- R13: administrator still works --
    def test_r13_administrator_plant_loader_still_works(self, monkeypatch, fake_hierarchy):
        with trusted_session(monkeypatch, user_id=1, role="administrator"):
            options = self._plants_handler()("device-register-plant")
        assert {o["value"] for o in options} == {PLANT_A, PLANT_B}

    def test_r13b_administrator_transformer_loader_still_works(self, monkeypatch, fake_hierarchy):
        with trusted_session(monkeypatch, user_id=1, role="administrator"):
            options, disabled = self._transformers_handler()(PLANT_B)
        assert [o["value"] for o in options] == [TRANSFORMER_B]
        assert disabled is False

    def test_r13c_administrator_review_still_works_and_names_the_real_plant(
        self, monkeypatch, fake_hierarchy
    ):
        with trusted_session(monkeypatch, user_id=1, role="administrator"):
            result = self._review_handler()(
                1, "dv-new", PLANT_B, TRANSFORMER_B, "active"
            )
        summary_text = str(result[5])
        assert PLANT_B_NAME in summary_text
        assert TRANSFORMER_B_CODE in summary_text


# ---------------------------------------------------------------------------
# Blocker 2 — AUTH-HARDEN-R06..R08: plant detail
# ---------------------------------------------------------------------------


class TestPlantDetailScope:
    def _handler(self):
        return _handlers(listings)["populate_plant_detail"]

    def test_r06_technician_out_of_scope_plant_leaks_no_metadata(
        self, technician_assigned_to_a
    ):
        rows, _columns, error, kpis, context, metric_health, attribution = self._handler()(
            {"route": "plant", "plant_id": PLANT_B}, None
        )
        assert rows == []
        assert error is not None
        assert kpis is None and context is None and metric_health is None and attribution is None
        rendered = "".join(str(x) for x in (error,))
        assert PLANT_B_NAME not in rendered
        assert "Testland" not in rendered

    def test_r07_technician_in_scope_plant_renders_normally(
        self, technician_assigned_to_a, monkeypatch
    ):
        from services import monitoring_service

        monkeypatch.setattr(monitoring_service, "latest_reading_rows", lambda **k: [])
        monkeypatch.setattr(monitoring_service, "latest_metric_readings", lambda *a, **k: [])

        rows, _columns, error, _kpis, context, _metric_health, _attribution = self._handler()(
            {"route": "plant", "plant_id": PLANT_A}, None
        )
        assert error is None
        assert context is not None
        rendered = str(context)
        assert PLANT_A_NAME in rendered or "Testland" in rendered

    def test_r08_general_plant_detail_unchanged_unrestricted(
        self, monkeypatch, fake_hierarchy
    ):
        from services import monitoring_service

        monkeypatch.setattr(monitoring_service, "latest_reading_rows", lambda **k: [])
        monkeypatch.setattr(monitoring_service, "latest_metric_readings", lambda *a, **k: [])

        with trusted_session(monkeypatch, user_id=7, role="general"):
            rows, _columns, error, _kpis, context, _metric_health, _attribution = (
                self._handler()({"route": "plant", "plant_id": PLANT_B}, None)
            )
        assert error is None, "General must retain unrestricted read access"
        assert context is not None

    def test_administrator_plant_detail_unchanged(self, monkeypatch, fake_hierarchy):
        from services import monitoring_service

        monkeypatch.setattr(monitoring_service, "latest_reading_rows", lambda **k: [])
        monkeypatch.setattr(monitoring_service, "latest_metric_readings", lambda *a, **k: [])

        with trusted_session(monkeypatch, user_id=1, role="administrator"):
            _rows, _columns, error, _kpis, context, _metric_health, _attribution = (
                self._handler()({"route": "plant", "plant_id": PLANT_B}, None)
            )
        assert error is None
        assert context is not None


# ---------------------------------------------------------------------------
# AUTH-HARDEN-1R2 (transformer detail coverage) — R2-16..R2-19: no prior
# dedicated regression test invoked the registered
# `populate_transformer_detail` callback directly, even though its
# `entity_in_scope` guard (Blocker 2's fix, mirrored one level down the
# hierarchy) was already in the production code.
# ---------------------------------------------------------------------------


class TestTransformerDetailScope:
    def _handler(self):
        return _handlers(listings)["populate_transformer_detail"]

    def _mock_monitoring(self, monkeypatch):
        from services import monitoring_service

        monkeypatch.setattr(monitoring_service, "latest_reading_rows", lambda **k: [])
        monkeypatch.setattr(monitoring_service, "latest_metric_readings", lambda *a, **k: [])

    def test_r2_16_technician_assigned_transformer_detail_passes(
        self, technician_assigned_to_a, monkeypatch
    ):
        self._mock_monitoring(monkeypatch)
        rows, _columns, error, kpis, context, metric_health, attribution = self._handler()(
            {
                "route": "transformer",
                "transformer_id": TRANSFORMER_A,
                "plant_name": PLANT_A_NAME,
                "transformer_code": TRANSFORMER_A_CODE,
            },
            None,
        )
        assert error is None
        assert context is not None
        assert str(context).count(TRANSFORMER_A_CODE) >= 1

    def test_r2_17_technician_unrelated_transformer_detail_denied_no_metadata(
        self, technician_assigned_to_a
    ):
        rows, _columns, error, kpis, context, metric_health, attribution = self._handler()(
            {
                "route": "transformer",
                "transformer_id": TRANSFORMER_B,
                "plant_name": PLANT_B_NAME,
                "transformer_code": TRANSFORMER_B_CODE,
            },
            None,
        )
        assert rows == []
        assert error is not None
        assert kpis is None and context is None and metric_health is None and attribution is None
        rendered = str(error)
        assert TRANSFORMER_B_CODE not in rendered
        assert PLANT_B_NAME not in rendered

    def test_r2_18_administrator_transformer_detail_unchanged(
        self, monkeypatch, fake_hierarchy
    ):
        self._mock_monitoring(monkeypatch)
        with trusted_session(monkeypatch, user_id=1, role="administrator"):
            _rows, _columns, error, _kpis, context, _metric_health, _attribution = (
                self._handler()(
                    {
                        "route": "transformer",
                        "transformer_id": TRANSFORMER_B,
                        "plant_name": PLANT_B_NAME,
                        "transformer_code": TRANSFORMER_B_CODE,
                    },
                    None,
                )
            )
        assert error is None
        assert context is not None

    def test_r2_19_general_transformer_detail_unchanged_unrestricted(
        self, monkeypatch, fake_hierarchy
    ):
        self._mock_monitoring(monkeypatch)
        with trusted_session(monkeypatch, user_id=7, role="general"):
            _rows, _columns, error, _kpis, context, _metric_health, _attribution = (
                self._handler()(
                    {
                        "route": "transformer",
                        "transformer_id": TRANSFORMER_B,
                        "plant_name": PLANT_B_NAME,
                        "transformer_code": TRANSFORMER_B_CODE,
                    },
                    None,
                )
            )
        assert error is None, "General must retain unrestricted read access"
        assert context is not None


# ---------------------------------------------------------------------------
# Blocker 3 — AUTH-HARDEN-R09..R12, R14, R15: report scope labels
# ---------------------------------------------------------------------------


class TestReportScopeLabels:
    def _preview_handler(self):
        return _handlers(report_center)["generate_report"]

    def _export_handler(self):
        return _handlers(report_center)["download_report_csv"]

    def _preview_label(self, **kwargs):
        """generate_report's scope-desc path only runs for a report key
        outside the two specially-handled ones ("installed_rtls",
        "rtl_alarms_30d") — "max_temperature" reaches it."""
        n_clicks, plant_id, transformer_id, device_id, asset_scope = (
            1, kwargs.get("plant_id", ""), kwargs.get("transformer_id", ""),
            kwargs.get("device_id", ""), kwargs.get("asset_scope", "plant"),
        )
        _style, result = self._preview_handler()(
            n_clicks, "max_temperature", asset_scope, plant_id, transformer_id,
            device_id, None, None, None, None,
        )
        return str(result)

    # -- R09: out-of-scope plant --
    def test_r09_technician_out_of_scope_plant_label_no_leak(
        self, technician_assigned_to_a, monkeypatch
    ):
        monkeypatch.setattr(report_center, "installed_rtls_rows", lambda **k: [])
        rendered = self._preview_label(asset_scope="plant", plant_id=PLANT_B)
        assert PLANT_B_NAME not in rendered
        assert PLANT_B in rendered, "the raw id is echoed back, not a resolved name"

    # -- R10: out-of-scope transformer --
    def test_r10_technician_out_of_scope_transformer_label_no_leak(
        self, technician_assigned_to_a, monkeypatch
    ):
        monkeypatch.setattr(report_center, "installed_rtls_rows", lambda **k: [])
        rendered = self._preview_label(
            asset_scope="transformer", plant_id=PLANT_B, transformer_id=TRANSFORMER_B
        )
        assert TRANSFORMER_B_CODE not in rendered
        assert PLANT_B_NAME not in rendered

    # -- R11: out-of-scope device --
    def test_r11_technician_out_of_scope_device_label_no_leak(
        self, technician_assigned_to_a, monkeypatch
    ):
        monkeypatch.setattr(report_center, "installed_rtls_rows", lambda **k: [])
        rendered = self._preview_label(asset_scope="device", device_id=DEVICE_B)
        assert DEVICE_B_CODE not in rendered
        assert DEVICE_B in rendered

    # -- R12: assigned report target resolves correctly --
    def test_r12_technician_assigned_target_resolves_the_real_label(
        self, technician_assigned_to_a, monkeypatch
    ):
        monkeypatch.setattr(report_center, "installed_rtls_rows", lambda **k: [])
        rendered = self._preview_label(asset_scope="plant", plant_id=PLANT_A)
        assert PLANT_A_NAME in rendered

    # -- R2-10: assigned technician TRANSFORMER label resolves correctly --
    def test_r2_10_technician_assigned_transformer_label_resolves_the_real_code(
        self, technician_assigned_to_a, monkeypatch
    ):
        monkeypatch.setattr(report_center, "installed_rtls_rows", lambda **k: [])
        rendered = self._preview_label(
            asset_scope="transformer", plant_id=PLANT_A, transformer_id=TRANSFORMER_A
        )
        assert TRANSFORMER_A_CODE in rendered
        assert PLANT_A_NAME in rendered

    # -- R2-11: assigned technician DEVICE label resolves correctly --
    def test_r2_11_technician_assigned_device_label_resolves_the_real_code(
        self, technician_assigned_to_a, monkeypatch
    ):
        monkeypatch.setattr(report_center, "installed_rtls_rows", lambda **k: [])
        rendered = self._preview_label(asset_scope="device", device_id=DEVICE_A)
        assert DEVICE_A_CODE in rendered

    # ------------------------------------------------------------------
    # AUTH-HARDEN-1R2 Finding 2: the export-path tests below inspect the
    # ACTUAL download payload `download_report_csv` hands back
    # (`dcc.send_bytes`'s dict: base64 `content` + `filename`), not the
    # separate status Div. The status Div only ever says "Exported N
    # row(s)" — it never carries a scope label at all, so a test that
    # checked it (as the old `test_export_path_out_of_scope_plant_label_
    # no_leak` did) could not have caught a leak even if `_scope_label`
    # were still broken. `format_csv` never writes `document.period_label`
    # into the CSV body either (services/report_export.py) — the only
    # place `_scope_label`'s output actually reaches the export is the
    # FILENAME (`export_filename`), so that is what these decode and
    # assert against.
    # ------------------------------------------------------------------

    def _download_payload(self, **kwargs):
        """Invoke the real `download_report_csv` and return
        (csv_text, filename) decoded from its actual `dcc.send_bytes`
        payload — the first tuple element, previously ignored entirely by
        the test this replaces."""
        n_clicks, report_key, asset_scope, plant_id, transformer_id, device_id = (
            1, kwargs.get("report_key", "installed_rtls"), kwargs["asset_scope"],
            kwargs.get("plant_id", ""), kwargs.get("transformer_id", ""),
            kwargs.get("device_id", ""),
        )
        download, _status, _style = self._export_handler()(
            n_clicks, report_key, asset_scope, plant_id, transformer_id,
            device_id, None,
        )
        csv_text = base64.b64decode(download["content"]).decode("utf-8")
        return csv_text, download["filename"]

    # -- R2-12: export, out-of-scope plant --
    def test_r2_12_export_out_of_scope_plant_reveals_no_resolved_metadata(
        self, technician_assigned_to_a, monkeypatch
    ):
        monkeypatch.setattr(report_center, "installed_rtls_rows", lambda **k: [])
        csv_text, filename = self._download_payload(asset_scope="plant", plant_id=PLANT_B)
        assert "Plant_Beta" not in filename
        assert PLANT_B_NAME not in csv_text
        assert PLANT_B in filename, "the raw id is echoed back, not a resolved name"

    # -- R2-13: export, out-of-scope transformer --
    def test_r2_13_export_out_of_scope_transformer_reveals_no_resolved_metadata(
        self, technician_assigned_to_a, monkeypatch
    ):
        monkeypatch.setattr(report_center, "installed_rtls_rows", lambda **k: [])
        csv_text, filename = self._download_payload(
            asset_scope="transformer", plant_id=PLANT_B, transformer_id=TRANSFORMER_B,
        )
        assert TRANSFORMER_B_CODE not in filename
        assert PLANT_B_NAME not in filename
        assert TRANSFORMER_B_CODE not in csv_text
        assert PLANT_B_NAME not in csv_text

    # -- R2-14: export, out-of-scope device --
    def test_r2_14_export_out_of_scope_device_reveals_no_resolved_metadata(
        self, technician_assigned_to_a, monkeypatch
    ):
        monkeypatch.setattr(report_center, "installed_rtls_rows", lambda **k: [])
        csv_text, filename = self._download_payload(asset_scope="device", device_id=DEVICE_B)
        assert DEVICE_B_CODE not in filename
        assert DEVICE_B_CODE not in csv_text
        assert DEVICE_B in filename

    # -- R2-15: export, assigned technician asset resolves the real label --
    def test_r2_15_export_assigned_target_contains_the_permitted_scope_label(
        self, technician_assigned_to_a, monkeypatch
    ):
        monkeypatch.setattr(report_center, "installed_rtls_rows", lambda **k: [])
        _csv_text, filename = self._download_payload(asset_scope="plant", plant_id=PLANT_A)
        assert "Plant_Alpha" in filename, (
            "an in-scope export must still name its own asset in the filename"
        )

    # -- R14: administrator report labels still work --
    def test_r14_administrator_report_label_still_resolves_real_names(
        self, monkeypatch, fake_hierarchy
    ):
        monkeypatch.setattr(report_center, "installed_rtls_rows", lambda **k: [])
        with trusted_session(monkeypatch, user_id=1, role="administrator"):
            _style, result = self._preview_handler()(
                1, "max_temperature", "plant", PLANT_B, "", "", None, None, None, None,
            )
        assert PLANT_B_NAME in str(result)

    # -- R15: general report functionality unchanged --
    def test_r15_general_report_label_still_resolves_real_names(
        self, monkeypatch, fake_hierarchy
    ):
        monkeypatch.setattr(report_center, "installed_rtls_rows", lambda **k: [])
        with trusted_session(monkeypatch, user_id=7, role="general"):
            _style, result = self._preview_handler()(
                1, "max_temperature", "plant", PLANT_B, "", "", None, None, None, None,
            )
        assert PLANT_B_NAME in str(result), (
            "General must retain unrestricted read access to report labels"
        )


# ---------------------------------------------------------------------------
# A-D: additional test-quality improvements the gate named explicitly, on
# top of R01-R15's coverage of the three blockers themselves.
# ---------------------------------------------------------------------------


class _Creds:
    """A minimal demo_auth-shaped double: username/password -> a one-entry
    credential map, exactly the settings object verify_credentials reads."""

    config_error = None

    def __init__(self, username, password):
        self.username = username
        self.password = password

    @property
    def credentials(self):
        return {self.username: self.password}


class TestAdditionalHardening:
    """A-D from the AUTH-HARDEN-1R gate: these strengthen how three EXISTING
    proofs are demonstrated, not new coverage on their own."""

    # -- A: a REAL handle_login() call establishes the trusted session,
    # never a manual start_trusted_session() for this specific case --
    def test_a_real_login_callback_establishes_the_trusted_session(self, monkeypatch):
        from config import settings

        creds = _Creds("operator", "s3cret")
        monkeypatch.setattr(auth_service, "demo_auth", creds)
        monkeypatch.setattr(settings, "demo_auth", creds)
        monkeypatch.setattr(auth_service.prototype_users, "seed_demo_user", lambda: None)

        row = fake_user_row(55, "administrator", username="operator")
        monkeypatch.setattr(
            auth_service.repo, "get_user_by_username",
            lambda u: row if u == "operator" else None,
        )
        monkeypatch.setattr(repo, "get_user_by_id", lambda uid: row if uid == 55 else None)

        handler = _handlers(auth_callbacks)["handle_login"]

        with no_trusted_session():
            assert auth_service.current_identity() is None, "no session before login"

            error, session_payload = handler(1, 0, 0, "operator", "s3cret")

            assert error == ""
            assert session_payload["user_id"] == 55
            identity = auth_service.current_identity()

        assert identity is not None, "handle_login must itself establish the trusted session"
        assert identity.user_id == 55
        assert identity.role == "administrator"

    # -- B: inactive mid-session, invoked against a REAL protected callback --
    def test_b_inactive_user_is_denied_on_a_real_protected_callback(self, monkeypatch):
        state = {"status": "active"}
        base = fake_user_row(1, "administrator")

        def get_by_id(uid):
            if uid != 1:
                return None
            return repo.UserRecord(
                user_id=1, username=base.username, full_name=base.full_name,
                email_address=None, mobile_number=None, role="administrator",
                status=state["status"], created_at=base.created_at, updated_at=base.updated_at,
            )

        monkeypatch.setattr(repo, "get_user_by_id", get_by_id)
        monkeypatch.setattr(device_admin.hierarchy_service, "list_all_devices", lambda **k: [])
        health = types.SimpleNamespace(devices={}, device_last_updated={})
        monkeypatch.setattr(
            device_admin.monitoring_service, "get_fleet_health", lambda *a, **k: health
        )
        monkeypatch.setattr(
            device_admin.prototype_assignments, "assigned_technicians", lambda: {}
        )
        handler = _handlers(device_admin)["populate_device_admin"]

        with no_trusted_session():
            auth_service.start_trusted_session(1)

            _rows, _columns, error, summary, _empty = handler(
                {"route": "admin_devices"}, "", "all"
            )
            assert error is None and summary, "starts as an active administrator"

            state["status"] = "inactive"  # an administrator disables them mid-session

            rows, _columns, error, _summary, _empty = handler(
                {"route": "admin_devices"}, "", "all"
            )

        assert rows == []
        assert error is not None, (
            "the same trusted session must be refused on its very next call, "
            "with no logout/login in between"
        )

    # -- C: Technician -> General revocation, real Technician-only callback --
    def test_c_technician_demoted_to_general_is_denied_on_next_operation(self, monkeypatch):
        state = {"role": "technician"}
        base = fake_user_row(104, "technician")

        def get_by_id(uid):
            if uid != 104:
                return None
            return repo.UserRecord(
                user_id=104, username=base.username, full_name=base.full_name,
                email_address=None, mobile_number=None, role=state["role"],
                status="active", created_at=base.created_at, updated_at=base.updated_at,
            )

        monkeypatch.setattr(repo, "get_user_by_id", get_by_id)
        monkeypatch.setattr(
            repo, "list_active_device_ids_for_user",
            lambda user_id: frozenset({"assigned-device"}),
        )
        calls = []
        monkeypatch.setattr(
            device_manage.rtl_programming_service, "record_request",
            lambda **k: calls.append(k)
            or types.SimpleNamespace(request_id="r1", device_id=k["device_id"]),
        )
        handler = _handlers(device_manage)["confirm_program_rtl"]

        with no_trusted_session():
            auth_service.start_trusted_session(104)

            handler(1, "assigned-device", "uid-1", "t1", "0821234567", None)
            assert calls, (
                "PROGRAM_RTL is Administrator+Technician (assigned scope) - "
                "starts allowed for this technician's own device"
            )

            state["role"] = "general"  # demoted mid-session, no re-login
            calls.clear()

            handler(1, "assigned-device", "uid-1", "t1", "0821234567", None)

        assert calls == [], (
            "General holds no operational-action capability at all - the SAME "
            "session must be refused this action on its very next attempt"
        )

    # -- D: an explicitly mismatched forged user_id, against a real callback --
    def test_d_forged_browser_user_id_does_not_borrow_another_technicians_scope(
        self, monkeypatch
    ):
        """The weaker version of this proof (TestForgedUserId in
        test_auth_harden.py) only checked current_device_scope() directly.
        This drives the SAME scenario through a real, registered, State-
        wired callback that still receives an auth-store payload argument
        (confirm_program_rtl), with that payload explicitly naming a
        DIFFERENT real technician than the one actually signed in."""
        tech_a = fake_user_row(104, "technician", username="tech.a")
        tech_b = fake_user_row(105, "technician", username="tech.b")
        rows = {104: tech_a, 105: tech_b}
        monkeypatch.setattr(repo, "get_user_by_id", lambda uid: rows.get(uid))

        assignments = {104: frozenset({"device-a"}), 105: frozenset({"device-b"})}
        monkeypatch.setattr(
            repo, "list_active_device_ids_for_user",
            lambda user_id: assignments.get(user_id, frozenset()),
        )

        calls = []
        monkeypatch.setattr(
            device_manage.rtl_programming_service, "record_request",
            lambda **k: calls.append(k)
            or types.SimpleNamespace(request_id="r1", device_id=k["device_id"]),
        )
        handler = _handlers(device_manage)["confirm_program_rtl"]

        #: Claims to BE technician B - the actual owner of "device-b".
        forged_auth_data = {
            "authenticated": True, "user_id": 105, "username": "tech.b",
            "full_name": "Tech B", "role": "technician",
        }

        with no_trusted_session():
            auth_service.start_trusted_session(104)  # really signed in as A

            # A's own device: must still succeed on A's real session, the
            # forged payload notwithstanding.
            handler(1, "device-a", "uid-1", "t1", "0821234567", forged_auth_data)
            assert calls, "the real session's own device must still work"
            calls.clear()

            # B's device, claimed via the forged payload: must be refused,
            # proving the forged user_id bought no widened scope at all.
            handler(1, "device-b", "uid-1", "t1", "0821234567", forged_auth_data)

        assert calls == [], (
            "a forged auth-store user_id must not grant access to technician "
            "B's device while the trusted Flask session is technician A"
        )
