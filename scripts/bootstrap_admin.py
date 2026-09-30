"""One-time, explicit bootstrap of the initial Administrator (ADR-033).

    python -m scripts.bootstrap_admin --username <name> --full-name "<Full Name>" [--email <addr>]
    python -m scripts.bootstrap_admin ... --allow-additional     # an Administrator already exists

Creates ONE Administrator in `pending_activation` (or re-issues the setup link
for that same Pending Administrator — safe to repeat) and prints a single-use,
time-limited setup URL. The operator opens it and chooses the password; no
password is ever generated, printed or stored here.

It refuses when an Active Administrator with a password already exists (unless
--allow-additional). It writes ONLY the application PostgreSQL (the account, a
hashed token, one audit row) and never touches the client SQL Server. It is
never run at application start-up or at login.
"""
from __future__ import annotations

import argparse
import sys

from services import account_service


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--username", required=True)
    parser.add_argument("--full-name", default=None)
    parser.add_argument("--email", default=None)
    parser.add_argument("--allow-additional", action="store_true",
                        help="create another Administrator although one is already active")
    args = parser.parse_args(argv)

    try:
        result = account_service.bootstrap_administrator(
            username=args.username, full_name=args.full_name,
            email_address=args.email, allow_additional=args.allow_additional,
        )
    except account_service.AccountError as exc:
        print(f"bootstrap refused: {exc}", file=sys.stderr)
        return 1

    link = result.link
    print(f"Administrator '{link.username}' is {'created' if result.created else 're-issued'} "
          "in Pending activation.")
    print("One-time setup link (shown once; expires "
          f"{link.expires_at:%Y-%m-%d %H:%M} UTC; single use):")
    print(f"  {link.url}")
    print("Open it in a browser and choose a password of at least 12 characters.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
