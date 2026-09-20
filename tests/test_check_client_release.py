"""The delivery guard must refuse everything docs/CLIENT_DELIVERY.md forbids.

The guard is the only mechanical control on a hand-curated delivery, so a
rule that lives in the document but not in the code is not a rule at all.
CLIENT-SYNC-5 found 33 such files: `docs/RTL_*`, `docs/UX_ACCEPTANCE_*`,
`docs/ux-baseline/**` and `docs/wireframes/**` were all named in the
document and all passed the guard clean.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from check_client_release import violations  # noqa: E402


class TestInternalMaterialIsRefused:
    def test_rtl_working_documents_are_refused(self):
        """Our notes on the client's own specification are not deliverables.

        RTL_FUNCTIONAL_SPEC_EXTRACT is text taken out of the client's PAD,
        and RTL_CLIENT_TECHNICAL_INPUT_REQUIRED is the list of things we do
        not know about their system. Both read as project material.
        """
        assert violations(["docs/RTL_FUNCTIONAL_SPEC_EXTRACT.md"])
        assert violations(["docs/RTL_CLIENT_TECHNICAL_INPUT_REQUIRED.md"])
        assert violations(["docs/RTL_FRONTEND_CURRENT_STATUS.md"])
        # Lowercase spelling exists on main too, so the rule cannot be
        # case-sensitive.
        assert violations(["docs/rtl_current_route_inventory.md"])
        assert violations(["docs/rtl_frontend_scope_guard.md"])

    def test_internal_acceptance_and_audit_records_are_refused(self):
        assert violations(["docs/UX_ACCEPTANCE_LOGIN.md"])
        assert violations(["docs/UX_ACCEPTANCE_DEVICE_ANALYTICS.md"])
        assert violations(["docs/PAD_SECTIONS_1_TO_3_4_AUDIT.md"])
        assert violations(["docs/CLIENT_FEEDBACK_IMPLEMENTATION_AUDIT.md"])

    def test_internal_design_artefacts_are_refused(self):
        assert violations(["docs/ux-baseline/baseline-login-1366.png"])
        assert violations(["docs/wireframes/01-login.html"])
        assert violations(["docs/wireframes/wireframe.css"])

    def test_tests_of_undelivered_tooling_are_refused(self):
        """A delivered test may not exercise material that is never delivered.

        scripts/build_context_pack.py is internal, so its tests cannot run on
        the client tree — they would fail on a clean clone.
        """
        assert violations(["tests/test_build_context_pack_check.py"])
        assert violations(["tests/test_context_pack_gate_guard.py"])

    def test_previously_covered_rules_still_hold(self):
        assert violations(["AGENTS.md"])
        assert violations(["docs/context/ACTIVE_GATE.md"])
        assert violations(["docs/decisions/ADR-001-event-classification-no-thresholds.md"])
        assert violations(["command center/00_README.md"])
        assert violations([".env"])
        assert violations(["debug.log"])


class TestDeliverableMaterialIsAllowed:
    def test_application_source_passes(self):
        assert violations(
            [
                "app.py",
                "pages/command_center.py",
                "components/attention.py",
                "services/fleet_overview_service.py",
                "alembic/versions/015_freshness_threshold_config.py",
                "assets/command_center.js",
            ]
        ) == []

    def test_client_facing_documents_pass(self):
        """The guard must not become so broad it eats the delivery itself."""
        assert violations(
            [
                "README.md",
                "docs/GETTING_STARTED.md",
                "docs/SYSTEM_OVERVIEW.md",
                "docs/USER_ROLES_AND_PERMISSIONS.md",
                "docs/FEATURES_AND_WORKFLOWS.md",
                "docs/DATA_AND_SYSTEM_BEHAVIOUR.md",
                "docs/DEMO_WALKTHROUGH.md",
                ".env.example",
            ]
        ) == []

    def test_ordinary_tests_pass(self):
        assert violations(
            ["tests/test_attention_service.py", "tests/test_br016_ownership.py"]
        ) == []
