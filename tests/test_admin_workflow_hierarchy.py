"""UI-5 presentation contracts for administrative workflows."""
from __future__ import annotations

from callbacks.device_register import _review_summary
from components.user_form_drawer import (
    USER_CANCEL_BTN,
    USER_CONFIRM_BTN,
    USER_DISMISS_BTN,
    USER_IDENTIFIER_ID,
    USER_ROLE_ID,
    USER_STATUS_ID,
    USER_USERNAME_ID,
)
from components.user_form_drawer import user_form_drawer
from pages import device_register, user_admin
from tests.dash_tree import find_by_class, find_by_id, text_of


def test_user_page_keeps_identity_action_filters_and_inventory():
    page = user_admin.layout()
    heading = find_by_class(page, "admin-page-heading")[0]
    assert "User Administration" in text_of(heading)
    assert find_by_id(heading, "user-admin-add-btn") is not None
    assert find_by_id(page, "user-admin-search") is not None
    assert find_by_id(page, "user-admin-status-filter") is not None
    assert find_by_id(page, "user-admin-table") is not None


def test_user_inventory_reuses_responsive_entity_table():
    page = user_admin.layout()
    wrappers = find_by_class(page, "entity-table-wrapper--responsive")
    assert len(wrappers) == 1
    assert "entity-table-wrapper--administrative-axis" in wrappers[0].className
    table = find_by_id(page, "user-admin-table")
    assert [column["id"] for column in table.columns] == [
        "username", "identifier", "role", "status", "actions"
    ]
    assert table.markdown_options == {"link_target": "_self"}


def test_drawer_fields_and_actions_are_preserved():
    drawer = user_form_drawer()
    for field_id in (USER_USERNAME_ID, USER_IDENTIFIER_ID, USER_ROLE_ID, USER_STATUS_ID):
        assert find_by_id(drawer, field_id) is not None
    for action_id in (USER_CONFIRM_BTN, USER_CANCEL_BTN, USER_DISMISS_BTN):
        assert find_by_id(drawer, action_id) is not None
    username_label = next(
        label for label in find_by_class(drawer, "user-form-drawer__field-label")
        if "Username" in text_of(label)
    )
    assert find_by_class(username_label, "required-marker")
    assert "Optional" in text_of(drawer)


def test_role_and_status_remain_distinct_neutral_controls():
    drawer = user_form_drawer()
    role = find_by_id(drawer, USER_ROLE_ID)
    status = find_by_id(drawer, USER_STATUS_ID)
    assert [option["value"] for option in role.options] == [
        "administrator", "technician", "general"
    ]
    assert [option["value"] for option in status.options] == ["active", "inactive"]


def test_registration_marks_only_validated_requirements():
    page = device_register.layout()
    form = find_by_id(page, "device-register-form")
    required_text = text_of(form)
    assert "RTL UID / Device Code" in required_text
    assert "Plant" in required_text
    assert "Transformer" in required_text
    assert len(find_by_class(form, "required-marker")) == 4  # legend + three fields
    # `field__label` since the form moved onto components.field; the
    # guarantee is unchanged — Status is the one field not marked required.
    status_label = next(
        label for label in find_by_class(form, "field__label")
        if "Status" in text_of(label)
    )
    assert not find_by_class(status_label, "required-marker")
    # REGISTER-UX-1: required is marked (the asterisk above) and validated
    # by the page, but not by the browser. Dash outlines
    # `input.dash-input:invalid` in red, so browser-`required` drew an empty
    # field as an error before the operator had done anything.
    assert not getattr(find_by_id(page, "device-register-code"), "required", None)


def test_registration_control_contract_is_unchanged():
    page = device_register.layout()
    assert find_by_id(page, "device-register-transformer").disabled is True
    assert find_by_id(page, "device-register-status").value == "active"
    assert find_by_id(page, "device-register-review-btn") is not None
    assert find_by_id(page, "device-register-submit-btn") is not None
    assert find_by_id(page, "device-register-edit-btn") is not None


def test_review_is_truthful_application_record_summary():
    page = device_register.layout()
    review = find_by_id(page, "device-register-review")
    assert "application device record" in text_of(review)
    summary = text_of(_review_summary("29017", "Plant A", "T1", "active"))
    for fact in ("RTL UID / Device Code", "Plant", "Transformer", "Administrative status"):
        assert fact in summary
    forbidden_claims = ("installed", "programmed", "commissioned", "communicating")
    assert not any(claim in summary.lower() for claim in forbidden_claims)
