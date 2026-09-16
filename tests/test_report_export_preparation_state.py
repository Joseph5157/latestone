"""MOBBIN-UX-4: transient "Preparing export..." state on Report Center's
download button.

Presentation-only contract, expressed entirely through the `running=`
argument Dash's own callback registration accepts — no change to
authorization, DeviceScope, CSV/PDF generation, report periods, filenames,
row gathering, or preview/export parity. Those stay covered (and green) by
tests/test_report_export.py, tests/test_report_export_authorization.py and
tests/test_report_export_db.py, unmodified by this tranche.

What this file cannot exercise directly: `running=`'s during/after values,
and the front-end's resolution of `report-download-btn.disabled` having two
legitimate owners (`toggle_download_button` and `download_report_csv`'s
`running=`), are applied by Dash's own client-side runtime — not by
anything reachable through a direct Python call to either decorated
function. This file proves the contract is correctly *declared* (including
the `allow_duplicate=True` pairing Dash's duplicate-output rule requires),
verified against the real `app.py`/`dash.Dash` instance in
TestRealAppRegistration below.
"""
from __future__ import annotations

from callbacks import report_center


class _SpecCapturingApp:
    """Collects each registered callback's full (args, kwargs).

    The `running=`/`allow_duplicate=True` contract lives in the decorator
    call itself, not in anything the function returns, so this stub keeps
    the kwargs and the raw Output objects rather than only the function.
    """

    def __init__(self):
        self.specs = {}

    def callback(self, *args, **kwargs):
        def decorator(fn):
            self.specs[fn.__name__] = (args, kwargs)
            return fn

        return decorator


def _specs():
    app = _SpecCapturingApp()
    report_center.register(app)
    return app.specs


class TestDownloadCallbackRunningState:
    def test_running_is_declared_on_the_download_callback(self):
        _args, kwargs = _specs()["download_report_csv"]
        assert kwargs.get("running"), "download_report_csv must declare running="

    def test_running_targets_only_the_download_button(self):
        _args, kwargs = _specs()["download_report_csv"]
        for output, *_values in kwargs["running"]:
            assert output.component_id == "report-download-btn"

    def test_running_sets_disabled_true_while_preparing_and_false_after(self):
        _args, kwargs = _specs()["download_report_csv"]
        running = {
            output.component_property: (during, after)
            for output, during, after in kwargs["running"]
        }
        assert running["disabled"] == (True, False)

    def test_running_sets_preparing_label_while_running_and_restores_download(self):
        _args, kwargs = _specs()["download_report_csv"]
        running = {
            output.component_property: (during, after)
            for output, during, after in kwargs["running"]
        }
        assert running["children"] == ("Preparing export…", "Download")

    def test_running_disabled_output_allows_the_pre_existing_owner(self):
        """`toggle_download_button` already owns this prop as a real,
        regular Output (R4-D9). Dash requires `allow_duplicate=True` on a
        second writer of the same prop — proven here directly on the
        `running=` Output object, not inferred from absence of an error."""
        _args, kwargs = _specs()["download_report_csv"]
        running_outputs = {
            output.component_property: output for output, *_ in kwargs["running"]
        }
        assert running_outputs["disabled"].allow_duplicate is True

    def test_running_children_output_has_no_other_owner_and_needs_no_flag(self):
        """The layout sets `.children` ("Download") once, statically — no
        other callback declares it, so no `allow_duplicate` is required
        (setting it anyway would not be wrong, but it would misstate that a
        real conflict exists where none does)."""
        _args, kwargs = _specs()["download_report_csv"]
        running_outputs = {
            output.component_property: output for output, *_ in kwargs["running"]
        }
        assert running_outputs["children"].allow_duplicate is False

    def test_download_callback_is_still_a_three_output_callback(self):
        """The running contract is additive only: this callback's own
        declared Outputs (download data, export status text, export status
        style) are unchanged — detailed outcome coverage for each stays in
        tests/test_report_export.py and tests/test_report_export_authorization.py."""
        args, _kwargs = _specs()["download_report_csv"]
        declared_outputs = [dep for dep in args if type(dep).__name__ == "Output"]
        assert len(declared_outputs) == 3


class TestToggleDownloadButtonDuplicateOutput:
    """The pre-existing R4-D9 callback's own side of the same pairing."""

    def test_toggle_download_button_output_allows_duplicate(self):
        args, _kwargs = _specs()["toggle_download_button"]
        declared_outputs = [dep for dep in args if type(dep).__name__ == "Output"]
        assert len(declared_outputs) == 1
        assert declared_outputs[0].component_id == "report-download-btn"
        assert declared_outputs[0].component_property == "disabled"
        assert declared_outputs[0].allow_duplicate is True

    def test_toggle_download_button_still_requires_prevent_initial_call(self):
        """`allow_duplicate=True` without `prevent_initial_call=True` is a
        Dash registration error (see DuplicateCallback) — proven here so a
        future edit cannot silently drop the pairing."""
        _args, kwargs = _specs()["toggle_download_button"]
        assert kwargs.get("prevent_initial_call") is True


class TestRealAppRegistration:
    """Validates the actual duplicate-output pairing against the real
    dash.Dash app, not only the capturing stub above — Dash's own
    validate_duplicate_output runs during real registration."""

    def test_the_real_app_builds_with_no_registration_error(self):
        import app as app_module

        assert app_module.app is not None
