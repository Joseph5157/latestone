"""The Device Management toolbar filters the table it sits above.

The search box and Status dropdown were rendered but read by nothing, so the
table always showed all 120 devices. These cover the filter they now drive.

Search spans the three identity columns an administrator recognises a device
by — code, plant, transformer — and deliberately not the row's internal keys
or its action markdown, where a match would look arbitrary.
"""
import pytest

from callbacks.device_admin import filter_device_rows


def row(device, plant, transformer, status="Active"):
    return {
        "id": f"{plant.lower()}-{device}",
        "device": device,
        "plant": plant,
        "transformer": transformer,
        "status": status,
        "freshness": "Fresh",
        "actions": "[View](#) [Assign](#) [Manage](#)",
        "_state": "fresh",
        "_severity": 0,
    }


@pytest.fixture
def rows():
    return [
        row("29044", "Az Zour South CCGT", "ku01"),
        row("29078", "Bang Pakong", "th01"),
        row("29064", "Bełchatów", "po01", status="Inactive"),
    ]


class TestNoFilter:
    def test_empty_search_and_all_status_returns_every_row(self, rows):
        assert filter_device_rows(rows, "", "all") == rows

    def test_absent_inputs_are_treated_as_no_filter(self, rows):
        assert filter_device_rows(rows, None, None) == rows

    def test_whitespace_search_is_not_a_filter(self, rows):
        assert filter_device_rows(rows, "   ", "all") == rows


class TestSearch:
    def test_matches_device_code(self, rows):
        assert [r["device"] for r in filter_device_rows(rows, "29078", "all")] == ["29078"]

    def test_matches_a_partial_device_code(self, rows):
        assert [r["device"] for r in filter_device_rows(rows, "290", "all")] == [
            "29044", "29078", "29064",
        ]

    def test_matches_plant_name_case_insensitively(self, rows):
        assert [r["device"] for r in filter_device_rows(rows, "bang pakong", "all")] == ["29078"]

    def test_matches_transformer_code(self, rows):
        assert [r["device"] for r in filter_device_rows(rows, "ku01", "all")] == ["29044"]

    def test_matches_a_non_ascii_plant_name(self, rows):
        """Bełchatów is a real plant in the fleet; folding it to ASCII would
        make it unreachable by typing its own name."""
        assert [r["device"] for r in filter_device_rows(rows, "Bełchatów", "all")] == ["29064"]

    def test_no_match_returns_empty_not_everything(self, rows):
        assert filter_device_rows(rows, "no-such-device", "all") == []

    def test_does_not_match_internal_row_keys(self, rows):
        """`_state` carries "fresh" on every row; searching it would return
        the whole table for a term the operator can see nowhere on screen."""
        assert filter_device_rows(rows, "fresh", "all") == []

    def test_does_not_match_action_markdown(self, rows):
        """Every row's actions contain "Manage"."""
        assert filter_device_rows(rows, "Manage", "all") == []


class TestStatus:
    def test_active_excludes_inactive_devices(self, rows):
        assert [r["device"] for r in filter_device_rows(rows, "", "active")] == ["29044", "29078"]

    def test_inactive_selects_only_inactive_devices(self, rows):
        assert [r["device"] for r in filter_device_rows(rows, "", "inactive")] == ["29064"]

    def test_status_match_ignores_label_casing(self, rows):
        """Rows carry the display label ("Active"), the dropdown carries the
        value ("active")."""
        assert filter_device_rows([row("1", "P", "t", status="ACTIVE")], "", "active") != []


class TestCombined:
    def test_search_and_status_both_apply(self, rows):
        assert filter_device_rows(rows, "290", "inactive") == [rows[2]]

    def test_search_that_matches_only_an_excluded_status_returns_empty(self, rows):
        assert filter_device_rows(rows, "Bełchatów", "active") == []


class TestPurity:
    def test_does_not_mutate_the_rows_it_is_given(self, rows):
        before = [dict(r) for r in rows]
        filter_device_rows(rows, "290", "active")
        assert rows == before
