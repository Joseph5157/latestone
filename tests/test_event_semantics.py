"""EVT-CONSUME-1I pure tests — the event-semantics mapping layer.

No database. Database-backed consumption (repository scoping, end-to-end
notification derivation) lives in test_event_consumption_db.py.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from config import notifications as notifications_cfg
from config.events import (
    EVENT_TYPE_BATTERY_LOW,
    EVENT_TYPE_CHECK_IN,
    EVENT_TYPE_INVALID_UID,
    EVENT_TYPE_POWER_DOWN,
    EVENT_TYPE_SENSOR_ERROR,
    EVENT_TYPE_STARTUP,
)
from services import event_semantics as sem
from services.notification_service import NotificationRow

NOW = datetime(2026, 8, 25, 12, 0, 0, tzinfo=timezone.utc)


@dataclass(frozen=True)
class FakeEvent:
    event_id: int
    device_id: str | None = None
    transformer_id: str | None = None
    reported_uid: str | None = None
    event_type: str = EVENT_TYPE_BATTERY_LOW
    event_ts: datetime = NOW
    temperature: float | None = None
    battery_voltage: float | None = None


# ---------------------------------------------------------------------------
# EVT-D1 — the mapping is the single owner of meaning
# ---------------------------------------------------------------------------


class TestMapping:
    def test_every_mapped_category_exists_in_config(self):
        """The mapping binds to spec-frozen labels; a typo'd key must fail
        here, not render an empty label."""
        for event_type in sem.mapped_event_types():
            key = sem.semantics_for(event_type).notification_category_key
            if key is not None:
                assert notifications_cfg.get_category(key) is not None

    @pytest.mark.parametrize(
        "event_type,category",
        [
            (EVENT_TYPE_BATTERY_LOW, "battery_alarm"),
            (EVENT_TYPE_POWER_DOWN, "power_down"),
            (EVENT_TYPE_SENSOR_ERROR, "sensor_error"),
            (EVENT_TYPE_STARTUP, "startup_checkin"),
            (EVENT_TYPE_CHECK_IN, "startup_checkin"),
        ],
    )
    def test_notification_backed_types_map_to_spec_categories(
        self, event_type, category
    ):
        assert (
            sem.semantics_for(event_type).notification_category_key == category
        )

    def test_invalid_uid_has_no_notification_category(self):
        assert sem.semantics_for(EVENT_TYPE_INVALID_UID).notification_category_key is None

    def test_high_temperature_and_vibration_have_no_mapping(self):
        """Client-clarification items are structurally absent, not disabled."""
        for unmapped in ("high_temperature", "vibration_event"):
            s = sem.semantics_for(unmapped)
            assert s.notification_category_key is None
            assert s.is_reportable_alarm is False
            assert s.forwarding_relevant is False

    def test_unknown_open_vocabulary_types_are_inert(self):
        """INGEST-D7 open vocabulary: stored unknowns never gain behaviour
        silently."""
        s = sem.semantics_for("some_future_type")
        assert s == sem.EventSemantics(None, False, False)

    def test_forwarding_relevant_is_classification_only(self):
        """EVT-D7 frozen: which types COULD be forwarded is recorded; who
        receives them is not decided anywhere in this module."""
        assert sem.semantics_for(EVENT_TYPE_STARTUP).forwarding_relevant is True
        assert sem.semantics_for(EVENT_TYPE_CHECK_IN).forwarding_relevant is True
        assert sem.semantics_for(EVENT_TYPE_BATTERY_LOW).forwarding_relevant is False

    def test_every_mapped_type_has_a_human_display_label(self):
        """A consumer naming an event type must not spell the name itself.

        Without a label here, Command Center's event rows and the
        Notification Center would each invent their own word for the same
        persisted type, which is the drift EVT-D1 exists to prevent.
        """
        for event_type in sem.mapped_event_types():
            label = sem.semantics_for(event_type).display_label
            assert label, f"{event_type} has no display label"
            assert label != event_type, (
                f"{event_type}'s label is still the raw type name"
            )

    @pytest.mark.parametrize(
        "event_type,label",
        [
            (EVENT_TYPE_BATTERY_LOW, "Battery Low"),
            (EVENT_TYPE_POWER_DOWN, "Power Down"),
            (EVENT_TYPE_SENSOR_ERROR, "Sensor Error"),
            (EVENT_TYPE_STARTUP, "Startup"),
            (EVENT_TYPE_CHECK_IN, "Check-In"),
            (EVENT_TYPE_INVALID_UID, "Invalid UID"),
        ],
    )
    def test_display_labels_use_the_event_vocabulary(self, event_type, label):
        """The EVENT's own vocabulary, not the notification CATEGORY's.

        `battery_low` is labelled "Battery Low" here and "Battery Alarm" as a
        notification category; both are correct for their own surface, and
        flattening them would misname one.
        """
        assert sem.semantics_for(event_type).display_label == label

    def test_display_label_for_falls_back_to_the_raw_type(self):
        """INGEST-D7 open vocabulary: an unmapped type that somehow reaches a
        display is named honestly rather than hidden or invented."""
        assert sem.display_label_for("some_future_type") == "some_future_type"

    def test_no_forwarding_recipient_logic_exists(self):
        """EVT-D7 frozen: no recipient-resolution function of any kind."""
        public_names = [n.lower() for n in dir(sem) if not n.startswith("_")]
        assert not any("recipient" in n for n in public_names)

    def test_reportable_alarms_are_exactly_the_three_alarm_types(self):
        reportable = {
            t for t in sem.mapped_event_types()
            if sem.semantics_for(t).is_reportable_alarm
        }
        assert reportable == {
            EVENT_TYPE_BATTERY_LOW,
            EVENT_TYPE_POWER_DOWN,
            EVENT_TYPE_SENSOR_ERROR,
        }

    def test_no_threshold_constants_in_the_semantics_layer(self):
        """EVT-D4: battery/temp classifications arrive pre-made from the
        device; consumers must contain no numeric rule like `< 3.75`."""
        source = Path(sem.__file__).read_text(encoding="utf-8")
        assert "3.75" not in source
        assert "3.61" not in source

    def test_thirty_days_belongs_to_the_alarm_report_only(self):
        """Review correction: the 30-day horizon is the REP-01 report
        window, never a notification-retention rule."""
        assert sem.ALARM_REPORT_WINDOW == timedelta(days=30)
        assert not hasattr(sem, "NOTIFICATION_WINDOW")

    def test_notification_query_bound_is_technical_not_temporal(self):
        """The only Notification Center bound is a row-count capacity —
        no expiry can hide behind it."""
        assert isinstance(sem.NOTIFICATION_QUERY_LIMIT, int)
        assert sem.NOTIFICATION_QUERY_LIMIT > 0


# ---------------------------------------------------------------------------
# FS-ALARM-1 / BR009 — the two-way client-facing alarm label split
# ---------------------------------------------------------------------------


class TestBR009AlarmLabels:
    """BR009: 'Low battery notification is Battery Alarm; other alarms are
    sent as Comms Alarm.' Exactly two client-facing alarm labels exist."""

    def test_battery_low_is_battery_alarm(self):
        assert sem.alarm_label_for_event_type(EVENT_TYPE_BATTERY_LOW) == "Battery Alarm"

    def test_power_down_is_comms_alarm(self):
        assert sem.alarm_label_for_event_type(EVENT_TYPE_POWER_DOWN) == "Comms Alarm"

    def test_sensor_error_is_comms_alarm(self):
        assert sem.alarm_label_for_event_type(EVENT_TYPE_SENSOR_ERROR) == "Comms Alarm"

    def test_only_two_labels_exist_across_every_reportable_alarm_type(self):
        labels = {
            sem.alarm_label_for_event_type(t)
            for t in sem.reportable_alarm_event_types()
        }
        assert labels == {"Battery Alarm", "Comms Alarm"}

    def test_underlying_event_type_remains_distinguishable_from_the_label(self):
        """BR009 collapses the LABEL, never the underlying persisted fact:
        power_down and sensor_error still have their own display_label and
        their own notification_category_key."""
        assert sem.display_label_for(EVENT_TYPE_POWER_DOWN) == "Power Down"
        assert sem.display_label_for(EVENT_TYPE_SENSOR_ERROR) == "Sensor Error"
        assert (
            sem.semantics_for(EVENT_TYPE_POWER_DOWN).notification_category_key
            == "power_down"
        )
        assert (
            sem.semantics_for(EVENT_TYPE_SENSOR_ERROR).notification_category_key
            == "sensor_error"
        )

    def test_non_alarm_types_raise_rather_than_invent_a_label(self):
        for event_type in (EVENT_TYPE_STARTUP, EVENT_TYPE_CHECK_IN, EVENT_TYPE_INVALID_UID):
            with pytest.raises(ValueError):
                sem.alarm_label_for_event_type(event_type)

    def test_summary_labels_collapse_power_down_and_sensor_error(self):
        """Regression: the summary line must walk the SAME collapsed label
        each row's notification_type actually carries, or a power_down/
        sensor_error row's count silently vanishes from the summary while
        still appearing in the table (caught in browser verification)."""
        labels = sem.summary_notification_labels()
        assert "Comms Alarm" in labels
        assert "Power Down" not in labels
        assert "Sensor Error" not in labels
        assert labels.count("Comms Alarm") == 1   # never duplicated
        assert "Battery Alarm" in labels
        assert "Startup / Check-In" in labels      # non-alarm label untouched

    def test_summary_labels_preserve_config_category_order(self):
        from config.notifications import all_categories

        labels = sem.summary_notification_labels()
        # >24h No Data, then Battery Alarm, then Comms Alarm (power_down's
        # slot — sensor_error's later slot is where the dedupe drops out).
        config_order = [c.label for c in all_categories()]
        assert labels[0] == config_order[0]
        assert labels[1] == "Battery Alarm"
        assert labels[2] == "Comms Alarm"


# ---------------------------------------------------------------------------
# EVT-D8/D9 — notification derivation and collapsing
# ---------------------------------------------------------------------------


class TestBuildEventNotifications:
    def test_rows_are_notificationrow_instances_with_stable_keys(self):
        rows = sem.build_event_notifications(
            [FakeEvent(event_id=1, device_id="d1")]
        )
        assert len(rows) == 1
        row = rows[0]
        assert isinstance(row, NotificationRow)
        assert row.key == f"battery_alarm:d1"

    def test_collapses_to_latest_per_device_and_category(self):
        events = [
            FakeEvent(event_id=i, device_id="d1", battery_voltage=3.5 + i / 100)
            for i in range(1, 4)  # three battery_low events
        ]
        rows = sem.build_event_notifications(events)

        assert len(rows) == 1
        row = rows[0]
        assert row.key == "battery_alarm:d1"
        assert "3 event(s)" in row.detail
        assert row.occurred_at == events[-1].event_ts   # latest wins

    def test_same_device_different_categories_do_not_merge(self):
        events = [
            FakeEvent(event_id=1, device_id="d1", event_type=EVENT_TYPE_BATTERY_LOW),
            FakeEvent(event_id=2, device_id="d1", event_type=EVENT_TYPE_POWER_DOWN),
        ]
        keys = {r.key for r in sem.build_event_notifications(events)}
        assert keys == {"battery_alarm:d1", "power_down:d1"}

    def test_startup_and_checkin_share_the_spec_category(self):
        events = [
            FakeEvent(event_id=1, device_id="d1", event_type=EVENT_TYPE_STARTUP),
            FakeEvent(event_id=2, device_id="d1", event_type=EVENT_TYPE_CHECK_IN),
        ]
        rows = sem.build_event_notifications(events)
        assert len(rows) == 1
        assert rows[0].key == "startup_checkin:d1"
        assert rows[0].notification_type == "Startup / Check-In"

    def test_startup_checkin_is_never_relabelled_as_an_alarm(self):
        """Task item 6: BR009 governs alarms only — a check-in is never a
        'Comms Alarm' regardless of how the alarm-label collapse works."""
        rows = sem.build_event_notifications(
            [FakeEvent(event_id=1, device_id="d1", event_type=EVENT_TYPE_CHECK_IN)]
        )
        assert rows[0].notification_type not in ("Battery Alarm", "Comms Alarm")
        assert rows[0].event_id is None            # non-alarm: no ack lifecycle
        assert rows[0].acknowledgement_state is None

    def test_power_down_notification_type_is_comms_alarm_per_br009(self):
        rows = sem.build_event_notifications(
            [FakeEvent(event_id=1, device_id="d1", event_type=EVENT_TYPE_POWER_DOWN)]
        )
        assert rows[0].notification_type == "Comms Alarm"

    def test_sensor_error_notification_type_is_comms_alarm_per_br009(self):
        rows = sem.build_event_notifications(
            [FakeEvent(event_id=1, device_id="d1", event_type=EVENT_TYPE_SENSOR_ERROR)]
        )
        assert rows[0].notification_type == "Comms Alarm"

    def test_battery_low_notification_type_is_battery_alarm(self):
        rows = sem.build_event_notifications(
            [FakeEvent(event_id=1, device_id="d1", event_type=EVENT_TYPE_BATTERY_LOW)]
        )
        assert rows[0].notification_type == "Battery Alarm"

    def test_power_down_and_sensor_error_share_a_label_but_not_a_row(self):
        """BR009 collapses the LABEL text only; the two alarm types must
        still produce two distinct, separately-acknowledgeable rows."""
        events = [
            FakeEvent(event_id=1, device_id="d1", event_type=EVENT_TYPE_POWER_DOWN),
            FakeEvent(event_id=2, device_id="d1", event_type=EVENT_TYPE_SENSOR_ERROR),
        ]
        rows = sem.build_event_notifications(events)
        assert {r.key for r in rows} == {"power_down:d1", "sensor_error:d1"}
        assert all(r.notification_type == "Comms Alarm" for r in rows)

    def test_comms_alarm_detail_still_names_the_specific_underlying_event(self):
        """Task item 4: 'Power Down' must remain visible as detail even
        though the headline notification label now reads Comms Alarm."""
        power_down_row = sem.build_event_notifications(
            [FakeEvent(event_id=1, device_id="d1", event_type=EVENT_TYPE_POWER_DOWN)]
        )[0]
        sensor_error_row = sem.build_event_notifications(
            [FakeEvent(event_id=1, device_id="d1", event_type=EVENT_TYPE_SENSOR_ERROR)]
        )[0]
        assert power_down_row.detail.startswith("Power Down — ")
        assert sensor_error_row.detail.startswith("Sensor Error — ")

    def test_battery_alarm_detail_also_names_its_specific_event(self):
        row = sem.build_event_notifications(
            [FakeEvent(event_id=1, device_id="d1", event_type=EVENT_TYPE_BATTERY_LOW)]
        )[0]
        assert row.detail.startswith("Battery Low — ")

    def test_battery_voltage_displayed_but_never_classifies(self):
        """EVT-D4: voltage is display payload; the row exists because the
        DEVICE said battery_low — whatever the number is."""
        rows = sem.build_event_notifications(
            [FakeEvent(event_id=1, device_id="d1", battery_voltage=4.10)],
        )
        assert len(rows) == 1                       # still a Battery Alarm row
        assert "battery 4.10 V" in rows[0].detail

    def test_old_events_are_not_excluded_by_the_report_horizon(self):
        """Review correction: an otherwise relevant event older than 30
        days must NOT vanish merely because REP-01 is a 30-day report.
        The Notification Center has no expiry."""
        old = FakeEvent(
            event_id=1,
            device_id="d1",
            event_ts=NOW - sem.ALARM_REPORT_WINDOW - timedelta(days=60),
        )
        rows = sem.build_event_notifications([old])

        assert len(rows) == 1
        assert rows[0].occurred_at == old.event_ts

    def test_unregistered_uid_hidden_by_default(self):
        """EVT-D5 default: nobody sees unregistered UIDs unless explicitly
        granted (admin-only caller gate)."""
        events = [FakeEvent(event_id=1, reported_uid="99999",
                            event_type=EVENT_TYPE_INVALID_UID)]
        assert sem.build_event_notifications(events) == []

    def test_unregistered_uid_rows_key_on_reported_uid(self):
        """EVT-D8 refinement: unknown UIDs collapse per UID, never into one
        global row; no href, no fake device entity."""
        events = [
            FakeEvent(event_id=1, reported_uid="99999", event_type=EVENT_TYPE_INVALID_UID),
            FakeEvent(event_id=2, reported_uid="99999", event_type=EVENT_TYPE_INVALID_UID),
            FakeEvent(event_id=3, reported_uid="88888", event_type=EVENT_TYPE_INVALID_UID),
        ]
        rows = sem.build_event_notifications(events, include_unregistered=True)

        assert sorted(r.key for r in rows) == [
            "unregistered_uid:88888", "unregistered_uid:99999"
        ]
        rogue = next(r for r in rows if r.key == "unregistered_uid:99999")
        assert rogue.entity_type == "Unregistered UID"
        assert rogue.entity_label == "99999"
        assert rogue.href == ""                      # no device page exists
        assert "2 event(s)" in rogue.detail

    def test_deterministic_ordering_by_stable_key(self):
        events = [
            FakeEvent(event_id=1, device_id="d2"),
            FakeEvent(event_id=2, device_id="d1"),
        ]
        keys = [r.key for r in sem.build_event_notifications(events)]
        assert keys == sorted(keys)


# ---------------------------------------------------------------------------
# EVT-D6 — typed alarm-report projection contract
# ---------------------------------------------------------------------------


class TestAlarmEventProjections:
    @dataclass(frozen=True)
    class DeviceMeta:
        device_code: str
        firmware_version: str

    def test_one_projection_per_alarm_event(self):
        events = [
            FakeEvent(event_id=1, device_id="d1", transformer_id="t1"),
            FakeEvent(event_id=2, device_id="d1", transformer_id="t1"),
        ]
        projections = sem.alarm_event_projections(events)
        assert len(projections) == 2                 # reports stay per-event

    def test_non_alarm_types_are_excluded(self):
        events = [
            FakeEvent(event_id=1, device_id="d1", event_type=EVENT_TYPE_STARTUP,
                      transformer_id="t1"),
        ]
        assert sem.alarm_event_projections(events) == []

    def test_taxonomy_fields_stay_none_per_r2d2_precedent(self):
        p = sem.alarm_event_projections(
            [FakeEvent(event_id=1, device_id="d1", transformer_id="t1")]
        )[0]
        assert p.ou is None and p.zone is None and p.sector is None
        assert p.cnc is None and p.feeder_name is None

    def test_alarm_at_is_the_source_occurrence_time(self):
        """EVT-D9: 'Alarm Date & Time' maps to event_ts, never created_at."""
        ts = NOW - timedelta(hours=3)
        p = sem.alarm_event_projections(
            [FakeEvent(event_id=1, device_id="d1", transformer_id="t1",
                       event_ts=ts)]
        )[0]
        assert p.alarm_at == ts

    def test_device_metadata_enriches_uid_firmware_transformer(self):
        meta = {"d1": self.DeviceMeta(device_code="29101", firmware_version="v7")}
        p = sem.alarm_event_projections(
            [FakeEvent(event_id=1, device_id="d1", transformer_id="t1",
                       temperature=85.0, battery_voltage=3.52)],
            device_metadata=meta,
        )[0]
        assert p.uid == "29101"
        assert p.firmware_version == "v7"
        assert p.temperature == 85.0
        assert p.battery_voltage == 3.52
        assert p.transformer_id == "t1"

    def test_unknown_metadata_projects_with_none_rather_than_dropping(self):
        p = sem.alarm_event_projections(
            [FakeEvent(event_id=1, device_id="ghost", transformer_id="t1")]
        )[0]
        assert p.uid is None and p.firmware_version is None

    def test_payload_measurements_carry_no_classification_power(self):
        """A sensor_error with a perfectly normal temperature still
        projects as an alarm — the type IS the classification, regardless
        of the reading. BR009: its client-facing label is Comms Alarm."""
        p = sem.alarm_event_projections(
            [FakeEvent(event_id=1, device_id="d1", transformer_id="t1",
                       event_type=EVENT_TYPE_SENSOR_ERROR, temperature=21.0)]
        )[0]
        assert p.alarm_label == "Comms Alarm"

    def test_projection_is_bounded_by_the_rep01_thirty_day_horizon(self):
        """EVT-D6: the ONLY 30-day bound lives here — the alarm report."""
        recent = FakeEvent(event_id=1, device_id="d1", event_ts=NOW - timedelta(days=10))
        old = FakeEvent(
            event_id=2, device_id="d1", event_ts=NOW - timedelta(days=31)
        )

        projections = sem.alarm_event_projections([recent, old], now=NOW)

        assert [p.event_id for p in projections] == [recent.event_id]

    def test_projection_horizon_is_evaluated_against_the_supplied_clock(self):
        """The bound uses the caller's reference time, not wall-clock now —
        deterministic and testable."""
        event = FakeEvent(
            event_id=1, device_id="d1", event_ts=NOW - timedelta(days=31)
        )

        earlier_reference = NOW - timedelta(days=5)   # cutoff becomes NOW-35
        projections = sem.alarm_event_projections([event], now=earlier_reference)

        assert len(projections) == 1

    def test_deterministic_ordering_by_occurrence_then_id(self):
        events = [
            FakeEvent(event_id=2, device_id="d1", event_ts=NOW),
            FakeEvent(event_id=1, device_id="d1", event_ts=NOW - timedelta(hours=1)),
            FakeEvent(event_id=3, device_id="d1", event_ts=NOW),
        ]
        order = [(p.alarm_at, p.event_id)
                 for p in sem.alarm_event_projections(events)]
        assert order == sorted(order)
