"""Controlled bootstrap of the legacy Technician assignments (ADR-032).

Run from the repository root:

    python -m scripts.bootstrap_rtl_assignments                      # PREVIEW only
    python -m scripts.bootstrap_rtl_assignments --apply              # import (needs no provisioning)
    python -m scripts.bootstrap_rtl_assignments --apply --provision-technicians

The default is a read-only preview: it prints the candidate assignments, the
excluded historical/unregistered UIDs and every blocking problem, and writes
nothing. ``--apply`` re-derives the plan and imports it in one transaction; it
refuses if any problem exists (conflicts are never resolved automatically).
Re-running is idempotent.

It reads the client SQL Server (SELECT only) and writes ONLY the
application-owned PostgreSQL assignment store. It is never run at start-up.
"""
from __future__ import annotations

import argparse
import sys

from services import rtl_assignment_bootstrap as bootstrap


def render_preview(plan: bootstrap.BootstrapPlan) -> str:
    lines = [
        "Legacy Technician assignment bootstrap - PREVIEW",
        f"  candidate current assignments to import : {len(plan.candidates)}",
        f"  already present (same Technician)       : {len(plan.already_present)}",
        f"  skipped (assignment history exists)     : {len(plan.skipped_has_history)}",
        f"  excluded historical/unregistered UIDs   : {len(plan.excluded_unregistered)}",
        f"  Technician persons needing an app user  : {len(plan.needs_provisioning)}",
        f"  blocking problems                       : {len(plan.problems)}",
        "",
        "Candidates (UID -> client person id, name):",
    ]
    lines += [f"  {c.device_uid}\t{c.person_id}\t{c.person_name}" for c in plan.candidates]
    lines += ["", "Excluded (not currently registered; NOT imported):"]
    lines += [f"  {r.device_uid}\t{r.full_name}" for r in plan.excluded_unregistered]
    if plan.needs_provisioning:
        lines += ["", "Technician persons with no application user:"]
        lines += [f"  {p.person_id}\t{p.full_name}" for p in plan.needs_provisioning]
    if plan.problems:
        lines += ["", "BLOCKING PROBLEMS:"] + [f"  - {p}" for p in plan.problems]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true", help="import after the preview passes")
    parser.add_argument("--provision-technicians", action="store_true",
                        help="create login-less application users for unmapped Technician persons")
    args = parser.parse_args(argv)

    plan = bootstrap.build_plan()
    print(render_preview(plan))
    if not plan.ok:
        print("\nSTOP: blocking problems exist. Nothing was imported.")
        return 1
    if not args.apply:
        print("\nPreview only. Re-run with --apply to import.")
        return 0
    try:
        result = bootstrap.apply_plan(plan, provision=args.provision_technicians)
    except bootstrap.BootstrapRefused as exc:
        print(f"\nREFUSED: {exc}")
        return 1
    print(f"\nImported {result['imported']} assignment(s); "
          f"created {result['provisioned_users']} login-less Technician user(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
