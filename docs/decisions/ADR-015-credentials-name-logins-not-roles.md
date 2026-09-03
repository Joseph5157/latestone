# ADR-015: Credentials name logins; the `users` row names the role

Status: Approved
Date: 2026-09-03
Evidence: `services/auth_service.py:71` (`verify_credentials`, the credential
half); `services/auth_service.py:96` (`authenticate`, the identity half);
`config/settings.py` (`parse_demo_credentials`, `_credential_pairs`,
`DemoAuthSettings`);
`db/seed_demo_personas.py` (the General identity); `pages/login.py` and
`callbacks/auth.py:30` (the form carries username and password only);
`docs/RTL_FUNCTIONAL_SPEC_EXTRACT.md:56` (the client lists `Password` as a
user field); `docs/CODE_AUDIT.md:540-575` ("Security posture", S-4/S-5)
Implemented-by: not yet — ROLE-4A is held at human review, uncommitted
Supersedes: nothing. It makes explicit the split ROLE-1 already built into
`authenticate()` and extends it from one credential to several.

## Context

ROLE-1 separated two jobs inside `auth_service`: `verify_credentials()` proves
a credential, and `authenticate()` decides who that credential *is* by loading
the persistent `users` row. The second half was already correct — role has
never come from the login form.

The first half was not finished. `verify_credentials` compared against a single
configured `DEMO_USERNAME`/`DEMO_PASSWORD` pair, and `authenticate()` then looks
up **the typed username**. So exactly one username could ever reach the lookup.
The database held five Technician rows and no General row, none of them with a
credential, and the practical consequence was that Administrator was the only
persona anyone could sign in as.

That is why CC-1 acceptance verified the non-administrator side by substituting
the authorization identity in the session store, and recorded honestly that "a
credentialed technician login has no demo credential" (`CC1_ACCEPTANCE.md`,
"Deferred, explicitly", item 1). ROLE-4B, 4C and 4D all need a real login for
the role they are about.

## Decision

**Credential configuration carries username/password pairs and nothing else.
The `users` row decides user_id, name, role and status.**

`DEMO_CREDENTIALS` adds personas to the existing `DEMO_USERNAME`/`DEMO_PASSWORD`
pair as a JSON object of `"username": "password"`. There is no field in that
configuration in which a role could be written, so adding a credential can never
grant a permission — it can only let an existing row be reached. A Technician
credential yields a Technician session because the row says technician.

### The encoding is JSON because a delimiter grammar could not say what a password was

The first form of this setting split on commas, then on the first colon. Human
review caught that `a:pw,b:c` has two equally valid readings — one credential
whose password is `pw,b:c`, or the two pairs `a`/`pw` and `b`/`c` — and the
parser silently chose the second. It was not an access risk (a phantom
credential still has to name an active `users` row, and configuration cannot
create one), but it was a **silent** failure that handed the real user a
shorter password than they set.

JSON quotes its values, so `,` and `:` are ordinary characters and the encoding
has exactly one reading. It is `json` from the standard library — no dependency,
and `AGENTS.md` requires justifying one.

One sharp edge came with it and is closed deliberately: `json.loads` resolves a
repeated key by keeping the last value and saying nothing, so
`{"a": "x", "a": "y"}` would have quietly configured one credential with no
indication which. `object_pairs_hook` reads the pairs *before* they collapse
into a dict, which is what lets a repeat be refused rather than guessed at.
Replacing one silent ambiguity with another would have missed the point.

The flow is unchanged and stays single:

```
credentials -> verify_credentials -> users row -> session -> existing guards
```

Authorization was not touched. ROLE-2 route policy, ROLE-3 device scope and the
action/capability guards keep consuming `role` off the session exactly as
before, and this gate added no policy of its own.

## Why not per-user password hashes in the database

The client's Functional Specification does list `Password` as a user field, so
credential storage is the eventual production shape and Option A is where this
ends up. It is the wrong step *now*, for three reasons:

1. **The mechanism is not chosen yet.** `docs/CODE_AUDIT.md:550-553` records
   that the session is browser-held, that the data callbacks do not verify it,
   and that closing S-4/S-5 "needs the client's mechanism (session cookie, SSO,
   API token) before it can be designed". Committing a hash column, a hashing
   scheme and a credential-management UI now builds durable storage for an
   authentication design that does not exist, on a schema the client will also
   own.
2. **It buys no security here.** A hash in `users` still authenticates into the
   same forgeable browser-side session. It would look more production-ready
   without being so, which is worse than the current honest placeholder.
3. **It is not the smallest correct change.** A migration on a client-bound
   schema, a new password-hashing dependency (`AGENTS.md` requires justifying
   one), and an admin flow for setting passwords are a tranche; the limitation
   in scope here is one function comparing against one pair.

No migration was created. The existing schema already carries everything the
identity side needs, and the credential side deliberately does not touch it.

**What survives the eventual swap is this ADR's rule, not its storage.** When
credentials move into the database or behind the client's SSO,
`verify_credentials` changes and `authenticate()` does not: the row still
decides the role. That separation is the decision; `DEMO_CREDENTIALS` is only
today's implementation of the credential half.

## Fail-closed behaviour

Unchanged where it existed, and extended to the new failure modes:

| Condition | Result |
|---|---|
| No credential configured | every login refused, logged |
| `DEMO_CREDENTIALS` is not valid JSON | **every** login refused, including the administrator |
| Not a JSON object (array, string, number, null) | every login refused |
| Empty username, or a non-string / empty password | every login refused |
| Repeated username, including a repeated JSON key | every login refused |
| Unknown username | refused |
| Wrong password | refused |
| Credential names no `users` row | refused |
| Row is not `active` | refused |
| Row's role outside `CONFIRMED_ROLES` | refused |

A partly-valid credential list refuses the whole map rather than dropping the
bad entry. Ambiguity about who may sign in must not resolve to "some logins
work" — that is the shape that convinces an operator a persona is disabled when
it is not. The logged diagnostic names the entry position, the username and the
reason; never a secret, and never `JSONDecodeError.doc`, which is the raw
configuration value and therefore contains every password.

An unknown username is compared against a sentinel before refusing, so it costs
the same as a wrong password. A faster "no such user" is a username oracle.

## What this does not claim

**S-4 and S-5 are untouched.** The session is still a browser-side `dcc.Store`,
the data callbacks still do not verify it, and anyone who can set that store can
still set `role` in it. Three real logins make the *demo* honest — nobody has to
hand-edit a store to see a Technician screen any more — and they make ROLE-4B/4D
testable. They do not make the session unforgeable, and no part of this gate
should be read as saying otherwise.

Passwords remain in environment configuration, not in the database and not in
git. `.env` is gitignored; `.env.example` carries placeholders only.
