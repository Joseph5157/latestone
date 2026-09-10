"""CTX-GUARD-1: the `Gate:` header must agree with the queued-gate declaration.

`ACTIVE_GATE.md` carries the current gate twice — once as the `Gate:` field in
the header block, and once as an explicit `## Next implementation gate: <NAME>`
section further down. Only the header is machine-read: `parse_fields()` stops
at the first markdown heading, so every gate appended below it is invisible to
the pack. That is exactly how the header sat on `C08-BASELINE-1` for ten gates
while the file's own declaration said otherwise, and a green `--check` said
nothing, because no check compared the two.

These tests pin the comparison. A declaration naming a gate that has already
closed elsewhere in the file is historical and ignored — that rule is what lets
superseded `## Next implementation gate:` sections stay in the file untouched,
which they must, since they are the record of how the project got here.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "build_context_pack.py"
REAL_ACTIVE_GATE = ROOT / "docs" / "context" / "ACTIVE_GATE.md"


def _load_module():
    """Import the script by path. `scripts/` is not a package."""
    spec = importlib.util.spec_from_file_location("build_context_pack", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["build_context_pack"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def pack():
    return _load_module()


def gate_doc(header_gate: str, *sections: str) -> str:
    """A minimal ACTIVE_GATE.md: the header block, then the given sections."""
    return "\n".join(
        [
            "# Active Gate",
            "",
            "Status: **QUEUED / NOT STARTED**",
            "Date: 2026-09-10",
            f"Gate: {header_gate}",
            "",
            *sections,
        ]
    ) + "\n"


# ---------------------------------------------------------------------------
# gate_identifier: the name is the part before the em dash
# ---------------------------------------------------------------------------

def test_gate_identifier_takes_the_name_before_the_em_dash(pack):
    assert pack.gate_identifier("CLIENT-PC-SYNC-2 — update the client laptop") == "CLIENT-PC-SYNC-2"


def test_gate_identifier_survives_a_soft_wrapped_header_value(pack):
    """`parse_fields` folds continuation lines, so the value arrives multi-line."""
    folded = "CLIENT-PC-SYNC-2 — update the client laptop to the delivered\nmilestone, and browser-smoke"
    assert pack.gate_identifier(folded) == "CLIENT-PC-SYNC-2"


def test_gate_identifier_handles_a_name_with_no_description(pack):
    assert pack.gate_identifier("CTX-GUARD-1") == "CTX-GUARD-1"


# ---------------------------------------------------------------------------
# The agreement check
# ---------------------------------------------------------------------------

def test_agreement_reports_no_problem(pack):
    text = gate_doc(
        "CLIENT-PC-SYNC-2 — update the client laptop",
        "## Next implementation gate: CLIENT-PC-SYNC-2 — QUEUED, NOT STARTED",
        "",
        "Scope: update the laptop.",
    )
    assert pack.check_gate_agreement(text) == []


def test_disagreement_is_a_problem_naming_both_sides(pack):
    """The exact drift that went unnoticed for ten gates."""
    text = gate_doc(
        "C08-BASELINE-1 — Record development baselines",
        "## Next implementation gate: CLIENT-PC-SYNC-2 — QUEUED, NOT STARTED",
        "",
        "Scope: update the laptop.",
    )
    problems = pack.check_gate_agreement(text)

    assert len(problems) == 1
    assert "C08-BASELINE-1" in problems[0]
    assert "CLIENT-PC-SYNC-2" in problems[0]


def test_a_declaration_for_an_already_closed_gate_is_ignored(pack):
    """Superseded declarations stay in the file; they must not fail the build."""
    text = gate_doc(
        "CLIENT-PC-SYNC-2 — update the client laptop",
        "## LOCAL-DB-CATCHUP-1 — COMPLETED / VERIFIED",
        "",
        "Done on 2026-09-07.",
        "",
        "## Next implementation gate: CLIENT-PC-SYNC-2 — QUEUED, NOT STARTED",
        "",
        "Scope: update the laptop.",
        "",
        "## Next implementation gate: LOCAL-DB-CATCHUP-1 — QUEUED, NOT STARTED",
        "",
        "Historical: this gate has since closed.",
    )
    assert pack.check_gate_agreement(text) == []


def test_a_closed_gate_is_recognised_by_CLOSED_as_well_as_COMPLETED(pack):
    text = gate_doc(
        "CTX-GUARD-1 — add the guard",
        "## RTL-PROG-SIM-1 — CLOSED / PUSHED / REMOTE-VERIFIED",
        "",
        "Done.",
        "",
        "## Next implementation gate: CTX-GUARD-1 — QUEUED, NOT STARTED",
        "",
        "## Next implementation gate: RTL-PROG-SIM-1 — QUEUED, NOT STARTED",
    )
    assert pack.check_gate_agreement(text) == []


def test_no_declaration_at_all_is_a_problem(pack):
    """Silence must not read as agreement — that is how the drift hid."""
    text = gate_doc("CLIENT-PC-SYNC-2 — update the client laptop", "## Some other section", "", "Prose.")
    problems = pack.check_gate_agreement(text)

    assert len(problems) == 1
    assert "Next implementation gate" in problems[0]


def test_two_open_declarations_are_a_problem(pack):
    """Ambiguity is reported, never silently resolved by picking one."""
    text = gate_doc(
        "CTX-GUARD-1 — add the guard",
        "## Next implementation gate: CTX-GUARD-1 — QUEUED, NOT STARTED",
        "",
        "## Next implementation gate: SOMETHING-ELSE-1 — QUEUED, NOT STARTED",
    )
    problems = pack.check_gate_agreement(text)

    assert len(problems) == 1
    assert "CTX-GUARD-1" in problems[0]
    assert "SOMETHING-ELSE-1" in problems[0]


def test_a_missing_header_gate_field_is_a_problem(pack):
    text = "\n".join(
        [
            "# Active Gate",
            "",
            "Status: **QUEUED / NOT STARTED**",
            "",
            "## Next implementation gate: CTX-GUARD-1 — QUEUED, NOT STARTED",
        ]
    ) + "\n"
    problems = pack.check_gate_agreement(text)

    assert len(problems) == 1
    assert "Gate:" in problems[0]


# ---------------------------------------------------------------------------
# Wiring: the check must actually reach --check's exit code
# ---------------------------------------------------------------------------

def test_check_fails_when_the_header_disagrees(pack, tmp_path, monkeypatch, capsys):
    """The guard is worthless if it is computed and not returned."""
    drifted = tmp_path / "ACTIVE_GATE.md"
    drifted.write_text(
        gate_doc(
            "C08-BASELINE-1 — Record development baselines",
            "## Next implementation gate: CLIENT-PC-SYNC-2 — QUEUED, NOT STARTED",
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(pack, "ACTIVE_GATE", drifted)

    exit_code = pack.main(["--check", "--skip-tests"])
    out = capsys.readouterr().out

    assert exit_code == 1
    assert "PROBLEM:" in out
    assert "C08-BASELINE-1" in out


def test_the_real_active_gate_agrees_with_its_own_declaration(pack):
    """Regression anchor: this repository's own file must satisfy the guard."""
    assert pack.check_gate_agreement(REAL_ACTIVE_GATE.read_text(encoding="utf-8")) == []
