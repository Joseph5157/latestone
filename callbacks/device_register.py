"""Device Registration callbacks — form validation, review, prototype submit.

All operations are frontend-only. The "submit" action stores the registered
device in a dcc.Store (in-memory); it does not write to any database.
"""
from __future__ import annotations

import logging

from dash import Input, Output, State, no_update, html

from services import hierarchy_service

logger = logging.getLogger(__name__)


def _plant_options() -> list[dict]:
    """Plant options for the dropdown — reused by plant and equipment selectors."""
    return [
        {"label": p.name, "value": p.plant_id}
        for p in hierarchy_service.list_plants()
    ]


def _transformer_options(plant_id: str) -> list[dict]:
    """Transformer options for a given plant."""
    if not plant_id:
        return []
    return [
        {"label": t.transformer_code, "value": t.transformer_id}
        for t in hierarchy_service.list_transformers(plant_id)
    ]


def _validate_form(code: str, plant_id: str, transformer_id: str) -> dict[str, str]:
    """Validate required fields. Returns {field: error_message} dict.

    Empty dict means valid.
    """
    errors = {}
    if not code or not code.strip():
        errors["code"] = "Device code is required."
    elif len(code.strip()) > 10:
        errors["code"] = "Device code must be 10 characters or fewer."
    if not plant_id:
        errors["plant"] = "Please select a plant."
    if not transformer_id:
        errors["transformer"] = "Please select a transformer."
    return errors


def _review_summary(code: str, plant_label: str, transformer_label: str, status: str) -> html.Div:
    """Render the review summary before prototype submit."""
    return html.Div(
        className="device-register-review",
        children=[
            html.Div(
                className="device-register-review__row",
                children=[
                    html.Span("Device Code:", className="device-register-review__label"),
                    html.Span(code, className="device-register-review__value"),
                ],
            ),
            html.Div(
                className="device-register-review__row",
                children=[
                    html.Span("Plant:", className="device-register-review__label"),
                    html.Span(plant_label, className="device-register-review__value"),
                ],
            ),
            html.Div(
                className="device-register-review__row",
                children=[
                    html.Span("Transformer:", className="device-register-review__label"),
                    html.Span(transformer_label, className="device-register-review__value"),
                ],
            ),
            html.Div(
                className="device-register-review__row",
                children=[
                    html.Span("Status:", className="device-register-review__label"),
                    html.Span(status.capitalize(), className="device-register-review__value"),
                ],
            ),
        ],
    )


def register(app) -> None:
    """Register device registration callbacks on the Dash app."""

    @app.callback(
        Output("device-register-plant", "options"),
        Input("device-register-plant", "id"),
    )
    def _populate_plants(_id):
        try:
            return _plant_options()
        except Exception:
            logger.exception("Failed to populate plant options")
            return []

    @app.callback(
        Output("device-register-transformer", "options"),
        Output("device-register-transformer", "disabled"),
        Input("device-register-plant", "value"),
        prevent_initial_call=True,
    )
    def _populate_transformers(plant_id):
        try:
            options = _transformer_options(plant_id)
            return options, not options
        except Exception:
            logger.exception("Failed to populate transformers for %r", plant_id)
            return [], True

    @app.callback(
        Output("device-register-code-error", "children"),
        Output("device-register-plant-error", "children"),
        Output("device-register-transformer-error", "children"),
        Output("device-register-form", "style"),
        Output("device-register-review", "style"),
        Output("device-register-review-summary", "children"),
        Input("device-register-review-btn", "n_clicks"),
        State("device-register-code", "value"),
        State("device-register-plant", "value"),
        State("device-register-transformer", "value"),
        State("device-register-status", "value"),
        prevent_initial_call=True,
    )
    def _show_review(n_clicks, code, plant_id, transformer_id, status):
        errors = _validate_form(code, plant_id, transformer_id)
        if errors:
            return (
                errors.get("code", ""),
                errors.get("plant", ""),
                errors.get("transformer", ""),
                no_update,  # form stays visible
                no_update,  # review stays hidden
                no_update,
            )
        # Look up labels for review
        plant_label = next(
            (p.name for p in hierarchy_service.list_plants() if p.plant_id == plant_id),
            plant_id,
        )
        transformer_label = next(
            (t.transformer_code for t in hierarchy_service.list_transformers(plant_id)
             if t.transformer_id == transformer_id),
            transformer_id,
        )
        summary = _review_summary(code.strip(), plant_label, transformer_label, status)
        return (
            "",  # clear errors
            "",
            "",
            {"display": "none"},   # hide form
            {"display": "block"},   # show review
            summary,
        )

    @app.callback(
        Output("device-register-form", "style", allow_duplicate=True),
        Output("device-register-review", "style", allow_duplicate=True),
        Input("device-register-edit-btn", "n_clicks"),
        prevent_initial_call=True,
    )
    def _back_to_form(n_clicks):
        return {"display": "block"}, {"display": "none"}

    @app.callback(
        Output("device-register-form", "style", allow_duplicate=True),
        Output("device-register-review", "style", allow_duplicate=True),
        Output("device-register-success", "style"),
        Output("device-register-success-detail", "children"),
        Input("device-register-submit-btn", "n_clicks"),
        State("device-register-code", "value"),
        State("device-register-plant", "value"),
        State("device-register-transformer", "value"),
        State("device-register-status", "value"),
        prevent_initial_call=True,
    )
    def _prototype_submit(n_clicks, code, plant_id, transformer_id, status):
        """Prototype submit — no real persistence."""
        if not n_clicks:
            return no_update, no_update, no_update, no_update

        plant_label = next(
            (p.name for p in hierarchy_service.list_plants() if p.plant_id == plant_id),
            plant_id or "—",
        )
        transformer_label = next(
            (t.transformer_code for t in hierarchy_service.list_transformers(plant_id)
             if t.transformer_id == transformer_id),
            transformer_id or "—",
        )

        detail = html.Div(
            className="device-register-success-detail",
            children=[
                html.P(f"Device Code: {code.strip() if code else '—'}"),
                html.P(f"Plant: {plant_label}"),
                html.P(f"Transformer: {transformer_label}"),
                html.P(f"Status: {(status or 'active').capitalize()}"),
            ],
        )

        return (
            {"display": "none"},   # form hidden
            {"display": "none"},   # review hidden
            {"display": "block"},  # success visible
            detail,
        )
