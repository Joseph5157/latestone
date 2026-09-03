"""ROLE-4A — three credentialed personas, one authentication mechanism.

The limitation this closes: `verify_credentials` proved a single configured
pair, so exactly one username could ever sign in. Five Technician rows and no
General row existed, and none of them had a credential — Administrator was the
only persona reachable through the normal login path.

**The invariant is the split.** A credential proves *a* login; the persisted
`users` row decides *who that is* and *what role they hold*. Configuration
therefore carries username/password pairs and nothing else: no role, no
capability, no identity. Add a credential for a technician and you get that
technician's role, because the row says so — not because the configuration
named one. That is what makes it impossible to grant yourself administrator by
editing your own credential entry, and it is the property every test below is
really about.

This is authentication only. Authorization keeps consuming `role` from the
session exactly as ROLE-2/ROLE-3 built it; nothing here decides what a role may
do, and `docs/CODE_AUDIT.md` "Security posture" (S-4/S-5) is unchanged — the
session is still browser-held and this gate does not claim otherwise.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone

import pytest

from config import settings
from config.settings import parse_demo_credentials
from repositories import plant_monitoring_repository as repo
from repositories.plant_monitoring_repository import UserRecord
from services import auth_service, prototype_users

#: `created_at`/`updated_at` are required on UserRecord and irrelevant here.
STAMP = datetime(2026, 9, 3, tzinfo=timezone.utc)


def row(user_id: int, username: str, full_name: str, role: str,
        status: str = "active") -> UserRecord:
    return UserRecord(
        user_id=user_id,
        username=username,
        full_name=full_name,
        email_address=f"{username}@example.invalid",
        mobile_number=None,
        role=role,
        status=status,
        created_at=STAMP,
        updated_at=STAMP,
    )


@dataclass(frozen=True)
class _Creds:
    """Credential configuration double — a username/password map and nothing
    else. It deliberately has no way to express a role."""

    credentials: dict
    config_error: str | None = None

    @property
    def is_configured(self) -> bool:
        return bool(self.credentials)

    @property
    def username(self) -> str:
        return next(iter(self.credentials), "")

    @property
    def password(self) -> str:
        return self.credentials.get(self.username, "")


ADMIN = "demo.admin"
TECH = "demo.tech01"
GENERAL = "demo.general01"

THREE_PERSONAS = {ADMIN: "admin-pw", TECH: "tech-pw", GENERAL: "general-pw"}

ROWS = {
    ADMIN: row(1, ADMIN, "Demo Administrator", "administrator"),
    TECH: row(2, TECH, "Demo Technician 01", "technician"),
    GENERAL: row(3, GENERAL, "Demo General User 01", "general"),
}


@pytest.fixture
def personas(monkeypatch):
    """Three configured credentials and the three rows they name."""
    creds = _Creds(dict(THREE_PERSONAS))
    monkeypatch.setattr(auth_service, "demo_auth", creds)
    monkeypatch.setattr(settings, "demo_auth", creds)
    monkeypatch.setattr(prototype_users, "seed_demo_user", lambda: None)
    monkeypatch.setattr(
        repo, "get_user_by_username", lambda username: ROWS.get(username)
    )
    return creds


class TestEachPersonaAuthenticates:
    """The gate's whole point: three separate credentials, three real users."""

    @pytest.mark.parametrize(
        "username, password, expected_role",
        [
            (ADMIN, "admin-pw", "administrator"),
            (TECH, "tech-pw", "technician"),
            (GENERAL, "general-pw", "general"),
        ],
    )
    def test_credential_resolves_to_its_own_persisted_identity(
        self, personas, username, password, expected_role
    ):
        user = auth_service.authenticate(username, password)
        assert user is not None, f"{username} could not sign in"
        assert user.username == username
        assert user.role == expected_role
        assert user.user_id == ROWS[username].user_id
        assert user.full_name == ROWS[username].full_name

    def test_the_three_personas_are_distinct_identities(self, personas):
        signed_in = [
            auth_service.authenticate(u, p) for u, p in THREE_PERSONAS.items()
        ]
        assert all(s is not None for s in signed_in)
        assert len({s.user_id for s in signed_in}) == 3
        assert {s.role for s in signed_in} == {
            "administrator", "technician", "general"
        }


class TestRoleComesFromStorageNotFromTheCredential:
    """The trust boundary. Configuration names a login; the row names a role."""

    def test_a_technician_credential_cannot_reach_administrator(self, personas):
        user = auth_service.authenticate(TECH, "tech-pw")
        assert user.role == "technician"
        assert user.role != "administrator"

    def test_a_general_credential_cannot_reach_technician_or_administrator(
        self, personas
    ):
        user = auth_service.authenticate(GENERAL, "general-pw")
        assert user.role == "general"
        assert user.role not in ("technician", "administrator")

    def test_changing_only_the_stored_row_changes_the_role(self, personas, monkeypatch):
        """Same credential, same configuration — the row is what moved.

        Proves the role is *read* from storage rather than fixed by the
        credential entry, which is the property that makes configuration
        unable to escalate anyone.
        """
        promoted = row(2, TECH, "Demo Technician 01", "administrator")
        monkeypatch.setattr(
            repo, "get_user_by_username",
            lambda username: promoted if username == TECH else ROWS.get(username),
        )
        assert auth_service.authenticate(TECH, "tech-pw").role == "administrator"

    def test_configuration_cannot_express_a_role_at_all(self):
        """A structural guarantee, not a behavioural one: whatever the parser
        returns is a username to password mapping, so there is no field an
        operator could put a role in."""
        creds, error = parse_demo_credentials(
            "admin", "pw", '{"a": "1", "b": "2"}'
        )
        assert error is None
        assert set(creds) == {"admin", "a", "b"}
        assert all(isinstance(v, str) for v in creds.values())


class TestFailsClosed:
    def test_unknown_username_is_refused(self, personas):
        assert auth_service.authenticate("nobody", "admin-pw") is None

    def test_wrong_password_is_refused(self, personas):
        assert auth_service.authenticate(TECH, "admin-pw") is None

    def test_one_personas_password_does_not_open_another(self, personas):
        assert auth_service.authenticate(ADMIN, "general-pw") is None
        assert auth_service.authenticate(GENERAL, "admin-pw") is None

    def test_credential_naming_no_user_row_is_refused(self, personas, monkeypatch):
        monkeypatch.setattr(repo, "get_user_by_username", lambda username: None)
        assert auth_service.authenticate(ADMIN, "admin-pw") is None

    def test_inactive_user_is_refused(self, personas, monkeypatch):
        inactive = row(2, TECH, "Demo Technician 01", "technician", "inactive")
        monkeypatch.setattr(repo, "get_user_by_username", lambda username: inactive)
        assert auth_service.authenticate(TECH, "tech-pw") is None

    def test_role_outside_the_vocabulary_is_refused(self, personas, monkeypatch):
        rogue = row(2, TECH, "Demo Technician 01", "viewer")
        monkeypatch.setattr(repo, "get_user_by_username", lambda username: rogue)
        assert auth_service.authenticate(TECH, "tech-pw") is None

    def test_no_credentials_configured_refuses_every_persona(self, monkeypatch):
        monkeypatch.setattr(auth_service, "demo_auth", _Creds({}))
        for username, password in THREE_PERSONAS.items():
            assert auth_service.verify_credentials(username, password) is False


class TestCredentialConfigurationParsing:
    """`DEMO_CREDENTIALS` is JSON. The grammar it replaced could not say what a
    password was: it split on commas and then the first colon, so `a:pw,b:c`
    read as two credentials *or* as one password `pw,b:c` with equal right, and
    the parser silently chose. That failure was quiet and it weakened a
    credential — the operator got a shorter password than they set. JSON quotes
    values, so a password is whatever is between the quotes.
    """

    def test_the_single_pair_still_works_unchanged(self):
        """Administrator compatibility: DEMO_USERNAME/DEMO_PASSWORD are
        untouched by the encoding change and still work with no JSON at all."""
        creds, error = parse_demo_credentials("admin", "demo1234", "")
        assert error is None
        assert creds == {"admin": "demo1234"}

    def test_extra_personas_are_added_to_the_single_pair(self):
        creds, error = parse_demo_credentials(
            "admin", "pw0",
            '{"demo.tech01": "pw1", "demo.general01": "pw2"}',
        )
        assert error is None
        assert creds == {
            "admin": "pw0", "demo.tech01": "pw1", "demo.general01": "pw2"
        }

    def test_blank_and_whitespace_configuration_adds_nothing(self):
        for raw in ("", "   ", "\n", "\t "):
            creds, error = parse_demo_credentials("admin", "pw0", raw)
            assert error is None
            assert creds == {"admin": "pw0"}

    def test_usernames_are_stripped(self):
        creds, error = parse_demo_credentials("", "", '{"  a  ": "1"}')
        assert error is None
        assert creds == {"a": "1"}


class TestPasswordsMayContainAnyCharacter:
    """The regression the JSON change exists for."""

    @pytest.mark.parametrize(
        "secret",
        [
            "pw,b:c",           # the exact string the old grammar mis-parsed
            "a,b",              # comma alone
            "a:b",              # colon alone
            "p@ss,w:rd",        # both, mixed
            ",:,:",             # nothing but delimiters
            "trailing,",
            ":leading",
            "with spaces, and: punctuation",
            'quote"inside',
            r"back\slash",
        ],
    )
    def test_a_password_survives_delimiters_verbatim(self, secret):
        creds, error = parse_demo_credentials(
            "", "", json.dumps({"user": secret})
        )
        assert error is None
        assert creds == {"user": secret}

    def test_the_old_grammars_ambiguous_case_is_now_one_credential(self):
        """`a:pw,b:c` used to yield {a: pw, b: c} with no error. As JSON it is
        unambiguously one credential whose password contains both delimiters."""
        creds, error = parse_demo_credentials("", "", '{"a": "pw,b:c"}')
        assert error is None
        assert creds == {"a": "pw,b:c"}
        assert "b" not in creds

    def test_a_password_of_delimiters_still_authenticates(self, monkeypatch):
        """End to end, not just parsed: the awkward password actually works."""
        secret = "p@ss,w:rd"
        creds = _Creds({TECH: secret})
        monkeypatch.setattr(auth_service, "demo_auth", creds)
        monkeypatch.setattr(prototype_users, "seed_demo_user", lambda: None)
        monkeypatch.setattr(
            repo, "get_user_by_username", lambda username: ROWS.get(username)
        )
        assert auth_service.authenticate(TECH, secret).role == "technician"
        assert auth_service.authenticate(TECH, "p@ss") is None
        assert auth_service.authenticate(TECH, "w:rd") is None


class TestMalformedConfigurationFailsClosed:
    """Fail closed as a whole. A configuration that is partly ambiguous must
    not resolve to "some logins work" — that is how an operator ends up
    believing a persona is disabled when it is not.
    """

    @pytest.mark.parametrize(
        "raw, why",
        [
            ("not json at all", "bare text"),
            ("{", "truncated object"),
            ('{"a": "1",}', "trailing comma"),
            ("{'a': '1'}", "single quotes are not JSON"),
            ('["a", "1"]', "array, not an object"),
            ('"just a string"', "string, not an object"),
            ("42", "number, not an object"),
            ("null", "null, not an object"),
            ('{"a": 1}', "non-string password"),
            ('{"a": null}', "null password"),
            ('{"a": ""}', "empty password"),
            ('{"a": {"nested": "x"}}', "object password"),
            ('{"": "1"}', "empty username"),
            ('{"   ": "1"}', "whitespace-only username"),
        ],
    )
    def test_malformed_configuration_refuses_everything(self, raw, why):
        creds, error = parse_demo_credentials("admin", "pw0", raw)
        assert creds == {}, why
        assert error, why

    def test_a_repeated_json_key_is_refused_not_silently_collapsed(self):
        """json.loads keeps the LAST value for a repeated key and says nothing.
        Reading the pairs before they collapse is what makes this refusable
        rather than a silent choice between two passwords."""
        creds, error = parse_demo_credentials("", "", '{"a": "first", "a": "second"}')
        assert creds == {}
        assert error
        assert "repeats" in error

    def test_a_duplicate_of_the_single_pair_is_ambiguous(self):
        creds, error = parse_demo_credentials("admin", "pw0", '{"admin": "other"}')
        assert creds == {}
        assert error

    @pytest.mark.parametrize(
        "raw",
        [
            '{"a": "sup3rsecret"}',
            '{"a": "c0nfidential", "a": "x"}',
            '{"a": "unclosed',
            '{"a": 1, "b": "n0tprinted"}',
        ],
    )
    def test_the_error_never_contains_a_password(self, raw):
        _creds, error = parse_demo_credentials("admin", "adminsecret", raw)
        if error is None:
            return
        for secret in ("sup3rsecret", "c0nfidential", "unclosed",
                       "n0tprinted", "adminsecret"):
            assert secret not in error, f"{secret!r} leaked into: {error}"


class TestNoCredentialMaterialLeaves:
    def test_session_payload_carries_no_password(self, personas):
        user = auth_service.authenticate(TECH, "tech-pw")
        payload = auth_service.to_session(user)
        assert "tech-pw" not in repr(payload)
        assert set(payload) == {
            "authenticated", "user_id", "username", "full_name", "role"
        }

    def test_a_refusal_is_not_logged_with_the_password(self, personas, caplog):
        import logging

        with caplog.at_level(logging.DEBUG):
            auth_service.authenticate(TECH, "wrong-password-value")
        assert "wrong-password-value" not in caplog.text
