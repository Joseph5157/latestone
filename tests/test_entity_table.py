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


def test_numeric_columns_are_right_aligned_from_their_own_type():
    """Alignment is derived, not listed.

    A per-page list of "which columns are numbers" is a second source of
    truth that drifts the first time a column is added.
    """
    table = entity_table(
        table_id="t",
        columns=[
            {"name": "Plant", "id": "plant"},
            {"name": "Devices", "id": "devices", "type": "numeric"},
        ],
        rows=[],
    )
    conditional = table.children[0].style_cell_conditional
    aligned = {
        r["if"]["column_id"]: r["textAlign"]
        for r in conditional if "textAlign" in r
    }
    assert aligned["devices"] == "right"
    assert "plant" not in aligned


def test_numeric_headers_are_right_aligned_too():
    table = entity_table(
        table_id="t",
        columns=[{"name": "Devices", "id": "devices", "type": "numeric"}],
        rows=[],
    )
    header = table.children[0].style_header_conditional
    assert {"if": {"column_id": "devices"}, "textAlign": "right"} in header


def test_the_identity_column_wraps_and_never_truncates():
    """Half of "Itaipu Binacional Dam (Paraguay part)" is not an identity.

    It is also the cell the operator clicks to navigate, so it is the one
    column that must never hide characters.
    """
    table = entity_table(
        table_id="t",
        columns=[{"name": "Plant", "id": "plant"}],
        rows=[],
        link_column_id="plant",
    )
    rule = next(
        r for r in table.children[0].style_cell_conditional
        if r["if"].get("column_id") == "plant" and "whiteSpace" in r
    )
    assert rule["whiteSpace"] == "normal"


def test_every_other_column_ellipsises_rather_than_clipping():
    """Silent clipping is the failure mode OBS-2 exists to prevent."""
    table = entity_table(table_id="t", columns=[], rows=[])
    assert table.children[0].style_cell["textOverflow"] == "ellipsis"


def test_rows_are_denser_than_the_default():
    table = entity_table(table_id="t", columns=[], rows=[])
    assert table.children[0].style_cell["padding"] == "11px 12px"


def test_responsive_presentation_is_opt_in():
    default = entity_table(table_id="default", columns=[], rows=[])
    responsive = entity_table(
        table_id="responsive", columns=[], rows=[], responsive=True
    )

    assert default.className == "entity-table-wrapper"
    assert responsive.className == "entity-table-wrapper entity-table-wrapper--responsive"


def test_administrative_and_freshness_axes_have_distinct_hooks():
    table = entity_table(
        table_id="axes",
        columns=[
            {"name": "Status", "id": "status"},
            {"name": "Data", "id": "freshness"},
        ],
        rows=[],
        state_column_id="freshness",
        administrative_state_column_id="status",
    )

    classes = set(table.className.split())
    assert "entity-table-wrapper--administrative-axis" in classes
    assert "entity-table-wrapper--freshness-axis" in classes


def test_markdown_target_is_opt_in_and_scoped_to_one_table():
    default = entity_table(table_id="default", columns=[], rows=[])
    same_tab = entity_table(
        table_id="same-tab", columns=[], rows=[], markdown_link_target="_self"
    )

    assert default.children[0].markdown_options is None
    assert same_tab.children[0].markdown_options == {"link_target": "_self"}
