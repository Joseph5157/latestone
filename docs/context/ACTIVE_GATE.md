# Active Gate

Status: **CLOSED / PUSHED / REMOTE-VERIFIED**
Date: 2026-09-04
Gate: RTL-IF-4 — Notification delivery abstraction
Branch: `main`, baseline `e3f49b14e4ea122190f9081b15967ddae00657ea`
Commit: `0b2a4d5ec2c88d5a395729d30dee86abf1b6fb4d` — subject
"feat(integration): add notification delivery abstraction". Pushed to
`origin/main`; local `HEAD` (at the time of that push), `origin/main`, and
`git ls-remote origin refs/heads/main` all verified to match this SHA (see
Verification below). This paragraph describes that already-completed,
already-verified push of `0b2a4d5ec2c88d5a395729d30dee86abf1b6fb4d` — it
does not assert anything about whatever commit this documentation edit
itself becomes part of, which is pushed separately, afterward, as its own
step (RTL-IF-4-CLOSE Step 6).
Commit/push permission: **GRANTED and exercised.** RTL-IF-4 was implemented
against explicit "DO NOT COMMIT OR PUSH" instructions and left
`READY FOR REVIEW / NOT COMMITTED`. It was then independently verified by
Codex (RTL-IF-4V — diff scope, in-app notification separation,
provider-neutral delivery contract, deterministic mock delivery, recipient
boundary, privacy/security, forwarding regression, event semantics, no
persistence/schema additions, test quality, architecture boundary all
PASS; no blockers; one non-blocking note — provider-specific endpoint/body
validation remains deferred until real provider formats and limits are
known), and this session's own RTL-IF-4-CLOSE task explicitly authorized
the commit and push recorded above.

**Caveats, preserved from implementation through this closure:** mock
delivery only; no real SMS/email; no production recipient policy; the
Notification Center remains independent and unmodified; message forwarding
is not completed by this tranche (still persists a preference only, sends
nothing); the durable delivery lifecycle (persistence, acknowledgement,
escalation, retention, retry) remains client-dependent and is not
implemented.

## Purpose

Introduce a protocol/provider-neutral notification-delivery boundary for
future Mock/SMS/Email delivery, without changing current in-app
Notification Center behavior and without inventing unresolved client
recipient rules:

```
existing persisted event -> existing event semantics -> existing Notification Center  [UNCHANGED]

future delivery caller -> DeliveryRequest -> NotificationDelivery interface
                                            -> MockNotificationDelivery now
                                            -> SMS / Email adapters later
```

See `docs/decisions/ADR-020-notification-delivery-is-separate-from-the-in-app-projection.md`
for the full decision record.

## What changed

- **`services/notification_delivery.py`** (new) — the contract:
  `CHANNEL_SMS`/`CHANNEL_EMAIL` (`SUPPORTED_CHANNELS`), `STATUS_DELIVERED`/
  `STATUS_FAILED`, `DeliveryRequest` (channel, recipient_endpoint, body,
  reference_id, subject — no Flask/session object, no DB session, no
  provider credentials, no Eskom/SMS vendor payload), `DeliveryResult`
  (status, detail — no provider response id), `NotificationDelivery`
  (`Protocol`, `deliver(request) -> result`, no authorization inside it —
  authorization already happened upstream, entirely the caller's job).
  `UnsupportedChannelError` refuses any channel outside
  `SUPPORTED_CHANNELS` before any delivery attempt.
- **`services/mock_notification_delivery.py`** (new) — deterministic
  `MockNotificationDelivery`: outcome (`succeed=True`/`False`) fixed at
  construction, returned synchronously for every `deliver()` call; no
  network, sleep, thread, or background loop; `.sent` accumulates every
  accepted `DeliveryRequest` so tests can assert exactly what would have
  been delivered. Not a real SMS/email provider — does not model any
  vendor's API or failure codes.
- **`docs/decisions/ADR-020-...md`** (new) — the decision record: why
  delivery stays a separate, unconsumed boundary; why no recipient-
  resolution policy exists; why no schema migration exists.
- **`docs/context/DECISION_INDEX.md`** — ADR-020 row added.
- Tests: `tests/test_notification_delivery.py` (new, 15 tests) — provider-
  neutral request shape, contract field audit (no Flask/session/DB object,
  no provider response id), deterministic mock SMS/email success and
  failure, request accumulation across repeated calls, unsupported-channel
  refusal before recording as sent, no-network-call proof, `Protocol`
  conformance, a caller-resolved real user contact endpoint (via
  `repo.get_user_by_id`) passed explicitly into a `DeliveryRequest`, and —
  via `ast`-based import inspection, not string search — structural proof
  that `notification_service.py`/`event_semantics.py` neither import nor
  are imported by either new module, and that no `callbacks/`/`pages/`/
  `components/` file imports either new module.

**Nothing in `services/notification_service.py`,
`services/event_semantics.py`, `services/message_forwarding_service.py`,
`services/device_event_service.py`, or
`repositories/plant_monitoring_repository.py` was modified.** No schema
migration. This tranche is additive-only: two new modules, one new test
file, one new ADR, and the two context documents.

## Explicitly NOT implemented (out of scope, per the task)

Real SMS, Exchange/email integration, Twilio or any other provider, MQTT/
RabbitMQ, worker, scheduler, retry engine, a `notification_deliveries`
table, notification acknowledgement, escalation, production recipient
routing, 18:30 forwarding, forwarding delivery, high-temperature/vibration
rules, UI redesign, admin notification configuration. No recipient-
resolution policy of any kind — `DeliveryRequest.recipient_endpoint` is
always caller-supplied; this tranche implements no logic that decides who
receives what. No durable delivery history. Enabling message forwarding
still sends nothing (FWD-D9, unchanged) — forwarding is not completed by
this tranche. No new runtime dependencies were installed.

## Verification

- Focused: `tests/test_notification_delivery.py` — 15 passed.
- Regression: `tests/test_notification_service.py` +
  `tests/test_event_semantics.py` + `tests/test_event_consumption_db.py` +
  `tests/test_message_forwarding.py` +
  `tests/test_rtl_command_service_lifecycle.py` +
  `tests/test_rtl_command_dispatch.py` +
  `tests/test_migration_rtl_command_lifecycle.py` +
  `tests/test_simulated_event_source.py` — all passed, run together in one
  invocation, unmodified.
- `python -m pytest -m db -q` — all passed, exit 0, no failures (Windows
  Git Bash swallows this pytest install's final summary line; exit code 0
  plus an unbroken dot sequence with no `F`/`E` markers across every
  progress chunk is the evidence available this session — same caveat
  recorded at RTL-IF-1 through RTL-IF-3's close).
- `python -m pytest -m "not db" -q` — all passed, exit 0, same evidence
  shape as above.
- `python -m pytest -q` (full suite) — all passed, exit 0, same evidence
  shape as above.
- `python scripts/build_context_pack.py --check` — CLEAN, at both open and
  close of this gate.
- `git diff --check` — clean, no whitespace errors.
- `git status --short` — matches the file list above plus untouched
  `debug.log`; no unexpected changes.
- Push verification (RTL-IF-4-CLOSE Step 4): after `git push origin main`,
  `git rev-parse HEAD`, `git rev-parse origin/main`, and
  `git ls-remote origin refs/heads/main` all returned
  `0b2a4d5ec2c88d5a395729d30dee86abf1b6fb4d`.

## Codex RTL-IF-4V independent verification

Result: **VERIFIED**, no blockers — diff scope PASS; in-app notification
separation PASS; provider-neutral delivery contract PASS; deterministic
mock delivery PASS; recipient boundary PASS; privacy/security PASS;
forwarding regression PASS; event semantics PASS; no persistence/schema
additions PASS; test quality PASS; architecture boundary PASS.

Non-blocking note: provider-specific endpoint/body validation (phone
number format, email address format, message length limits, encoding)
remains deferred until a real provider's actual format and limits are
known — `DeliveryRequest.recipient_endpoint`/`.body` accept any string
today, deliberately, since inventing validation rules ahead of a real
SMS/email provider would risk encoding assumptions the eventual provider
does not share.

This gate does not overstate what was built: no real SMS or email exists,
`MockNotificationDelivery` is exactly what its name says, no production
recipient-routing policy exists, and the existing Notification Center is
unmodified and structurally independent of this boundary.

## Security / privacy

No secret enters browser-facing data — `DeliveryRequest`/`DeliveryResult`
carry no credential field at all. The adapter never trusts a browser
role/user_id: `DeliveryRequest` has no identity field, and `deliver()`
performs no authorization check, by design (authorization is entirely the
caller's job, upstream). `MockNotificationDelivery.deliver()`'s failure
`detail` string is a fixed, safe, hardcoded literal — never derived from
caller input, so it cannot leak anything the caller supplied. No test in
this tranche embeds a real credential, phone number, or email address —
`tests/test_notification_delivery.py`'s one DB-marked test creates its own
disposable fixture user on the isolated schema. Recipient resolution, when
it is eventually implemented, remains explicitly deferred to a future
tranche — not sketched here even as a stub. AUTH-HARDEN-1/AUTH-PROD-HARDEN-1
behavior is untouched: no file in `services/auth_service.py`, `app.py`, or
`config/settings.py`'s session/cookie settings was read or modified.

## Known ambiguity

None encountered. No authority conflict between `AGENTS.md`,
`SOURCE_AUTHORITY.md`, `PROJECT_LEDGER.md` §8 (client-undecided delivery/
recipient rules), ADR-018, ADR-019, or the notification/forwarding source
files inspected.

## Next queued gate

None queued. This gate is implemented, independently verified (Codex
RTL-IF-4V), committed as `0b2a4d5ec2c88d5a395729d30dee86abf1b6fb4d`, and
pushed to `origin/main` with the remote match confirmed above. What comes
next is a separate, later decision — most plausibly whichever client
decision resolves first among production recipient-routing policy, a real
SMS/email provider selection, or the durable delivery lifecycle (§8), but
none is decided by this gate.
