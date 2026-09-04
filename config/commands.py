"""RTL command type and state vocabulary (RTL-IF-1).

Constants only — no logic, mirroring `config/audit.py`. Unlike
`rtl_programming_requests.status` (a CHECK-constrained, fully-known
five-value lifecycle since migration 005), `rtl_commands.command_type` and
`rtl_commands.state` carry no CHECK constraint (migration 008) — this
tranche's vocabulary is a single value each, and a future transport
tranche adding SENT/ACK/FAILED states or new command types extends this
module, not a migration.
"""
from __future__ import annotations

#: The only command type this tranche writes. A programming request always
#: produces exactly one PROGRAM_RTL command (RTL-IF-1); future tranches may
#: add further types (e.g. a deactivation or forwarding command) as those
#: features grow their own transport story.
COMMAND_TYPE_PROGRAM_RTL = "PROGRAM_RTL"

#: The initial (and, this tranche, only) lifecycle state. A future
#: transport tranche owns the transitions out of it — SENT, ACK, FAILED, or
#: whatever names that work settles on.
STATE_QUEUED = "QUEUED"
