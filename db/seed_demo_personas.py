"""
Login-persona demo seed — the identities the three demo credentials name.

DEVELOPMENT / DEMO DATA. Everything this module creates is invented. It exists
so each confirmed role can be signed into through the ordinary login path
(ROLE-4A), not to describe any real person.

DELIBERATELY SEPARATE FROM THE OTHER TWO SEEDS, and opt-in:

    python -m db.seed_plant_monitoring --reset   plants/transformers/devices/readings
    python -m db.seed_admin_demo --reset         technicians/assignments
    python -m db.seed_demo_personas --reset      login personas

`seed_admin_demo` describes a duty roster: who is responsible for which RTLs.
This one describes who can sign in. They are different claims, and the project
already refuses to conflate seeds that make different claims — see that
module's docstring on why equipment and staffing are not seeded together. Two
concrete reasons keep them apart here:

- `seed_admin_demo.demo_usernames()` is the set of technicians whose device
  assignments that seed owns; it decides which assignments `--reset` deletes
  and which a reseed may take over. A General user has no assignments, and
  putting a non-technician in that set would change what the administration
  seed considers its own — an assignment-semantics change made for a login
  reason, which ROLE-4A must not do.
- The Administrator and Technician personas already exist (from
  `auth_service.seed_demo_user` and `seed_admin_demo` respectively). Only the
  General persona was missing, so this seed's job is deliberately small.

**A CREDENTIAL IS NOT CREATED HERE, AND NO ROLE IS READ FROM ONE.** This module
writes identities; `DEMO_CREDENTIALS` configures logins. The split is the
ROLE-4A decision (ADR-015): seeding a row does not grant anyone a password, and
configuring a password does not grant anyone a role.

CONTAINMENT, the same rule `seed_admin_demo` uses. This module only touches
identities it owns, recognised by their reserved `.invalid` address (RFC 2606,
so it can never route anywhere). A username collision with an account this seed
did not create is refused outright rather than overwritten, and `--reset`
removes only the personas listed below.

NEVER RUN THIS AGAINST PRODUCTION. It writes to `users`, and `--reset` deletes
rows.
"""
from __future__ import annotations

import argparse

from repositories import plant_monitoring_repository as repo


class DemoPersonaRefused(RuntimeError):
    """Raised instead of overwriting a user this seed does not own."""


class DemoPersona:
    """One synthetic login identity.

    `email_address` doubles as the ownership marker, exactly as it does in
    `seed_admin_demo`: it is what `claim_persona` checks before touching an
    existing row, so the seed can tell "my row from a previous run" apart from
    "somebody else's account that happens to share this username".
    """

    __slots__ = ("username", "full_name", "email_address", "role", "status")

    def __init__(
        self,
        username: str,
        full_name: str,
        email_address: str,
        role: str,
        status: str = "active",
    ) -> None:
        self.username = username
        self.full_name = full_name
        self.email_address = email_address
        self.role = role
        self.status = status


#: The identities this seed owns. Obviously synthetic by construction: `demo.`
#: usernames, `Demo ...` display names and `.invalid` addresses. No client
#: person's name appears in development data.
#:
#: Only the General persona is here. Administrator is seeded from the configured
#: demo credential by `prototype_users.seed_demo_user`, and the five Technicians
#: by `seed_admin_demo` — re-creating either would give two modules a claim on
#: one row.
DEMO_PERSONAS: tuple[DemoPersona, ...] = (
    DemoPersona(
        username="demo.general01",
        full_name="Demo General User 01",
        email_address="demo.general01@example.invalid",
        role="general",
    ),
)


def demo_usernames() -> tuple[str, ...]:
    """The usernames this seed owns — and the only rows `--reset` may delete."""
    return tuple(persona.username for persona in DEMO_PERSONAS)


def claim_persona(persona: DemoPersona) -> None:
    """Create this identity, or adopt the row a previous run left behind.

    Refuses if the username exists but does not look like this seed's own work.
    The check is the reserved `.invalid` address rather than the display name,
    because an administrator editing a demo persona's name through the UI should
    not turn a later reseed into a refusal — but a genuine account that happens
    to be called `demo.general01` must never be quietly overwritten.
    """
    existing = repo.get_user_by_username(persona.username)
    if existing is not None and existing.email_address != persona.email_address:
        raise DemoPersonaRefused(
            f"User {persona.username!r} already exists and was not created by "
            f"this seed (expected {persona.email_address!r}, found "
            f"{existing.email_address!r}). Refusing to overwrite it. Rename or "
            f"remove that account first if the demo persona is really wanted."
        )
    repo.create_or_update_user(
        username=persona.username,
        full_name=persona.full_name,
        role=persona.role,
        status=persona.status,
        email_address=persona.email_address,
    )


def reset_demo_personas() -> None:
    """Remove this seed's personas. Nothing else.

    Safe to run when nothing was ever seeded. No assignment cleanup is needed
    or attempted: this seed creates no assignments, and deleting one it did not
    make would be exactly the cross-seed reach the module docstring refuses.
    """
    for username in demo_usernames():
        repo.delete_user_by_username(username)


def seed_demo_personas() -> tuple[str, ...]:
    """Create the demo login personas. Idempotent; returns what it claimed."""
    for persona in DEMO_PERSONAS:
        claim_persona(persona)
    return demo_usernames()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Seed the synthetic login personas used to demonstrate each role "
            "through the ordinary login path. Development data only — never "
            "run against production. Creates identities, never credentials: "
            "set DEMO_CREDENTIALS to give one a password."
        )
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help=(
            "Remove this seed's personas first. Only rows this seed owns are "
            "deleted; other users are left alone."
        ),
    )
    args = parser.parse_args(argv)

    print("Login-persona demo seed — DEVELOPMENT DATA ONLY")
    print(f"Schema: {repo._SCHEMA}")

    if args.reset:
        print("\nRemoving previous demo personas...")
        reset_demo_personas()
        print("  Reset complete.")

    try:
        claimed = seed_demo_personas()
    except DemoPersonaRefused as exc:
        print(f"\nRefused: {exc}")
        return 1

    print("\nPersonas in place:")
    for username in claimed:
        row = repo.get_user_by_username(username)
        print(f"  {username}  role={row.role}  status={row.status}")
    print(
        "\nThese identities have no password. Add one to DEMO_CREDENTIALS in "
        ".env to sign in as them (see .env.example)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
