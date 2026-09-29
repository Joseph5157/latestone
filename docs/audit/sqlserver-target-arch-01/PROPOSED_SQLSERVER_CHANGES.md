# Proposed SQL Server changes — proposal register

No database change, table design, migration SQL, or writer access is authorised by this document. Each item is a capability proposal for a later gate.

| Requirement | Existing SQL Server support / exact gap | Proposed direction | Data / dependent feature | If client declines | Security / audit / ownership |
|---|---|---|---|---|---|
| Application audit trail | No complete observed application actor/change history | Strong candidate for a separate application-owned SQL Server structure, subject to approval | Administrative/operational actor, action and outcome; accountability | Application actions cannot have a durable accountable history | Least-privilege writers, retention and access review; do not alter source telemetry logs by default. |
| Alarm acknowledgement / response history | Source logs record source facts, not who responded, when or what outcome followed | Strong candidate for a separate application-owned structure, subject to approval | Acknowledgement/response actor, time and status; alarm workflow | Source alarms can be displayed, but accountable response workflow remains unavailable | Restrict action writers; preserve source facts without rewriting them; audit acknowledgements. |
| Application configuration | No confirmed application configuration for temperature limits or freshness/offline policy | Strong candidate for approved app-owned configuration persistence | Administrator-set thresholds/settings; condition and freshness features | Configuration remains unavailable or development-only | Protect administrator-only changes and record them in the application audit trail. Offline hours are not specified here. |
| Command lifecycle / application action state | `settings_upload_log` is source history, not app request → dispatch → result/failure → acknowledgement lifecycle | Consider separate application-owned persistence **only if** production programming, activation/deactivation or other commands are approved | Request intent, dispatcher result and action state; command workflow | No safe durable application command workflow | High-risk operational authority; client approval, least privilege and audit are essential. |

## Explicitly not proposed yet

- No new RTL-to-transformer assignment table: `trfr_list`, `tug_report`, `vw_installed_rtls` and `vw_transformer_org_hierarchy` require client authority/operational-use clarification first.
- No new user/role schema: `persons` and `roles` require security and authentication clarification first.
- No new technician-assignment table: investigate/adapt `technician_assignments` first.
- No new notification/forwarding table: existing contact/forwarding structures require consent, ownership, access and retention clarification first.
- No SQL Server modification for seven synthetic dashboard metrics: the client must identify a real source or approve their production retirement.

Separate application-owned structures are a safer *possible direction* where application state is distinct from read-only client source telemetry. That is not an approval to create them. A later gate must design only approved needs.

Recommended sequence: resolve client questions → approve individual changes → implement repository/dialect changes and approved structures → migrate only records confirmed to have production value → verify real behaviour → remove PostgreSQL runtime dependencies → SQL Server-only acceptance.
