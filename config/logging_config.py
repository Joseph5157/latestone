"""
Application logging setup.

Configured once at startup by `app.py`. Callbacks catch broad exceptions to
keep the UI friendly, so without logging a genuine programming error is
indistinguishable from an expected database failure and leaves no trace —
which is precisely how several defects previously survived a green test suite.

Log records stay server-side. Nothing here is surfaced to the browser: user
facing errors go through `components.status_panels`, which never includes
stack traces, SQL, or connection details.
"""
from __future__ import annotations

import logging
import os
import sys

DEFAULT_LEVEL = "INFO"
_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"


def configure_logging() -> None:
    """Idempotent root logger setup honouring the LOG_LEVEL env var."""
    root = logging.getLogger()
    if root.handlers:  # already configured (e.g. Dash reloader re-import)
        return

    level_name = os.getenv("LOG_LEVEL", DEFAULT_LEVEL).upper()
    level = getattr(logging, level_name, logging.INFO)

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(_FORMAT))
    root.addHandler(handler)
    root.setLevel(level)
