"""The seven form labels the `field()` migration didn't reach.

Deliberately not migrated onto `components.field`: that helper carries its
own visual language (`.field`, `--card-spacing`-adjacent sizing, a fixed
description/error slot shape) built for a new form. These five surfaces —
the RTL manage drawer, the device toolbar, the device dashboard's custom
range, report center — each already have an established, page-tuned visual
language of their own (`manage-drawer__field-label`, `report-form__label`,
...). Swapping five surfaces onto one new class purely to fix a label
association would be a redesign wearing an accessibility-fix's clothes.

The fix here is therefore surgical: for a real `dcc.Input`, add the
`htmlFor` that was simply missing. For `dcc.Dropdown`, `DatePickerRange` and
`dcc.RadioItems` — none of which render a native, `<label for>`-targetable
element, and none of which accept `aria-*` props directly (verified:
`dcc.Dropdown(**{"aria-labelledby": ...})` raises `TypeError`) — the label
gets an id and the control is wrapped in `role="group"` /
`aria-labelledby`, exactly the pattern `components.field` already uses for
this stack's non-labelable controls. No visual class changes.
"""
from dash import dcc, html

from tests.dash_tree import find_by_id, walk


def label_for(tree, text_fragment):
    return next(
        n for n in walk(tree)
        if isinstance(n, html.Label) and text_fragment in "".join(
            c if isinstance(c, str) else "".join(walk_text(c)) for c in
            (n.children if isinstance(n.children, list) else [n.children])
        )
    )


def walk_text(node):
    for n in walk(node):
        if isinstance(n, str):
            yield n


def group_wrapping(tree, control_id):
    """The `role="group"` ancestor of the control with this id, if any."""
    control = find_by_id(tree, control_id)
    assert control is not None, f"no control with id {control_id!r}"
    for n in walk(tree):
        if getattr(n, "role", None) != "group":
            continue
        if control in list(walk(n)):
            return n
    return None


class TestManageDrawerProgramFields:
    """RTL UID, Transformer Name and RTL Master MSISDN are real
    `dcc.Input`s, so `htmlFor` is the whole fix."""

    def drawer(self):
        from components.device_manage_drawer import device_manage_drawer

        return device_manage_drawer()

    def test_rtl_uid_label_targets_its_input(self):
        from components.device_manage_drawer import PROGRAM_RTL_UID_ID

        label = label_for(self.drawer(), "RTL UID")
        assert label.htmlFor == PROGRAM_RTL_UID_ID

    def test_transformer_name_label_targets_its_input(self):
        from components.device_manage_drawer import PROGRAM_RTL_TRANSFORMER_ID

        label = label_for(self.drawer(), "Transformer Name")
        assert label.htmlFor == PROGRAM_RTL_TRANSFORMER_ID

    def test_msisdn_label_targets_its_input(self):
        from components.device_manage_drawer import PROGRAM_RTL_MSISDN_ID

        label = label_for(self.drawer(), "RTL Master MSISDN")
        assert label.htmlFor == PROGRAM_RTL_MSISDN_ID

    def test_visual_classes_are_unchanged(self):
        """A pure association fix — the drawer's own styling is untouched."""
        label = label_for(self.drawer(), "RTL UID")
        assert label.className == "manage-drawer__field-label"


class TestManageDrawerForwardingState:
    """A `dcc.Dropdown`: `htmlFor` cannot reach it, so the label names a
    group instead."""

    def test_dropdown_sits_inside_a_named_group(self):
        from components.device_manage_drawer import MSG_FWD_TOGGLE_ID, device_manage_drawer

        drawer = device_manage_drawer()
        label = label_for(drawer, "Forwarding State")
        group = group_wrapping(drawer, MSG_FWD_TOGGLE_ID)
        assert group is not None
        assert label.id
        assert getattr(group, "aria-labelledby") == label.id

    def test_no_dead_htmlfor(self):
        from components.device_manage_drawer import device_manage_drawer

        label = label_for(device_manage_drawer(), "Forwarding State")
        assert getattr(label, "htmlFor", None) is None


class TestDeviceAdminStatusFilter:
    def test_status_dropdown_sits_inside_a_named_group(self):
        from pages.device_admin import layout

        page = layout()
        label = label_for(page, "Status")
        group = group_wrapping(page, "device-admin-status-filter")
        assert group is not None
        assert label.id
        assert getattr(group, "aria-labelledby") == label.id

    def test_toolbar_classes_are_unchanged(self):
        from pages.device_admin import layout

        label = label_for(layout(), "Status")
        assert label.className == "device-admin-toolbar__label"


class TestDeviceDashboardCustomRange:
    def test_date_range_picker_sits_inside_a_named_group(self):
        from pages.device_dashboard import layout

        page = layout("plant-11-t1-d1")
        label = label_for(page, "Custom UTC range")
        group = group_wrapping(page, "custom-date-range")
        assert group is not None
        assert label.id
        assert getattr(group, "aria-labelledby") == label.id


class TestReportCenterDateRange:
    """`dcc.RadioItems` groups several controls under one label — the
    canonical case for `role="group"`, distinct from a single unlabelable
    control."""

    def test_radio_group_sits_inside_a_named_group(self):
        from pages.report_center import layout

        page = layout()
        label = label_for(page, "Date Range")
        group = group_wrapping(page, "report-period")
        assert group is not None
        assert label.id
        assert getattr(group, "aria-labelledby") == label.id

    def test_the_custom_range_picker_stays_inside_the_same_group(self):
        """report-custom-date-range is conditionally shown under the same
        Date Range heading; it must not need a second label."""
        from pages.report_center import layout

        page = layout()
        group = group_wrapping(page, "report-period")
        assert find_by_id(group, "report-custom-date-range") is not None
