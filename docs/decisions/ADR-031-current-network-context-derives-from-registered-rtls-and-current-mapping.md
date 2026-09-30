# ADR-031: Current network context derives from the registered RTLs and their current mapping

Status: Approved
Date: 2026-09-30
Evidence: `docs/database/CLIENT_RTL_SQLSERVER_KNOWLEDGE_BASE.md` §12 (current
mapping), §13 (transformer movement), §14 (TUG); the live comparison recorded
under "Current network context rule" in §12;
`docs/audit/latest-network-context-01/LATEST_NETWORK_CONTEXT_ACCEPTANCE.md`;
`services/rtl_network_service.py`
Implemented-by: `428e092` (`feat(rtl): add current network context`; full sha
428e092ac65b9b2ae239c819826c55a428293491 — the commit carries this ADR too, so
the sha is recorded here afterwards, as ADR-030 did)

## Context

The SQL Server mixes current and legacy rows. Transformer movement is normal
(2,434 code changes across 400 telemetry UIDs), so "the transformer an RTL
reported at some time" is not "the transformer it is on". The application needs
one defensible answer to "where is this RTL in the network?" without treating
the 70,738-row TUG asset list, or any history table, as the monitored fleet.

## Decision

Current client network context is derived from the **current registered RTL
population plus the current transformer mapping**, with TUG-derived hierarchy
used only as **read-only reference enrichment**:

1. **Population**: exactly `dbo.device_list`.
2. **Current transformer**: `dbo.trfr_list` alone. No row → "No current
   transformer mapping". Several rows → ambiguous; none is chosen.
3. **Hierarchy**: `dbo.vw_transformer_org_hierarchy` where its row names the
   same code, compared as the database compares it (trimmed, case-insensitive).
   Never fuzzy. Absent, blank or conflicting → "Hierarchy unavailable".
4. **Precedence**: `trfr_list` outranks the latest settings, check-in and
   telemetry codes because the prior audit established it as the current
   candidate (it matches `device_status.trfr`). Those three are corroboration:
   a difference is surfaced as a disagreement on the row ("Needs review") and
   never silently resolved, nor allowed to change the displayed transformer.
5. **History stays history**: no most-frequent, earliest or latest-seen code is
   promoted to current, and a code change is not treated as proof of relocation.
6. TUG supplies hierarchy text only. It is not used to infer transformer
   status, decommissioning, RTL lifecycle or communication state.

Engineering owns this technical source selection, so CDB-03 no longer asks the
client whether TUG is "the approved source". The client still owns the business
questions: whether `location` is permanent, TUG's refresh, and how
decommissioned transformers are represented.

## Consequences

Two current RTLs (29042, 29598) are shown with their `trfr_list` transformer
and a "Needs review" note, because their latest telemetry names another code.
If the client later approves a different current-mapping authority, or an
application-owned dated assignment history replaces `trfr_list` (KB §13), only
step 2 changes; the population, hierarchy and disagreement rules stand.
The Network view says nothing about whether an RTL is reporting or operating
(CDB-01/CDB-02 remain open).
