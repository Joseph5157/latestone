"""COLOUR-KEY-1 (ADR-026): one colour key for the whole dashboard."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from components import status_colors as sc
from services.attention_service import ProblemKind
from services.temperature_condition_service import TemperatureCondition

CSS = re.sub(r"/\*.*?\*/", "", (Path(__file__).resolve().parent.parent / "assets" / "app.css")
             .read_text(encoding="utf-8"), flags=re.S)
KEY_TONES = {tone for tone, *_ in sc.COLOUR_KEY}


def _walk(node):
    yield node
    children = getattr(node, "children", None)
    for child in children if isinstance(children, (list, tuple)) else ([children] if children is not None else []):
        yield from _walk(child)


def _text(node):
    return " ".join(str(n) for n in _walk(node) if isinstance(n, str))


def test_the_key_has_the_six_levels_in_order():
    assert [t for t, *_ in sc.COLOUR_KEY] == ["critical", "warning", "nodata", "info", "normal", "none"]


def test_every_condition_and_kind_has_a_tone_in_the_key():
    assert set(sc.CONDITION_TONE) == set(TemperatureCondition)
    assert set(sc.KIND_TONE) == set(ProblemKind)
    assert set(sc.CONDITION_TONE.values()) | set(sc.KIND_TONE.values()) <= KEY_TONES


def test_limits_not_set_is_not_the_device_fault_colour():
    assert sc.CONDITION_TONE[TemperatureCondition.LIMITS_NOT_SET] == "none"
    assert sc.KIND_TONE[ProblemKind.SENSOR_ERROR] == "info"


@pytest.mark.parametrize("tone", sorted(KEY_TONES))
def test_every_tone_has_a_token_in_light_and_dark(tone):
    token = sc.TONE_TOKEN[tone]
    assert re.search(rf":root\s*\{{[^}}]*{re.escape(token)}\s*:", CSS)
    dark = re.search(r"\.app-root\.theme--dark:not\(:has\(\.login-page\)\)\s*\{(.*?)\}", CSS, flags=re.S).group(1)
    assert f"{token}:" in dark
    assert f".status-chip--{tone}" in CSS


def test_status_colours_are_never_literals():
    for m in re.finditer(r"(status-chip|condition__seg|legend|strip__seg|meter__fill|trend__seg)--[a-z]+[^{]*\{([^}]*)\}", CSS):
        assert not re.search(r"#[0-9a-fA-F]{3,6}\b", m.group(2)), m.group(0)[:80]


def test_the_colour_key_names_every_level_and_says_blue_is_selection():
    text = _text(sc.colour_key())
    for _tone, name, _meaning, _covers in sc.COLOUR_KEY:
        assert name in text
    assert "Blue" in text and "never a status" in text


def test_the_real_fleet_overview_uses_no_status_colours_so_shows_no_key():
    """SATURDAY-REAL-FLEET-01: factual rows only, no Normal/Warning/Critical rating."""
    from pages import plants_overview
    assert not any(getattr(n, "className", "") == "colour-key" for n in _walk(plants_overview.layout()))


@pytest.mark.parametrize("tone", ["critical", "warning", "nodata", "info"])
def test_every_problem_tone_colours_text_on_its_token(tone):
    rule = re.search(rf"\.status-text--{tone}\s*\{{([^}}]*)\}}", CSS)
    assert rule and f"color: var({sc.TONE_TOKEN[tone]})" in rule.group(1)


@pytest.mark.parametrize("tone", ["critical", "warning", "nodata", "info"])
def test_tone_colours_read_as_text_in_light(tone):
    root = re.search(r":root\s*\{(.*?)\}", CSS, flags=re.S).group(1)
    colour = re.search(rf"{sc.TONE_TOKEN[tone]}:\s*(#[0-9a-fA-F]{{6}})", root).group(1)
    from tests.test_app_theme import _contrast
    assert _contrast(colour, "#ffffff") >= 4.5 and _contrast(colour, "#f4f6f8") >= 4.5


def test_the_dot_is_gone():
    assert not hasattr(sc, "status_dot") and ".status-dot" not in CSS
