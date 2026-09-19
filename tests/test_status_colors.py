"""COLOUR-KEY-1 (ADR-026): one colour key for the whole dashboard."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from components import attention, fleet_overview, status_colors as sc
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


@pytest.mark.parametrize("condition", list(TemperatureCondition))
def test_a_condition_looks_the_same_on_both_pages(condition):
    fo = fleet_overview.condition_chip(condition).className
    cc = attention.condition_chip(condition).className
    tone_class = f"status-chip--{sc.CONDITION_TONE[condition]}"
    assert tone_class in fo.split() and tone_class in cc.split()


def test_limits_not_set_is_not_the_device_fault_colour():
    assert sc.CONDITION_TONE[TemperatureCondition.LIMITS_NOT_SET] == "none"
    assert sc.KIND_TONE[ProblemKind.SENSOR_ERROR] == "info"


def test_the_pages_keep_no_tone_table_of_their_own():
    for module in (attention, fleet_overview):
        src = Path(module.__file__).read_text(encoding="utf-8")
        assert "_KIND_TONE = {" not in src and "_CONDITION_TONE = {" not in src and "_TONE = {" not in src


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


def test_both_pages_show_the_key():
    from pages import command_center, plants_overview
    for page in (plants_overview, command_center):
        assert any(getattr(n, "className", "") == "colour-key" for n in _walk(page.layout())), page


def test_the_command_center_names_the_fault_card_device_fault():
    assert ("Device fault", "info") in attention.SEVERITY_COUNTERS


def test_the_alarm_legend_names_the_level_before_the_alarm():
    from datetime import date
    from services.attention_service import DailyAlarms
    days = [DailyAlarms(day=date(2026, 9, 19), count=2,
                        by_kind=((ProblemKind.POWER_DOWN, 1), (ProblemKind.BATTERY_LOW, 1)))]
    text = _text(attention.alarm_trend_card(days))
    assert "Critical · Power Down" in text and "Warning · Battery Low" in text


def test_the_hottest_card_is_not_painted_as_a_selection():
    from inspect import getsource
    assert "accent=True" not in getsource(fleet_overview.stat_cards)


@pytest.mark.parametrize("tone", sorted(KEY_TONES))
def test_every_tone_has_a_dot_on_its_token(tone):
    rule = re.search(rf"\.status-dot--{tone}\s*\{{([^}}]*)\}}", CSS)
    assert rule and f"var({sc.TONE_TOKEN[tone]})" in rule.group(1)


def test_the_dot_is_decorative():
    dot = sc.status_dot("critical")
    assert dot.className == "status-dot status-dot--critical"
    assert getattr(dot, "aria-hidden") == "true"
