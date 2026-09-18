"""One place that wires a label to its control.

The application hand-assembled 25 labels across nine files, and eight of them
were associated with nothing. Worse, several that looked associated were not:
`htmlFor="device-register-plant"` points at a `dcc.Dropdown`, which renders a
`<div>`, and a label cannot be `for` a div.

What Dash allows, and what it does not:

- `dcc.Input` renders a real `<input id=…>`, so `htmlFor` works.
- `dcc.Dropdown` renders a div-based combobox, so `htmlFor` is inert. Its
  accessible name has to come from a wrapper, because…
- `dcc.*` components reject arbitrary `aria-*` props outright (verified:
  `dcc.Input(**{"aria-describedby": …})` raises TypeError), and `dash.html`
  ships no `Input` to fall back to.

So `aria-invalid` and `aria-describedby` on the control itself — shadcn's
Field pattern — are not reachable in this stack without replacing every form
control. `role="alert"` on the error is: it announces the message at the
moment it appears, which is the moment that matters.
"""
from dash import dcc, html

from components.field import field
from tests.dash_tree import find_by_exact_class, text_of, walk


def label_of(node):
    return next(n for n in walk(node) if isinstance(n, html.Label))


class TestNativeControl:
    def test_the_label_points_at_the_control(self):
        f = field("RTL UID", dcc.Input(id="rtl-uid"), control_id="rtl-uid")
        assert label_of(f).htmlFor == "rtl-uid"

    def test_the_control_is_rendered_as_given(self):
        control = dcc.Input(id="rtl-uid")
        assert control in list(walk(field("RTL UID", control, control_id="rtl-uid")))

    def test_a_required_field_is_marked_in_the_label(self):
        f = field("RTL UID", dcc.Input(id="rtl-uid"), control_id="rtl-uid", required=True)
        assert "*" in text_of(label_of(f))


class TestUnlabelableControl:
    """`htmlFor` at a `dcc.Dropdown` is the failure this guards: it looks
    correct in the source and associates nothing in the browser.
    """

    def dropdown_field(self, **kwargs):
        return field(
            "Plant",
            dcc.Dropdown(id="plant"),
            control_id="plant",
            labelable=False,
            **kwargs,
        )

    def test_no_dead_html_for(self):
        assert label_of(self.dropdown_field()).htmlFor is None

    def test_the_label_names_a_group_around_the_control(self):
        f = self.dropdown_field()
        label = label_of(f)
        group = next(
            n for n in walk(f) if getattr(n, "role", None) == "group"
        )
        assert label.id
        assert getattr(group, "aria-labelledby") == label.id

    def test_the_control_still_renders_inside_the_group(self):
        f = self.dropdown_field()
        group = next(n for n in walk(f) if getattr(n, "role", None) == "group")
        assert any(isinstance(n, dcc.Dropdown) for n in walk(group))


class TestErrors:
    def test_the_error_slot_announces_itself_when_filled(self):
        """The message appears after a submit, so it has to interrupt — the
        pattern login already uses for its own error."""
        f = field(
            "RTL UID", dcc.Input(id="rtl-uid"),
            control_id="rtl-uid", error_id="rtl-uid-error",
        )
        error = next(n for n in walk(f) if getattr(n, "id", None) == "rtl-uid-error")
        assert error.role == "alert"

    def test_the_slot_is_empty_until_a_callback_fills_it(self):
        f = field(
            "RTL UID", dcc.Input(id="rtl-uid"),
            control_id="rtl-uid", error_id="rtl-uid-error",
        )
        error = next(n for n in walk(f) if getattr(n, "id", None) == "rtl-uid-error")
        assert not error.children

    def test_a_field_without_an_error_slot_renders_none(self):
        f = field("RTL UID", dcc.Input(id="rtl-uid"), control_id="rtl-uid")
        assert find_by_exact_class(f, "field__error") == []


class TestDescription:
    def test_help_text_renders_under_the_control(self):
        f = field(
            "Transformer", dcc.Dropdown(id="tx"), control_id="tx", labelable=False,
            description="Choose a plant first to load its transformers.",
        )
        assert "Choose a plant first" in text_of(f)

    def test_description_is_optional(self):
        f = field("RTL UID", dcc.Input(id="rtl-uid"), control_id="rtl-uid")
        assert find_by_exact_class(f, "field__description") == []


class TestHint:
    def test_hint_sits_directly_after_the_control(self):
        control = dcc.Input(id="rtl-uid")
        f = field(
            "RTL UID", control, control_id="rtl-uid",
            error_id="rtl-uid-error", hint="5 digits", hint_id="rtl-uid-hint",
        )
        assert f.children[1] is control
        assert f.children[2].id == "rtl-uid-hint"
        assert f.children[2].children == "5 digits"
        assert f.children[3].id == "rtl-uid-error"

    def test_hint_is_never_an_alert(self):
        f = field("RTL UID", dcc.Input(id="u"), control_id="u", hint="x", hint_id="u-hint")
        assert getattr(f.children[2], "role", None) is None

    def test_hint_is_optional(self):
        f = field("RTL UID", dcc.Input(id="u"), control_id="u")
        assert find_by_exact_class(f, "field__hint") == []


class TestRegistrationFormMigration:
    def page(self):
        from pages.device_register import layout

        return layout()

    def test_no_label_claims_to_target_a_dropdown(self):
        """The three dropdown labels carried `htmlFor` at a div."""
        dropdown_ids = {
            n.id for n in walk(self.page()) if isinstance(n, dcc.Dropdown)
        }
        for label in (n for n in walk(self.page()) if isinstance(n, html.Label)):
            assert getattr(label, "htmlFor", None) not in dropdown_ids

    def test_every_input_still_has_a_working_label(self):
        page = self.page()
        input_ids = {n.id for n in walk(page) if isinstance(n, dcc.Input)}
        targeted = {
            getattr(n, "htmlFor", None)
            for n in walk(page)
            if isinstance(n, html.Label)
        }
        assert input_ids <= targeted

    def test_the_per_field_errors_survive_with_their_ids(self):
        """Three callbacks write to these; renaming them would break
        validation silently."""
        ids = {getattr(n, "id", None) for n in walk(self.page())}
        assert {
            "device-register-code-error",
            "device-register-plant-error",
            "device-register-transformer-error",
        } <= ids
