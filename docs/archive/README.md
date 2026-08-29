# Archive

Cold storage (see `AGENTS.md` context levels). Everything here is a completed
planning prompt or spec for a tranche that has already shipped, verified
against `main` at the time it was archived — not against a claim in the
document itself.

Per `docs/context/SOURCE_AUTHORITY.md`: **a document here is never evidence
for current behaviour.** If you need to know what the application does now,
read the source it describes, not the prompt that planned it. If this
directory and the running code disagree, the code is right and this directory
is stale history.

Do not load this directory to start a task. `AGENTS.md` names what to read
instead: `docs/context/ACTIVE_GATE.md` and the ADRs it points to.

## Contents

| File | Tranche | Shipped as |
|---|---|---|
| `ENT-2_Post_Review_Agent_Prompt.md` | ENT-2 — grouped exception queue | `4e6d26c` |
| `ENT-3_PLANNING_PROMPT.md` | ENT-3 — device snapshot/quick-trends consolidation | `ccd0206` |
| `ENT-4_PLANNING_PROMPT.md` | ENT-4 — Notification Center ordering, categories, navigation | verified in `services/notification_service.py`, `callbacks/notifications.py` |
| `AUD-1_PLANNING_PROMPT.md` | AUD-1 — wire audit_log into real mutations | `c69c51b` |
| `AUD-1I_IMPLEMENTATION_SPEC.md` | AUD-1 implementation spec | `c69c51b` |
| `REPORT-2_PLANNING_PROMPT.md` | REPORT-2 — Installed RTLs report backend | `8f2d43c` |

A document's own "Status" or "Gate" heading is not authoritative once it is
here — ENT-4's prompt still reads "Do not implement until this plan is
approved" despite being fully shipped. That mismatch is exactly why these
files were moved out of the root: a status line inside prose goes stale
silently; a location does not.
