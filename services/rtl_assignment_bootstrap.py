"""One-time, explicit bootstrap of the legacy Technician assignments (ADR-032).

Adopts the client's legacy ``techmician_device_list`` snapshot - transitional
POSITIVE evidence, never an authoritative source - into the application-owned
assignment store, for currently REGISTERED RTLs only. It is a command, never
run at application start-up, and it has two phases:

* ``build_plan`` - a pure-read PREVIEW: what would be imported, what is
  excluded, and every blocking problem. Writes nothing.
* ``apply_plan`` - runs only from a plan with no problems, in one transaction,
  and is idempotent: a UID that already has ANY assignment row (open or ended)
  is skipped, so a rerun never duplicates and never resurrects an assignment an
  Administrator has since ended or moved.

Identity: a legacy name is matched EXACTLY (no case-folding, no trimming, no
fuzzy match) to one client ``persons`` row whose role is Technician; the person
is then resolved to an application user through ``users.client_person_id``.
A Technician person with no application user is reported, and only created (as
a login-less user - no credential exists, so it grants no sign-in) when
``provision`` is explicitly requested.

Imported rows carry provenance LEGACY_IMPORT, no assigned_at and no
assigned_by: the original date and actor are unknown and are not invented. The
import time is stored separately as ``imported_at``.

Conflicts are never resolved automatically: if a candidate UID already has an
open assignment to a DIFFERENT Technician, the plan is blocked.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from db.engine import session_scope
from repositories import plant_monitoring_repository as repo
from repositories.rtl_assignment_source_repository import (
    ClientPerson,
    LegacyAssignmentRow,
    RTLAssignmentSourceRepository,
)
from repositories.rtl_temperature_repository import RTLTemperatureRepository

USERNAME_PREFIX = "client-person-"


@dataclass(frozen=True)
class Candidate:
    device_uid: int
    person_id: int
    person_name: str
    user_id: int | None  # None until provisioned


@dataclass
class BootstrapPlan:
    candidates: list[Candidate] = field(default_factory=list)  # to import
    excluded_unregistered: list[LegacyAssignmentRow] = field(default_factory=list)
    already_present: list[int] = field(default_factory=list)  # open row, same Technician
    skipped_has_history: list[int] = field(default_factory=list)  # ended earlier: not resurrected
    needs_provisioning: list[ClientPerson] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)  # blocking; import must not run

    @property
    def ok(self) -> bool:
        return not self.problems


def _registered() -> set[int]:
    return set(RTLTemperatureRepository().get_registered_device_uids())


def build_plan(
    *,
    source: RTLAssignmentSourceRepository | None = None,
    registered_fetch=_registered,
    user_ids_by_person=repo.list_user_ids_by_client_person_id,
    assignment_state=repo.list_rtl_assignment_uid_state,
    current_assignments=repo.list_current_rtl_assignments,
) -> BootstrapPlan:
    """The read-only preview. Every check that can stop the import is here."""
    source = source or RTLAssignmentSourceRepository()
    plan = BootstrapPlan()
    legacy = source.get_legacy_assignments()
    technicians = source.get_technician_persons()
    everyone = source.get_all_persons()
    registered = registered_fetch()

    tech_by_name: dict[str, list[ClientPerson]] = defaultdict(list)
    for p in technicians:
        tech_by_name[p.full_name].append(p)
    person_names = {p.full_name for p in everyone}

    # 1. Identity: exact name -> exactly one Technician person.
    person_of_name: dict[str, ClientPerson] = {}
    for name in sorted({row.full_name for row in legacy}):
        matches = tech_by_name.get(name, [])
        if len(matches) == 1:
            person_of_name[name] = matches[0]
        elif not matches and name in person_names:
            plan.problems.append(f"Legacy name {name!r} matches a person who is not a Technician.")
        elif not matches:
            plan.problems.append(f"Legacy name {name!r} matches no person.")
        else:
            plan.problems.append(f"Legacy name {name!r} matches {len(matches)} Technician persons.")

    # 2. Data quality: no duplicate pair, no UID with two Technicians.
    seen_pairs: set[tuple[str, int]] = set()
    names_by_uid: dict[int, set[str]] = defaultdict(set)
    for row in legacy:
        pair = (row.full_name, row.device_uid)
        if pair in seen_pairs:
            plan.problems.append(f"Duplicate legacy pair {pair!r}.")
        seen_pairs.add(pair)
        names_by_uid[row.device_uid].add(row.full_name)
    for uid, names in sorted(names_by_uid.items()):
        if len(names) > 1:
            plan.problems.append(f"UID {uid} is legacy-assigned to more than one Technician.")

    # 3. Registered vs historical/unregistered; app identity; existing state.
    users = user_ids_by_person()
    state = assignment_state()
    current = {a.device_uid: a.technician_user_id for a in current_assignments()}
    needs: dict[int, ClientPerson] = {}
    for row in sorted(legacy, key=lambda r: r.device_uid):
        if row.device_uid not in registered:
            plan.excluded_unregistered.append(row)
            continue
        person = person_of_name.get(row.full_name)
        if person is None:
            continue  # already reported as a problem above
        user_id = users.get(person.person_id)
        if user_id is None:
            needs[person.person_id] = person
        if row.device_uid in current:
            if user_id is not None and current[row.device_uid] == user_id:
                plan.already_present.append(row.device_uid)
            else:
                plan.problems.append(
                    f"UID {row.device_uid} already has a current application assignment to a "
                    "different Technician; not overwritten."
                )
            continue
        if row.device_uid in state:  # ended earlier: an Administrator changed it
            plan.skipped_has_history.append(row.device_uid)
            continue
        plan.candidates.append(Candidate(row.device_uid, person.person_id, person.full_name, user_id))
    plan.needs_provisioning = sorted(needs.values(), key=lambda p: p.person_id)
    return plan


class BootstrapRefused(RuntimeError):
    pass


def apply_plan(plan: BootstrapPlan, *, provision: bool = False) -> dict[str, int]:
    """Import ``plan.candidates`` in ONE transaction. Refuses a blocked plan."""
    if not plan.ok:
        raise BootstrapRefused("The preview has blocking problems; nothing was imported.")
    if plan.needs_provisioning and not provision:
        raise BootstrapRefused(
            "Some Technician persons have no application user. Re-run with provisioning "
            "explicitly requested after reviewing the preview."
        )
    imported = provisioned = 0
    with session_scope() as session:
        user_of_person: dict[int, int] = dict(repo.list_user_ids_by_client_person_id())
        for person in plan.needs_provisioning:
            if person.person_id in user_of_person:
                continue
            username = f"{USERNAME_PREFIX}{person.person_id}"
            if repo.username_exists(username, session=session):
                raise BootstrapRefused(f"Username {username!r} is taken by another account.")
            user_of_person[person.person_id] = repo.provision_technician_user_for_person(
                session=session, client_person_id=person.person_id,
                username=username, full_name=person.full_name,
            )
            provisioned += 1
        existing = repo.list_rtl_assignment_uid_state()
        for c in plan.candidates:
            if c.device_uid in existing:
                continue  # raced with another run: never duplicate
            repo.insert_rtl_assignment(
                session=session, device_uid=c.device_uid,
                technician_user_id=user_of_person[c.person_id],
                provenance=repo.PROVENANCE_LEGACY_IMPORT,
            )
            imported += 1
    return {"imported": imported, "provisioned_users": provisioned}
