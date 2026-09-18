"""The RTL UID format rule, in one place (ADR-022).

Functional Specification §4.4.1: "5-digit RTL UID, e.g. 29xxx". Exactly
five ASCII digits. No "29" prefix is required: the source labels that digit
string an example, not a rule. Registration and RTL programming both read
this module, so the two can never disagree about what a valid UID is.

`[0-9]`, not `\\d`: Python's `\\d` also matches non-ASCII digits (e.g.
full-width "２９０１７"), which no RTL can send.
"""
from __future__ import annotations

import re

UID_PATTERN = re.compile(r"^[0-9]{5}$")

UID_REQUIRED_MESSAGE = "Device code is required."
UID_FORMAT_MESSAGE = "Device code must be exactly 5 digits, e.g. 29017."


def uid_format_error(value: str | None) -> str | None:
    """Why `value` is not a valid UID once trimmed, or None if it is."""
    if not isinstance(value, str) or not value.strip():
        return UID_REQUIRED_MESSAGE
    if not UID_PATTERN.fullmatch(value.strip()):
        return UID_FORMAT_MESSAGE
    return None
