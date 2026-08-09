"""Enter must submit the login form.

Regression tests for audit finding NEW-14.

Both login inputs already declared `n_submit=0`, but the callback listened only
to the button's `n_clicks`, so pressing Enter did nothing.

The guard must stay strict about the *initial* firing: the router inserts the
login form dynamically, so the callback fires on insertion with every counter at
0. An `is None` style guard is what previously greeted visitors with "Invalid
username or password." before they had typed anything.
"""
from __future__ import annotations

from callbacks.auth import login_was_submitted


class TestSubmitDetection:
    def test_form_insertion_is_not_a_submission(self):
        """The regression that must not come back: all counters at 0."""
        assert login_was_submitted(0, 0, 0) is False

    def test_none_counters_are_not_a_submission(self):
        assert login_was_submitted(None, None, None) is False

    def test_button_click_submits(self):
        assert login_was_submitted(1, 0, 0) is True

    def test_enter_in_password_submits(self):
        assert login_was_submitted(0, 0, 1) is True

    def test_enter_in_username_submits(self):
        assert login_was_submitted(0, 1, 0) is True

    def test_later_attempts_still_count(self):
        assert login_was_submitted(3, 0, 0) is True
        assert login_was_submitted(0, 2, 4) is True

    def test_mixed_none_and_value_submits(self):
        assert login_was_submitted(None, None, 1) is True
