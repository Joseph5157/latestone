"""
Administration demo seed — synthetic technicians and RTL assignments.

DEVELOPMENT / DEMO DATA. Everything this module creates is invented. The
technicians are not real people, the assignments describe no real duty roster,
and none of it comes from the client. It exists so the Administrator screens
(assignment coverage, the unassigned-RTL exception list) can be demonstrated
against representative state instead of an empty fleet.

DELIBERATELY SEPARATE FROM THE MONITORING SEED, and opt-in:

    python -m db.seed_plant_monitoring --reset    plants/transformers/devices/readings
    python -m db.seed_admin_demo --reset          technicians/assignments

`seed_plant_monitoring` must never create users or assignments as a side
effect. The monitoring seed describes equipment, which is a claim about what
exists; this one describes people and responsibilities, which is a claim about
an organisation. Conflating them would mean any developer refreshing readings
silently acquired a staff list.

NEVER RUN THIS AGAINST PRODUCTION. It writes to `users` and
`user_device_assignments`, and `--reset` deletes rows.

CONTAINMENT. This module only ever touches identities it owns, defined by
`DEMO_TECHNICIANS` below and recognised by their reserved `.invalid` email
address. A username collision with a real account is refused outright rather
than overwritten (`DemoSeedRefused`), `--reset` removes only demo users and
only assignments those users hold, and a device already assigned outside this
seed keeps the technician it has.

NO WORKLOAD MODEL IS IMPLIED. Technician loads are uneven only because an
evenly divided fleet looks synthetic. There is no scoring, no territory, no
skills matrix and no availability concept here — none of those are confirmed
client concepts, and nothing downstream should infer them from these numbers.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from dataclasses import dataclass

from repositories import plant_monitoring_repository as repo

#: How many of the 120 Managed RTLs carry a technician. Chosen so the
#: Administrator dashboard visibly has work to do: 24 unassigned is enough to
#: populate an exception list and demonstrate the assignment workflow, while
#: 80% coverage still reads as a fleet that is largely managed. A DEVELOPMENT
#: VALUE — no client target for assignment coverage exists.
ASSIGNED_DEVICE_COUNT = 96

#: Per-technician share of ASSIGNED_DEVICE_COUNT, in `DEMO_TECHNICIANS` order.
#: Uneven on purpose (see the module docstring): 19/19/19/19/20 would read as
#: generated. Must sum to ASSIGNED_DEVICE_COUNT; a test pins that.
TECHNICIAN_LOAD = (24, 22, 20, 16, 14)

#: Salt for the device-selection hash. Load-bearing: `db.generators` derives
#: registration dates from an UNSALTED hash of the same device_id, so an
#: unsalted hash here would rank devices in the same order and make the
#: unassigned RTLs exactly the oldest ones on record — a pattern nobody
#: designed, showing up in ADMIN-3's exception table as if it meant something.
_ASSIGNMENT_SALT = b"admin-demo-assignment:"


@dataclass(frozen=True)
class DemoTechnician:
    """One synthetic technician identity.

    `email_address` doubles as the ownership marker: it is what
    `_claim_demo_user` checks before touching an existing row, so the seed can
    tell "my row from a previous run" apart from "somebody else's account that
    happens to share this username".
    """

    username: str
    full_name: str
    email_address: str
    role: str = "technician"
    status: str = "active"


#: The five identities this seed owns. Obviously synthetic by construction:
#: `demo.` usernames, `Demo Technician N` names, and `.invalid` addresses
#: (RFC 2606 reserves that TLD, so they can never route anywhere). No client
#: person's name appears in development data.
DEMO_TECHNICIANS: tuple[DemoTechnician, ...] = tuple(
    DemoTechnician(
        username=f"demo.tech{n:02d}",
        full_name=f"Demo Technician {n:02d}",
        email_address=f"demo.tech{n:02d}@example.invalid",
    )
    for n in range(1, 6)
)


class DemoSeedRefused(RuntimeError):
    """Raised instead of overwriting a user this seed does not own."""


@dataclass(frozen=True)
class AdminDemoSummary:
    """What the seed actually put in the database, read back afterwards."""

    total_devices: int
    assigned_devices: int
    unassigned_devices: int
    active_technicians: int


def demo_usernames() -> tuple[str, ...]:
    """The usernames this seed owns, in `DEMO_TECHNICIANS` order."""
    return tuple(t.username for t in DEMO_TECHNICIANS)


def _assignment_key(device_id: str) -> int:
    """Stable per-device rank, independent of the registration-date hash."""
    digest = hashlib.sha256(_ASSIGNMENT_SALT + device_id.encode("utf-8"))
    return int(digest.hexdigest()[:12], 16)


def assignment_plan(device_ids) -> tuple[tuple[str, str], ...]:
    """[(device_id, technician_username)] for the devices that get a technician.

    Pure and deterministic: same devices in, same plan out, regardless of the
    order they arrive in. That is what makes a demo reproducible — a reset and
    reseed must not silently reshuffle who owns what between two screenshots.

    Devices are ranked by a salted hash and the first `ASSIGNED_DEVICE_COUNT`
    are assigned, so the unassigned remainder is scattered across the fleet
    rather than being a contiguous alphabetical tail. `device_id` breaks hash
    ties so the ordering is total.

    Fewer devices than the plan expects (a partially seeded database) assigns
    every device it was given rather than raising, and the per-technician
    shares shrink in `TECHNICIAN_LOAD` order.
    """
    ranked = sorted(device_ids, key=lambda d: (_assignment_key(d), d))
    chosen = ranked[:ASSIGNED_DEVICE_COUNT]

    plan: list[tuple[str, str]] = []
    position = 0
    for technician, load in zip(DEMO_TECHNICIANS, TECHNICIAN_LOAD):
        share = chosen[position : position + load]
        plan.extend((device_id, technician.username) for device_id in share)
        position += load

    # Any remainder from a TECHNICIAN_LOAD that no longer sums to
    # ASSIGNED_DEVICE_COUNT would be silently dropped; a test pins the sum, but
    # spreading leftovers keeps this honest if that ever changes.
    for offset, device_id in enumerate(chosen[position:]):
        plan.append((device_id, DEMO_TECHNICIANS[offset % len(DEMO_TECHNICIANS)].username))

    return tuple(plan)


def _claim_demo_user(technician: DemoTechnician) -> None:
    """Create this identity, or adopt the row a previous run left behind.

    Refuses if the username exists but does not look like this seed's own work.
    The check is the reserved `.invalid` address rather than the display name,
    because an administrator editing a demo technician's name through the UI
    should not turn a later reseed into a refusal — but a genuine account that
    happens to be called `demo.tech01` must never be quietly overwritten.
    """
    existing = repo.get_user_by_username(technician.username)
    if existing is not None and existing.email_address != technician.email_address:
        raise DemoSeedRefused(
            f"User {technician.username!r} already exists and was not created by "
            f"this seed (expected {technician.email_address!r}, found "
            f"{existing.email_address!r}). Refusing to overwrite it. Rename or "
            f"remove that account first if the demo identity is really wanted."
        )
    repo.create_or_update_user(
        username=technician.username,
        full_name=technician.full_name,
        role=technician.role,
        status=technician.status,
        email_address=technician.email_address,
    )


def reset_demo_data() -> None:
    """Remove this seed's assignments and technicians. Nothing else.

    Assignments go first: `users.user_id` is referenced by
    `user_device_assignments`, and no ON DELETE CASCADE exists. Both steps are
    scoped to `demo_usernames()`, so real users, real assignments and any
    history belonging to them survive untouched.

    Safe to run when nothing was ever seeded.
    """
    repo.delete_assignments_for_usernames(demo_usernames())
    for username in demo_usernames():
        repo.delete_user_by_username(username)


def seed_admin_demo() -> AdminDemoSummary:
    """Create the demo technicians and assign RTLs to them. Idempotent.

    Every identity is claimed BEFORE any device is assigned, so a refusal
    leaves the fleet exactly as it was rather than half-assigned to whichever
    technicians happened to be claimed first.

    Assignment goes through `repo.assign_device_to_user`, not ad-hoc SQL: that
    is where role validation, the `FOR UPDATE` lock and the one-active-
    assignment-per-device rule already live, and it leaves an unchanged
    assignment alone instead of closing and reopening it — which is what makes
    re-running this write no history.

    A device already assigned outside this seed is skipped, not stolen. The
    plan describes which RTLs this seed would like to own; an existing
    assignment is somebody else's decision and outranks it.
    """
    for technician in DEMO_TECHNICIANS:
        _claim_demo_user(technician)

    device_ids = [d.device_id for d in repo.list_all_devices()]
    owned = set(demo_usernames())

    for device_id, username in assignment_plan(device_ids):
        current = repo.get_active_device_assignment(device_id)
        if current is not None and current.username not in owned:
            continue
        repo.assign_device_to_user(device_id=device_id, technician_username=username)

    counts = repo.count_device_assignments()
    return AdminDemoSummary(
        total_devices=counts.total_devices,
        assigned_devices=counts.assigned_devices,
        unassigned_devices=counts.unassigned_devices,
        active_technicians=repo.count_active_technicians(),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Seed synthetic technicians and RTL assignments for demonstrating "
            "the Administrator screens. Development data only — never run "
            "against production."
        )
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help=(
            "Remove this seed's technicians and their assignments first. Only "
            "demo-owned rows are deleted; other users and assignments are left "
            "alone."
        ),
    )
    args = parser.parse_args(argv)

    print("Administration demo seed — DEVELOPMENT DATA ONLY")
    print(f"Schema: {repo._SCHEMA}")

    if args.reset:
        print("\nRemoving previous demo technicians and their assignments...")
        reset_demo_data()
        print("  Reset complete.")

    print("\nSeeding demo technicians and assignments...")
    try:
        summary = seed_admin_demo()
    except DemoSeedRefused as exc:
        print(f"\nRefused: {exc}", file=sys.stderr)
        return 1

    coverage = (
        summary.assigned_devices / summary.total_devices * 100
        if summary.total_devices
        else 0.0
    )
    print("\nDone.\n")
    print(f"  Managed RTLs        {summary.total_devices}")
    print(f"  Assigned RTLs       {summary.assigned_devices}")
    print(f"  Unassigned RTLs     {summary.unassigned_devices}")
    print(f"  Active Technicians  {summary.active_technicians}")
    print(f"  Assignment Coverage {coverage:.0f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
