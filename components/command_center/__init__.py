"""Command Center presentation family (ADR-008).

Fresh markup only. No imports from fleet_condition.py, needs_attention.py or
any other Fleet Overview presentation component - Command Center reuses the
service layer those pages read from (get_fleet_health, list_recent_device_events),
never their rendering.
"""
