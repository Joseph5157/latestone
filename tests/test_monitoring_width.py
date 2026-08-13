"""Page-width regression, Phase 5 integration.

Fleet, Plant and Transformer share `page--monitoring` (1550px); Device stays
on the default reading-width `.page` (1200px). One file collects the
assertion for all four so a future change to any one page cannot silently
drift from the others without a test noticing here.
"""
from __future__ import annotations


def test_fleet_uses_the_monitoring_width_class():
    from pages import plants_overview

    assert "page--monitoring" in plants_overview.layout().className


def test_plant_uses_the_monitoring_width_class():
    from pages import plant_detail

    assert "page--monitoring" in plant_detail.layout("Plant").className


def test_transformer_uses_the_monitoring_width_class():
    from pages import transformer_detail

    layout = transformer_detail.layout("Plant", "T1", "p1")
    assert "page--monitoring" in layout.className


def test_device_does_not_use_the_monitoring_width_class():
    """Device stays at the 1200px reading width — not part of this phase."""
    from pages import device_dashboard

    layout = device_dashboard.layout()
    assert "page--monitoring" not in layout.className
