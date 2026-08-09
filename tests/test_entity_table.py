"""Presentation contracts for the shared entity table."""
from components.entity_table import entity_table, freshness_style_rules
from services.monitoring_service import Freshness


def test_one_style_rule_per_freshness_state():
    """A fourth state must never ship unstyled.

    Asserting the count against the enum rather than against 3 means adding a
    state breaks this test instead of silently rendering in default black.
    """
    rules = freshness_style_rules("freshness")
    assert len(rules) == len(Freshness)


def test_style_rules_join_on_state_identity_not_display_text():
    """Guards the contract: _state identifies, rendered text presents.

    "Stale" is a label that may be reworded; `stale` is the enum's value.
    """
    queries = [r["if"]["filter_query"] for r in freshness_style_rules("freshness")]
    assert '{_state} eq "stale"' in queries
    assert not any("Stale" in q for q in queries)
    assert not any("_severity" in q for q in queries)


def test_style_rules_are_scoped_to_the_named_column():
    rules = freshness_style_rules("freshness")
    assert {r["if"]["column_id"] for r in rules} == {"freshness"}


def test_entity_table_applies_state_rules_when_a_state_column_is_named():
    table = entity_table(
        table_id="t",
        columns=[{"name": "Data", "id": "freshness"}],
        rows=[],
        state_column_id="freshness",
    )
    conditional = table.children[0].style_data_conditional
    assert any("_state" in str(r.get("if", {})) for r in conditional)


def test_entity_table_without_a_state_column_adds_no_state_rules():
    table = entity_table(table_id="t", columns=[], rows=[])
    conditional = table.children[0].style_data_conditional
    assert not any("_state" in str(r.get("if", {})) for r in conditional)
