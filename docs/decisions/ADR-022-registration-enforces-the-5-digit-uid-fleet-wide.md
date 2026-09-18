# ADR-022: Registration enforces the 5-digit RTL UID, unique across the fleet

Status: Approved
Date: 2026-09-18
Evidence: `services/rtl_uid.py` (`UID_PATTERN`, `uid_format_error`);
`services/device_registration.py` (`device_code_problem`, `register_device`);
`services/rtl_programming_service.py` (`_validate_programming_identity`);
`services/device_event_service.py` (identity resolution rule 3);
`repositories/plant_monitoring_repository.py` (`find_device_ids_by_code`);
`alembic/versions/001_baseline.py` (`UNIQUE (transformer_id, device_code)`);
`tests/test_device_register.py`
Implemented-by: not yet
Supersedes: nothing. Closes the registration half of tracker row PROG-02,
which FS-PROG-1 (`176dc49`) left open.

## Context

Two rules about the RTL UID (`devices.device_code`) disagreed:

- **Registration** accepted any trimmed code of up to 10 characters.
- **RTL programming** (FS-PROG-1) accepts only exactly 5 digits
  (Functional Specification §4.4.1: "5-digit RTL UID, e.g. 29xxx").

So an Administrator could register a device and then find that it could not
be programmed. FS-PROG-1 deliberately left registration unchanged, pending
client confirmation.

Uniqueness had the same kind of gap. The only database guarantee is
`UNIQUE (transformer_id, device_code)`. The same code could therefore be
registered under two transformers. But the RTL Master addresses a device by
UID alone (`Program->29xxx->TRFRName`), and incoming messages carry only
the UID. Event ingestion's rule 3 already refuses to pick a device when a
UID matches more than one. A duplicate code would therefore quietly stop
both devices receiving their startup and alarm events.

The local development data holds 120 devices with 120 distinct codes, all
of them 5 digits.

## Decision

1. **One UID format rule, in one place.** `services/rtl_uid.py` owns
   `UID_PATTERN` (`^\d{5}$`) and `uid_format_error()`. Registration and
   RTL programming both use it. No "29" prefix is required: the
   specification shows that as an example, not a rule.
2. **Registration enforces it at both layers.** The form checks it live and
   at Review. `register_device` checks it again, so a direct callback
   invocation cannot skip it.
3. **Codes are unique across the whole fleet, enforced in the application
   only.** `device_code_problem()` refuses a code already registered
   anywhere, naming the plant and transformer that hold it. Review calls it,
   and `register_device` calls it again inside its own transaction.
4. **No database constraint yet.** Global uniqueness is strongly implied by
   how the RTL Master addresses devices, but no source document states it.
   Per the project's constraint rule (confirmed rules only), a
   `UNIQUE (device_code)` index waits for the client. The data is already
   clean, so adding it later is a short migration.

**These are development baselines, not client-confirmed rules.** The format
comes from the Functional Specification. Applying it at registration, and
fleet-wide uniqueness, are our decisions pending client confirmation.

## Consequences

- Every registered device can be programmed, and a registered UID resolves
  to exactly one device during event ingestion.
- Two Administrators registering the same code at the same instant could
  both succeed, because only a database constraint closes that race. It is
  unlikely, and ingestion's rule 3 fails safe (it attributes to neither
  device).
- If the client says a UID may repeat across sites (for example, a
  replacement RTL reusing an old code), decision 3 is one function call to
  remove.
- Open client question: "Is an RTL UID unique across the whole network?"
