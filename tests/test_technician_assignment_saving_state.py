"""MOBBIN-UX-3: transient "Saving..." state on Technician Assignment's confirm.

Presentation-only contract, expressed entirely through the `running=`
argument Dash's own callback registration accepts — no change to
authorization, DeviceScope, persistence, or the existing success/failure/
no-op/refusal copy. Those outcomes stay covered (and green) by
tests/test_action_guard_callbacks.py::TestConfirmAssignment; this file only
proves the transient state Dash applies around that unchanged function.

What this file cannot exercise directly: `running=`'s during/after values are
applied by Dash's own front-end runtime around the HTTP request/response
cycle (including when the callback raises), not by anything reachable
through a direct Python call to the decorated function. That reset-on-
exception guarantee is documented Dash behaviour, verified here only by
proving the `running` contract is correctly declared and does not depend on
this function's control flow.
"""
from __future__ import annotations

from callbacks import device_assign
from components.assign_device_drawer import ASSIGN_CONFIRM_BTN


class _SpecCapturingApp:
    """Collects each registered callback's full (args, kwargs).

    `_handlers()` helpers elsewhere in this suite keep only the decorated
    function; the `running=` contract lives in the decorator call itself, so
    this stub keeps the kwargs too.
    """

    def __init__(self):
        self.specs = {}

    def callback(self, *args, **kwargs):
        def decorator(fn):
            self.specs[fn.__name__] = (args, kwargs)
            return fn

        return decorator


def _confirm_assignment_spec():
    app = _SpecCapturingApp()
    device_assign.register(app)
    return app.specs["confirm_assignment"]


class TestConfirmAssignmentRunningState:
    def test_running_is_declared_on_the_confirm_callback(self):
        _args, kwargs = _confirm_assignment_spec()
        assert kwargs.get("running"), "confirm_assignment must declare running="

    def test_running_targets_only_the_confirm_button(self):
        """No other component (the table, the result slot, the whole
        drawer) is touched by the transient state — only the button the
        operator just clicked."""
        _args, kwargs = _confirm_assignment_spec()
        running = kwargs["running"]
        for output, *_values in running:
            assert output.component_id == ASSIGN_CONFIRM_BTN

    def test_running_sets_disabled_true_while_saving_and_false_after(self):
        _args, kwargs = _confirm_assignment_spec()
        running = dict(
            (output.component_property, (during, after))
            for output, during, after in kwargs["running"]
        )
        assert running["disabled"] == (True, False)

    def test_running_sets_saving_label_while_saving_and_restores_after(self):
        _args, kwargs = _confirm_assignment_spec()
        running = dict(
            (output.component_property, (during, after))
            for output, during, after in kwargs["running"]
        )
        assert running["children"] == ("Saving…", "Confirm Assignment")

    def test_running_outputs_are_not_also_regular_callback_outputs(self):
        """Dash refuses a `running` Output that is also a declared Output of
        the same callback (a genuine conflict, not a style choice) — proven
        here so a future edit cannot silently reintroduce it."""
        args, kwargs = _confirm_assignment_spec()
        running = kwargs["running"]
        running_targets = {
            (output.component_id, output.component_property)
            for output, *_ in running
        }
        declared_targets = {
            (dep.component_id, dep.component_property)
            for dep in args
            if getattr(dep, "component_property", None) is not None
            and type(dep).__name__ == "Output"
        }
        assert running_targets.isdisjoint(declared_targets)

    def test_confirm_assignment_is_still_a_two_output_callback(self):
        """The running contract is additive only: this callback's own
        declared Outputs (result slot, close-button label) are unchanged —
        detailed outcome coverage for each stays in
        TestConfirmAssignment (tests/test_action_guard_callbacks.py)."""
        args, _kwargs = _confirm_assignment_spec()
        declared_outputs = [
            dep for dep in args if type(dep).__name__ == "Output"
        ]
        assert len(declared_outputs) == 2
