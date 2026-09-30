"""Production authentication preflight (ADR-033).

    python -m scripts.auth_preflight            # enforces only when APP_ENV=production
    python -m scripts.auth_preflight --force    # run the checks in any environment

Exit 0 = safe to start; exit 1 = a numbered list of what to fix. It is wired in
front of the production start command (railway.json) so a deployment with demo
credentials, no session secret, or no usable Administrator fails closed with an
operator instruction instead of starting. It never prints a secret.
"""
from __future__ import annotations

import argparse
import sys

from config import settings
from services import auth_preflight


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--force", action="store_true", help="check even when APP_ENV is not production")
    args = parser.parse_args(argv)

    if not settings.IS_PRODUCTION and not args.force:
        print("auth preflight: APP_ENV is not production; nothing enforced.")
        return 0

    problems = auth_preflight.production_problems()
    if not problems:
        print("auth preflight: OK")
        return 0
    print("auth preflight: FAILED", file=sys.stderr)
    for number, problem in enumerate(problems, start=1):
        print(f"  {number}. {problem}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
