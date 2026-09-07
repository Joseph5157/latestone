"""Vibration contract question registry (VIB-CONFIG-1 / C-02, framework only).

Single source of truth for WHICH questions exist — transcribed verbatim
from `docs/VIBRATION_METRIC_CONTRACT_TBD.md`'s "Unknown / Required from
Client/Backend" table (15 rows, confirmed by direct count 2026-09-07; a
prior tracked-context claim of 14 was itself a miscount, corrected
alongside this gate). This module invents no answer to any of them — it
only names the SLOTS an Administrator may later fill in, exactly as the
TBD document already states them. Nothing here implies a unit, an axis
model, an aggregation type, or any other vibration semantic; `key` is a
stable identifier for a slot, not evidence about what the slot's eventual
value will look like.

Deliberately a plain tuple + lookup, not a database ENUM or migration
CHECK constraint on question_key — mirrors `config/audit.py`'s own
precedent (the audit_log.operation column has no CHECK either, "this
module is the application-side source of truth"). If a 16th question is
ever confirmed, it is added here; no migration is needed, because the
persistence layer (`vibration_contract_answers`) is a genuine key-value
table, not one column per question.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VibrationContractQuestion:
    key: str
    question: str
    why_it_matters: str


VIBRATION_CONTRACT_QUESTIONS: tuple[VibrationContractQuestion, ...] = (
    VibrationContractQuestion(
        "metric_key", "What is the metric key?",
        "Must match database column/API field",
    ),
    VibrationContractQuestion(
        "operator_label", "What is the operator-facing label?",
        "UI display name",
    ),
    VibrationContractQuestion(
        "unit", "What is the unit?",
        "mm/s, m/s², in/s, g, µm, etc.",
    ),
    VibrationContractQuestion(
        "precision", "What precision is needed?",
        "Decimal places for display",
    ),
    VibrationContractQuestion(
        "aggregation_type", "Is it instantaneous or cumulative?",
        "Determines STATISTICS vs DELTA aggregation",
    ),
    VibrationContractQuestion(
        "chart_type", "What is the chart type?",
        "Line, bar, or something else?",
    ),
    VibrationContractQuestion(
        "sampling_cadence", "What is the sampling cadence?",
        "Freshness policy alignment",
    ),
    VibrationContractQuestion(
        "source_resolution", "What is the source resolution?",
        "Chart binning and energy-like metrics",
    ),
    VibrationContractQuestion(
        "sensor_range", "Is there a valid sensor range?",
        "Future threshold support",
    ),
    VibrationContractQuestion(
        "thresholds_exist", "Do thresholds exist?",
        "Warning/critical states",
    ),
    VibrationContractQuestion(
        "axes", "Are there multiple axes?",
        "X/Y/Z or single combined value?",
    ),
    VibrationContractQuestion(
        "continuous_or_event", "Is this continuous data or event data?",
        "Storage and display model",
    ),
    VibrationContractQuestion(
        "value_representation", "What does the value represent?",
        "Displacement, velocity, acceleration, RMS, peak?",
    ),
    VibrationContractQuestion(
        "storage_model", "How is it stored in the database?",
        "Column name, table, schema",
    ),
    VibrationContractQuestion(
        "api_access", "How is it accessed via API?",
        "Endpoint, query pattern",
    ),
)

_BY_KEY: dict[str, VibrationContractQuestion] = {
    q.key: q for q in VIBRATION_CONTRACT_QUESTIONS
}


def get_question(key: str) -> VibrationContractQuestion | None:
    """Look up one question by its stable key, or None if unknown."""
    return _BY_KEY.get(key)


def is_known_question_key(key: str) -> bool:
    return key in _BY_KEY


def question_keys() -> tuple[str, ...]:
    """Ordered tuple of all confirmed question keys."""
    return tuple(q.key for q in VIBRATION_CONTRACT_QUESTIONS)
