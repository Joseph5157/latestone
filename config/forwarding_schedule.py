"""BR016 auto-disable schedule constants (C08-AUTO-DISABLE-1).

Constants only, mirroring `config/commands.py` and `config/audit.py`. The
default cutoff is a development baseline (docs/context/ACTIVE_GATE.md,
C08-BASELINE-1), pending client confirmation — not a client-confirmed
production value.

`zoneinfo` is the standard library (Python 3.9+); no new dependency is
needed to reason about Africa/Johannesburg wall-clock time.
"""
from __future__ import annotations

from datetime import time
from zoneinfo import ZoneInfo

#: The one timezone this schedule is evaluated in. BR016 says "18:30 daily";
#: a bare `time(18, 30)` with no zone would silently mean whatever the
#: server's local time happens to be, which for a Railway-hosted process is
#: not guaranteed to be South African time.
TIMEZONE_NAME = "Africa/Johannesburg"
TIMEZONE = ZoneInfo(TIMEZONE_NAME)

#: Development baseline default (C-08): the application-owned cutoff, absent
#: an active same-day override. Never mutated at runtime — the *override* is
#: the only thing that varies, and it lives in the database
#: (forwarding_auto_disable_override), not here.
DEFAULT_CUTOFF_TIME: time = time(18, 30)
