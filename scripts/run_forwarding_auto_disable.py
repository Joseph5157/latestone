"""Standalone entry point for the C08-AUTO-DISABLE-1 scheduled job (BR016).

Run this from an external scheduler — cron, a Railway scheduled job, or
similar — on whatever cadence the deployment chooses (every minute, every
15 minutes, hourly). Never call this from a timer embedded inside a Dash/
Gunicorn worker process: see the "Scheduler architecture decision" in
docs/context/ACTIVE_GATE.md for why (duplicate/racing attempts across
multiple worker processes). The underlying service call is idempotent, so
repeat or overlapping invocations are safe either way — see
services/forwarding_auto_disable_service.py's module docstring.

Usage:
    python -m scripts.run_forwarding_auto_disable
"""
from __future__ import annotations

import logging
import sys

from config.logging_config import configure_logging
from services import forwarding_auto_disable_service as service

logger = logging.getLogger(__name__)


def main() -> int:
    configure_logging()
    result = service.apply_auto_disable()
    if result.ran:
        logger.info(
            "Auto-disable cutoff %s reached (local time %s); disabled %d account(s).",
            result.effective_cutoff,
            result.local_now,
            len(result.disabled_user_ids),
        )
    else:
        logger.info(
            "Auto-disable cutoff %s not yet reached (local time %s); no action taken.",
            result.effective_cutoff,
            result.local_now,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
