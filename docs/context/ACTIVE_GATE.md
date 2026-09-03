# Active Gate

Status: Complete — reviewed, accepted, committed and pushed
Date: 2026-09-03
Gate: ROLE-4A — credentialed personas
Branch: `main`, baseline `524efdf`
Commit/push permission: GRANTED at ROLE-4A-CLOSE, after review, for the
reviewed ROLE-4A file set onto `main`. The gate was implemented under an
explicit "do not commit, do not push" and held for that review.

## Purpose

Give Administrator, Technician and General a real login each, through the
application's ordinary credential path, so every role resolves to its own
persisted identity instead of one credential being the only way in.

## The limitation this closes

`verify_credentials` compared against a single configured pair
(`services/auth_service.py:71` at baseline), and `authenticate()` then looks up
**the typed username** — so exactly one username could ever reach the lookup.
The database held five Technician rows and no General row, none with a
credential. Administrator was the only persona anyone could sign in as.

That is why CC-1 acceptance verified the non-administrator side by substituting
the authorization identity in the session store and recorded that "a
credentialed technician login has no demo credential"
(`CC1_ACCEPTANCE.md`, "Deferred, explicitly", item 1). ROLE-4B, 4C and 4D each
need a real login for the role they are about.

## Decision — ADR-015

**Credential configuration names logins; the `users` row names the role.**

`DEMO_CREDENTIALS` adds personas beside the existing
`DEMO_USERNAME`/`DEMO_PASSWORD` administrator pair, as a JSON object of
`"username": "password"`. There is no field in that configuration in which a
role could be written, so adding a credential can only let an existing row be
reached — never grant a permission.

### Changed during closure, at the operator's direction

Review caught that the first encoding — comma-separated `name:secret` entries —
could not say what a password was: `a:pw,b:c` reads equally as one credential
with password `pw,b:c` or as two pairs, and the parser silently chose the
second. Not an access risk (a phantom credential still has to name an active
`users` row), but a silent one that handed the real user a shorter password
than they set.

Replaced with a JSON object parsed by the standard library's `json` — no new
dependency, and values are quoted, so `,` and `:` are ordinary characters.
`json.loads` resolving a repeated key by silently keeping the last was closed
in the same change: `object_pairs_hook` reads the pairs before they collapse,
so a repeat is refused rather than guessed at. `DEMO_USERNAME`/`DEMO_PASSWORD`
are untouched and still work with no JSON at all.

Per-user password hashes in the database were considered and deliberately not
built. The client's Functional Spec does list `Password` as a user field, so
that is the eventual production shape, but `docs/CODE_AUDIT.md:550-553` records
that the real mechanism is undesigned pending the client (S-4/S-5), and a hash
would authenticate into the same forgeable browser-side session. Reasoning in
full in ADR-015.

**Schema migration: NO.** **New dependency: none.**

## In scope

- `config/settings.py` — `parse_demo_credentials()`, `_credential_pairs()` and
  the widened `DemoAuthSettings`. Invalid JSON, a non-object, an empty username,
  a non-string or empty password, or a repeated username refuse the **whole**
  map — every login, the administrator included.
- `services/auth_service.py` — `verify_credentials()` checks the map;
  `authenticate()` is unchanged, which is the point.
- `db/seed_demo_personas.py` — the one missing identity, `demo.general01`.
  Deliberately a separate seed: `seed_admin_demo.demo_usernames()` decides which
  assignments that seed owns, and putting a non-technician in it would be an
  assignment-semantics change made for a login reason.
- `tests/test_credentialed_personas.py`, `tests/test_seed_demo_personas.py`.
- `tests/test_auth_hardening.py`, `tests/test_auth_identity.py` — the `_Creds`
  doubles gain the map the service now reads. Every existing assertion is
  unchanged; 178 of them still pass.
- `.env.example`, `docs/GETTING_STARTED.md`.

## Explicitly out of scope — and not touched

- **ROLE-4B** — Technician Manage / Programming / Forwarding / Deactivation UI.
  Those actions are already authorized in backend policy and still have no
  reachable Technician surface. Unchanged here.
- **ROLE-4C** — the broader General/Viewer experience. Only the one identity
  needed for a credentialed login was added.
- **ROLE-4D** — the full browser role matrix. A minimal credential smoke was
  run instead (below).
- Authorization of any kind: no route policy, capability, action or scope rule
  was edited. No second authorization system was introduced.
- The `users` schema, and any migration.
- The untracked `debug.log`.

## Relevant files

- `services/auth_service.py`
- `config/settings.py`
- `db/seed_demo_personas.py`
- `services/prototype_users.py` (read only — `seed_demo_user` still seeds the
  administrator alone, which is what keeps configuration from minting users)
- `docs/decisions/ADR-015-credentials-name-logins-not-roles.md`

## Verification

Regression seen failing first, for the right reason: **7 failed, 21 passed** —
`demo.tech01` and `demo.general01` "could not sign in" while the administrator
could. After: 28 passed.

- `tests/test_credentialed_personas.py` — 53 passed, including passwords
  carrying `,` and `:` together (parsed *and* authenticated end to end), the
  old grammar's exact ambiguous string, repeated JSON keys, and 14 malformed
  configurations.
- `tests/test_seed_demo_personas.py` — 13 passed (7 DB-marked); the end-to-end
  one now uses a delimiter-bearing password.
- Existing auth/login/session/user suites — **178 passed**, assertions unchanged.
- Authorization non-regression (authorization, action guard, route scope, scope
  repository, report export, auth identity/hardening) — **354 passed**.
- Non-DB suite — **2,563 passed**. Full suite — **3,059 passed**.
- Live smoke through the real `authenticate()` against the development
  database, no monkeypatching and no session editing:

| login | role | user_id | password in session |
|---|---|---|---|
| `admin` | administrator | 103 | no |
| `demo.tech01` | technician | 104 | no |
| `demo.general01` | general | 115 | no |

  Run with passwords containing both delimiters (`te,ch:1234`,
  `gen,eral:1234`). Wrong password, unknown username and another persona's
  password all returned `None`. A malformed `DEMO_CREDENTIALS` refused every
  login including the administrator, and the logged diagnostic contained no
  secret.

- Live authorization read off those three sessions: Administrator reaches every
  route; **Technician and General are both denied `admin_devices`, `admin_users`
  and `device_register`** — unchanged by being able to log in. Device scope:
  administrator and general unrestricted, `demo.tech01` restricted to its 24
  assigned RTLs.
- Real `plant_monitoring.users` confirmed untouched by the test run; the DB
  tests ran against `isolated_schema` and leaked none.

## What this does not claim

S-4 and S-5 are untouched. The session is still browser-held, the data
callbacks still do not verify it, and anyone who can set that store can still
set `role` in it. Three real logins make the demo honest and ROLE-4B/4D
testable; they do not make the session unforgeable.

## Operator action needed for a browser login

The identities exist in the development database, but a credential is local
configuration and was deliberately not written into `.env`. To sign in as the
other two personas, add one line with secrets of your own choosing:

```
DEMO_CREDENTIALS={"demo.tech01": "<secret>", "demo.general01": "<secret>"}
```

## Outcome

ROLE-4A is **CLOSED**. The reviewed change was committed as

```text
f0862d085680ca0d4b0f774d6b44f5d224810b75
feat(auth): add credentialed demo personas
```

covering the two implementation modules, the new persona seed, four test files,
two configuration/doc files and the context records, and pushed to
`origin/main` with local and remote SHAs verified to match. The untracked
`debug.log` was neither staged nor committed.

Verification baseline at closure: full suite **3,059 passed**, non-DB **2,563
passed**, auth/session **178**, authorization non-regression **354**, persona
seed DB tests **7**, credential smoke **3/3** through the real `authenticate()`.
`git diff --check` clean; context pack CLEAN before staging and after the
commits.

### Provenance

Two commits, which is what the validator requires rather than a style choice:
`scripts/build_context_pack.py:208` accepts an `Implemented-by` only if it
begins "not yet" or names a **reachable** commit, so an ADR can never cite the
commit that carries it. `f0862d0` was written into `ADR-015` and
`DECISION_INDEX.md` immediately afterwards, by
`docs(context): backfill ROLE-4A provenance`. ADR-014 used the same two-step.

Nothing is outstanding for ROLE-4A.

### Still open, deliberately

**S-4 / S-5 remain architectural debt.** The session is a browser-side
`dcc.Store`, the data callbacks do not independently verify it, and anyone who
can set that store can still set `role` in it. Closing them needs the client's
authentication mechanism, which is not yet chosen
(`docs/CODE_AUDIT.md:540-575`). ROLE-4A must not be described as solving it.

**Browser acceptance has not happened.** The credential path was proven at the
service boundary against the development database; the full browser role matrix
is ROLE-4D.

## Next queued gate — do not start

**ROLE-4B — Technician operational surface**, then ROLE-4C (General persona)
and ROLE-4D (browser acceptance for all three roles). PCB remains paused at
`PCB-9-CLOSE`.
