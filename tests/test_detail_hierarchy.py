"""UI-3 structural contracts for Plant and Transformer detail pages.

These tests pin presentation hierarchy without asserting pixels. Data values,
scope and route outcomes remain covered by the existing detail/ROLE-3 suites.
"""
from __future__ import annotations

from pages import plant_detail, transformer_detail
from tests.dash_tree import find_by_exact_class, find_by_id, links, text_of


def _assert_common_hierarchy(layout, *, context_id, kpis_id, metric_id, attribution_id):
    [summary] = find_by_exact_class(layout, "detail-operational-summary")
    [metric_section] = find_by_exact_class(layout, "detail-metric-section")

    assert find_by_id(summary, context_id) is not None
    assert find_by_id(summary, kpis_id) is not None
    assert find_by_id(summary, attribution_id) is not None
    assert find_by_id(metric_section, metric_id) is not None
    assert "Operational summary" in text_of(summary)
    assert "Metric health" in text_of(metric_section)


def _assert_table_axes(layout, table_id):
    table = find_by_id(layout, table_id)
    assert table is not None
    wrapper = next(
        node for node in find_by_exact_class(layout, "entity-table-wrapper")
        if find_by_id(node, table_id) is not None
    )
    classes = wrapper.className.split()
    assert "entity-table-wrapper--responsive" in classes
    assert "entity-table-wrapper--administrative-axis" in classes
    assert "entity-table-wrapper--freshness-axis" in classes


class TestPlantHierarchy:
    def test_preserves_identity_and_fleet_breadcrumb(self):
        layout = plant_detail.layout("Itaipu")
        assert "Itaipu" in text_of(layout)
        assert ("Fleet", "/plants") in links(layout)

    def test_groups_summary_before_metric_detail_and_inventory(self):
        layout = plant_detail.layout("Itaipu")
        _assert_common_hierarchy(
            layout,
            context_id="plant-context",
            kpis_id="plant-kpis",
            metric_id="plant-metric-health",
            attribution_id="plant-attribution",
        )
        rendered = text_of(layout)
        assert rendered.index("Operational summary") < rendered.index("Metric health")
        assert rendered.index("Metric health") < rendered.index("Transformer inventory")

    def test_inventory_reuses_responsive_distinct_status_axes(self):
        _assert_table_axes(plant_detail.layout("Itaipu"), "transformers-table")


class TestTransformerHierarchy:
    def test_preserves_identity_and_parent_breadcrumb(self):
        layout = transformer_detail.layout("Itaipu", "ta01", "p1")
        assert "ta01" in text_of(layout)
        assert ("Fleet", "/plants") in links(layout)
        assert ("Itaipu", "/plants/p1") in links(layout)

    def test_groups_summary_before_metric_detail_and_inventory(self):
        layout = transformer_detail.layout("Itaipu", "ta01", "p1")
        _assert_common_hierarchy(
            layout,
            context_id="transformer-context",
            kpis_id="transformer-kpis",
            metric_id="transformer-metric-health",
            attribution_id="transformer-attribution",
        )
        rendered = text_of(layout)
        assert rendered.index("Operational summary") < rendered.index("Metric health")
        assert rendered.index("Metric health") < rendered.index("RTL inventory")

    def test_inventory_reuses_responsive_distinct_status_axes(self):
        _assert_table_axes(transformer_detail.layout("Itaipu", "ta01", "p1"), "devices-table")
