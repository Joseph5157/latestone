"""RTL command read API (RTL-IF-1).

Command *creation* is not here: it happens inside
`rtl_programming_service.record_request`, atomically with the programming
request and its audit row, because it is that call's responsibility, not a
standalone operation. This module exists only for the minimum read
capability RTL-IF-1 needs — resolving a programming request's corresponding
command for tests and future transport work — never a command-management
UI (explicitly out of scope for this tranche).
"""
from __future__ import annotations

from repositories import plant_monitoring_repository as repo
from repositories.plant_monitoring_repository import CommandRecord


def get_command_for_request(request_id: int) -> CommandRecord | None:
    """Resolve a programming request's single corresponding command, or None."""
    return repo.get_command_for_request(request_id)


__all__ = ["CommandRecord", "get_command_for_request"]
