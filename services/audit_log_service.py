"""Read-only Administration audit-log projection."""
from __future__ import annotations

import logging

from repositories import plant_monitoring_repository as repo
from repositories.plant_monitoring_repository import AuditLogRecord

logger = logging.getLogger(__name__)

DEFAULT_AUDIT_LOG_LIMIT = 500


class AuditLogViewerError(Exception):
    """A safe failure to load the audit-log viewer."""


def recent_audit_log(*, limit: int = DEFAULT_AUDIT_LOG_LIMIT) -> list[AuditLogRecord]:
    """Load the existing audit trail for read-only presentation."""
    try:
        return repo.list_audit_log(limit=limit)
    except Exception as exc:
        logger.exception("Failed to load Administration audit log")
        raise AuditLogViewerError(
            "Audit log could not be loaded. Please try again."
        ) from exc


__all__ = [
    "AuditLogViewerError",
    "DEFAULT_AUDIT_LOG_LIMIT",
    "recent_audit_log",
]
