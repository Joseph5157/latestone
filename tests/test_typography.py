"""The application ships the face it renders in.

`body` named `"Inter", system-ui, …` while nothing in the app ever fetched
Inter — only IBM Plex Sans has `@font-face` rules. So the application
rendered in whatever the viewer happened to have installed: Inter on a
machine that has it, Segoe UI on one that does not. Measured on the same
string those differ by ~10% in width, which moves every column fit and
truncation point in the app.

IBM Plex Sans is bundled, licensed (OFL, see assets/fonts/), industrial in
character, and was already being fetched for one gauge rule. Promoting it to
the UI face makes rendering deterministic and gives the type a point of view.

It ships exactly two weights, so the stylesheet declares exactly those two.
A weight a face does not have is not an error anywhere — the browser
synthesises it silently — which is how `650` came to style 10% of the text
on Device Management.
"""
from pathlib import Path
import re

import pytest

#: The weights present in assets/fonts/ibm-plex-sans/.
SHIPPED_WEIGHTS = {400, 600}


@pytest.fixture(scope="module")
def css():
    return (Path(__file__).resolve().parents[1] / "assets" / "app.css").read_text(
        encoding="utf-8"
    )


@pytest.fixture(scope="module")
def rules(css):
    """(selector, declarations) for every rule, comments stripped."""
    stripped = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    return [
        (" ".join(m.group(1).split()), m.group(2))
        for m in re.finditer(r"([^{}]+)\{([^}]*)\}", stripped)
    ]


class TestTheFaceIsShipped:
    def test_font_files_present_for_every_declared_face(self):
        fonts = Path(__file__).resolve().parents[1] / "assets" / "fonts" / "ibm-plex-sans"
        assert (fonts / "IBMPlexSans-Regular.woff2").exists()
        assert (fonts / "IBMPlexSans-SemiBold.woff2").exists()

    def test_the_ui_face_is_the_one_with_font_face_rules(self, css):
        """Guards the actual defect: a stack whose first family is never
        fetched renders as whatever the viewer has installed."""
        declared = set(re.findall(r"@font-face\s*\{[^}]*?font-family:\s*\"([^\"]+)\"", css, re.S))
        assert declared == {"IBM Plex Sans"}
        ui_stack = re.search(r"--font-ui:\s*([^;]+);", css).group(1)
        assert ui_stack.startswith('"IBM Plex Sans"')

    def test_body_renders_in_the_ui_face(self, css):
        body = re.search(r"\nbody\s*\{([^}]*)\}", css).group(1)
        assert "font-family: var(--font-ui)" in body

    def test_inter_is_no_longer_named_as_a_family(self, rules):
        """It was never fetched; naming it only made the fallback silent.

        Checks font-family declarations rather than the file text, so prose
        about the defect in a comment does not count as committing it again.
        """
        families = [
            value
            for _sel, body in rules
            for value in re.findall(r"font-family:\s*([^;]+);", body)
        ]
        assert families, "no font-family declarations found — check the parser"
        assert not any("Inter" in f for f in families)


class TestWeightsAreReal:
    def test_no_declared_weight_is_synthesised(self, rules):
        """A weight outside the shipped set is invented by the browser. `650`
        styled the ACTIVE chip on all 30 rows of Device Management."""
        used = {
            int(w)
            for _sel, body in rules
            for w in re.findall(r"font-weight:\s*(\d+)", body)
        }
        assert used <= SHIPPED_WEIGHTS, f"synthesised weights: {sorted(used - SHIPPED_WEIGHTS)}"

    def test_both_shipped_weights_are_actually_used(self, rules):
        """Bundling a face and then using one of its weights is what the
        gauge-only Plex usage already was."""
        used = {
            int(w)
            for _sel, body in rules
            for w in re.findall(r"font-weight:\s*(\d+)", body)
        }
        assert used == SHIPPED_WEIGHTS

    def test_the_chart_face_does_not_fork_from_the_ui_face(self, css):
        """`--font-fleet-chart` predates the UI face and named the same
        family a second time; two definitions drift."""
        assert "--font-fleet-chart: var(--font-ui)" in css
