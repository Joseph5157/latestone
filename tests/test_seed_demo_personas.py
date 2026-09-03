"""ROLE-4A — the login-persona seed.

One concern, in two halves. The pure half is the shape of what it claims: a
synthetic identity, a confirmed role, and no credential anywhere near it. The
database half is containment — this seed writes people, and it must never touch
a user it did not create.

Deliberately narrow. It owns the General persona only; Administrator comes from
the configured demo credential and the Technicians from `seed_admin_demo`, and
a test that let this module claim either would be encoding the cross-seed reach
its docstring refuses.
"""
from __future__ import annotations

import pytest

from db import seed_demo_personas as seed
from db.seed_admin_demo import DEMO_TECHNICIANS
from db.seed_demo_personas import (
    DEMO_PERSONAS,
    DemoPersonaRefused,
    claim_persona,
    demo_usernames,
    reset_demo_personas,
    seed_demo_personas,
)
from repositories import plant_monitoring_repository as repo
from services.prototype_users import CONFIRMED_ROLES


class TestWhatItClaims:
    def test_every_persona_holds_a_confirmed_role(self):
        for persona in DEMO_PERSONAS:
            assert persona.role in CONFIRMED_ROLES

    def test_the_missing_general_persona_is_the_point_of_this_seed(self):
        assert [p.role for p in DEMO_PERSONAS] == ["general"]

    def test_identities_are_obviously_synthetic(self):
        """`.invalid` is reserved by RFC 2606, so these can never route."""
        for persona in DEMO_PERSONAS:
            assert persona.username.startswith("demo.")
            assert persona.email_address.endswith("@example.invalid")

    def test_it_does_not_claim_a_technician_another_seed_owns(self):
        technicians = {t.username for t in DEMO_TECHNICIANS}
        assert technicians.isdisjoint(set(demo_usernames()))

    def test_a_persona_carries_no_credential_field(self):
        """The ROLE-4A split, structurally: this module writes identities, and
        `DEMO_CREDENTIALS` configures logins. A password attribute here would be
        the first step back towards a role that configuration can grant."""
        persona = DEMO_PERSONAS[0]
        assert not hasattr(persona, "password")
        assert not any("pass" in slot.lower() for slot in persona.__slots__)


class TestContainment:
    pytestmark = [pytest.mark.db, pytest.mark.usefixtures("isolated_schema")]

    def test_seeding_creates_the_general_persona(self):
        reset_demo_personas()
        seed_demo_personas()
        row = repo.get_user_by_username("demo.general01")
        assert row is not None
        assert row.role == "general"
        assert row.status == "active"

    def test_seeding_is_idempotent(self):
        reset_demo_personas()
        seed_demo_personas()
        first = repo.get_user_by_username("demo.general01")
        seed_demo_personas()
        second = repo.get_user_by_username("demo.general01")
        assert first.user_id == second.user_id
        assert first.role == second.role

    def test_reset_removes_only_what_this_seed_owns(self):
        reset_demo_personas()
        seed_demo_personas()
        repo.create_or_update_user(
            username="real.person",
            full_name="Real Person",
            role="general",
            status="active",
            email_address="real.person@example.invalid",
        )
        reset_demo_personas()
        assert repo.get_user_by_username("demo.general01") is None
        assert repo.get_user_by_username("real.person") is not None

    def test_it_refuses_to_overwrite_an_account_it_does_not_own(self):
        reset_demo_personas()
        repo.create_or_update_user(
            username="demo.general01",
            full_name="Someone Real",
            role="administrator",
            status="active",
            email_address="someone@real.example",
        )
        with pytest.raises(DemoPersonaRefused):
            seed_demo_personas()
        survivor = repo.get_user_by_username("demo.general01")
        assert survivor.role == "administrator"
        assert survivor.email_address == "someone@real.example"

    def test_it_adopts_its_own_row_even_after_a_rename(self):
        """An administrator editing the display name through the UI must not
        turn the next reseed into a refusal — ownership is the address."""
        reset_demo_personas()
        seed_demo_personas()
        repo.create_or_update_user(
            username="demo.general01",
            full_name="Renamed By An Admin",
            role="general",
            status="active",
            email_address="demo.general01@example.invalid",
        )
        seed_demo_personas()
        row = repo.get_user_by_username("demo.general01")
        assert row.full_name == "Demo General User 01"

    def test_reset_is_safe_when_nothing_was_seeded(self):
        reset_demo_personas()
        reset_demo_personas()
        assert repo.get_user_by_username("demo.general01") is None


class TestTheSeededPersonaCanBeAuthenticated:
    pytestmark = [pytest.mark.db, pytest.mark.usefixtures("isolated_schema")]

    def test_a_configured_credential_resolves_to_the_general_role(self, monkeypatch):
        """End to end across the ROLE-4A split, against a real row: the seed
        supplies the identity, configuration supplies only the password, and
        the role comes back from storage."""
        from config import settings
        from config.settings import DemoAuthSettings
        from services import auth_service, prototype_users

        reset_demo_personas()
        seed_demo_personas()

        # A password carrying both delimiters, so this also proves the JSON
        # encoding end to end and not just in the parser's unit tests.
        secret = "gen,eral:pw"
        creds = DemoAuthSettings(
            username="",
            password="",
            extra_credentials='{"demo.general01": "gen,eral:pw"}',
        )
        monkeypatch.setattr(auth_service, "demo_auth", creds)
        monkeypatch.setattr(settings, "demo_auth", creds)
        monkeypatch.setattr(prototype_users, "seed_demo_user", lambda: None)

        user = auth_service.authenticate("demo.general01", secret)
        assert user is not None
        assert user.role == "general"
        assert user.username == "demo.general01"
        assert auth_service.authenticate("demo.general01", "wrong") is None
        assert auth_service.authenticate("demo.general01", "gen") is None


def test_module_exposes_a_cli():
    assert callable(seed.main)
