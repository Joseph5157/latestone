# PostgreSQL retirement matrix

Current schema authority is Alembic migrations `001` through `015`. Nothing is deleted or migrated by this audit.

The two decisions below are deliberately separate:

- **Capability / schema migration:** must the production capability eventually have a SQL Server representation?
- **Existing data migration:** are the rows currently in this development PostgreSQL database production records worth preserving?

| PostgreSQL table | Why it exists / current use | Capability / schema direction | Existing data migration | Eventual disposition / dependency |
|---|---|---|---|---|
| `plants` | Synthetic 30-plant hierarchy | No direct SQL Server replacement decided; hierarchy authority is unresolved | NOT APPLICABLE — synthetic hierarchy | RETIRE DEMO/SYNTHETIC after approved real hierarchy mapping and application migration. |
| `transformers` | Synthetic 71-transformer hierarchy | Same review as hierarchy/mapping | NOT APPLICABLE — synthetic hierarchy | RETIRE DEMO/SYNTHETIC after mapping decision. |
| `devices` | Synthetic 120-device model / registered-device UI | `device_list` is the registered RTL directory; full device model remains review | NOT APPLICABLE — synthetic model | RETIRE DEMO/SYNTHETIC when source-backed directory/hierarchy path is ready. |
| `readings` | Eight synthetic metric histories | Temperature read capability maps to `master_temperature`; seven metrics need client source decision | NOT APPLICABLE — synthetic measurements | RETIRE DEMO/SYNTHETIC; do not create SQL Server structures merely to retain unsupported metrics. |
| `users` | Development authentication and role identity | REVIEW_REQUIRED: assess `persons` / `roles` and production security model | REVIEW REQUIRED | Keep temporarily until production authentication is decided and implemented. |
| `user_device_assignments` | Development user-device visibility | Adapt `technician_assignments` if client confirms its operational use | REVIEW REQUIRED | Keep temporarily; no second technician-assignment structure proposed. |
| `rtl_active_state` | Application activation/deactivation state | SQL Server representation only if production activation/deactivation is retained | REVIEW REQUIRED | Keep temporarily; capability decision and any record migration are separate. |
| `rtl_programming_requests` | Programming request intent/history | SQL Server command lifecycle only if production commands are authorised | REVIEW REQUIRED | Keep temporarily pending production command decision. |
| `rtl_commands` | Command dispatch/result lifecycle | Same conditional command capability | REVIEW REQUIRED | Keep temporarily pending production command decision. |
| `message_forwarding` | Application forwarding preference | REVIEW_REQUIRED against existing contact/forwarding structures | REVIEW REQUIRED | Keep temporarily pending consent, ownership and forwarding policy. |
| `forwarding_auto_disable_override` | Application forwarding override | REVIEW_REQUIRED with forwarding capability | REVIEW REQUIRED | Keep temporarily pending the same client decision. |
| `device_events` | Normalised app event projection and acknowledgement | Source events can be adapted; acknowledgement/response capability needs a SQL Server representation if retained | REVIEW REQUIRED | Keep temporarily; do not presume development rows move to production. |
| `audit_log` | Application actor/change audit trail | Strong candidate for approved app-owned SQL Server audit capability | REVIEW REQUIRED | Keep temporarily pending detailed audit/retention design and production-record review. |
| `temperature_threshold_config` | Administrator temperature limits | Strong candidate for approved app-owned SQL Server configuration | REVIEW REQUIRED | Keep temporarily; no current rows are automatically production configuration. |
| `freshness_threshold_config` | Administrator freshness setting | Strong candidate for approved app-owned SQL Server configuration; exact offline hours remain unresolved | REVIEW REQUIRED | Keep temporarily pending client threshold decision and configuration design. |
| `vibration_contract_answers` | Unresolved contract capture | REVIEW_REQUIRED; no confirmed client SQL Server counterpart | REVIEW REQUIRED | Retire if the business confirms the capability is not required; otherwise decide its production owner. |

## What prevents deleting PostgreSQL today

The application still runs from PostgreSQL hierarchy and synthetic readings; it also depends on current authentication/assignment, commands/active state, events/acknowledgements, audit and configuration capabilities. PostgreSQL is transitional, but is retired only after client clarifications, approved SQL Server changes, repository/service migration, any specifically approved production-record migration, real-data verification, runtime dependency removal, and SQL Server-only acceptance testing.
