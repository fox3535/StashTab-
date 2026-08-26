"""Staging-only synthetic fixture interface.

Slice-00 does not connect to or create a staging database. Apply is a later unlock.
"""

from __future__ import annotations

import os
import sys


def main() -> int:
    env = (os.environ.get("APP_ENV") or "").strip().lower()
    if env != "staging":
        print("Refusing: APP_ENV must be staging for synthetic fixtures.", file=sys.stderr)
        return 2
    print(
        "Slice-00 fixture apply is disabled. No database connection was attempted. "
        "Use a later named unlock to load synthetic shops."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
