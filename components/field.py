"""Label, control, help text and error as one unit.

The application assembled these by hand 25 times across nine files, and the
wiring drifted: eight labels were associated with nothing, and several that
carried `htmlFor` pointed at a `dcc.Dropdown` — which renders a `<div>`, and
a `<label for>` cannot target a div. Both failures look correct in the source
and do nothing in the browser, which is exactly the kind of defect a helper
exists to prevent.

What this stack allows:

- `dcc.Input` renders a real `<input id=…>`, so `htmlFor` genuinely works.
  That is `labelable=True`, the default.
- `dcc.Dropdown` and `DatePickerRange` render composites, so their accessible
  name has to come from a wrapper: `labelable=False` puts the control in a
  `role="group"` named by the label.

What it does not allow: `aria-invalid` and `aria-describedby` on the control
itself, which is how shadcn's Field ties an error to its input. Every `dcc.*`
component rejects arbitrary `aria-*` props, and `dash.html` ships no `Input`
to fall back to. `role="alert"` on the error slot is the reachable half — it
announces the message when it appears, which is the moment it is needed.
"""
from __future__ import annotations

from dash import html


def field(
    label: str,
    control,
    *,
    control_id: str,
    description: str | None = None,
    error_id: str | None = None,
    required: bool = False,
    labelable: bool = True,
) -> html.Div:
    """One form field.

    control_id: the control's own id. Used as the label's target when the
        control is labelable, and to derive the label's id when it is not.
    labelable: whether `<label for>` reaches the control. True for dcc.Input;
        False for dcc.Dropdown and the date pickers, whose rendered markup a
        label cannot target.
    error_id: id of the (initially empty) slot a validation callback writes
        into. Omit for a field with no per-field validation.
    """
    label_text = [label]
    if required:
        label_text.append(html.Span(" *", className="required-marker"))

    label_id = f"{control_id}-label"
    label_node = html.Label(
        label_text,
        id=label_id,
        className="field__label",
        # A dead `for` is worse than none: it reads as solved and is not.
        htmlFor=control_id if labelable else None,
    )

    if labelable:
        control_node = control
    else:
        control_node = html.Div(
            control,
            role="group",
            **{"aria-labelledby": label_id},
        )

    children = [label_node, control_node]
    if description:
        children.append(html.P(description, className="field__description"))
    if error_id:
        # role="alert" so the message is announced when a callback fills it,
        # matching the login form's existing error behaviour.
        children.append(html.P(id=error_id, className="field__error", role="alert"))

    return html.Div(children, className="field")
