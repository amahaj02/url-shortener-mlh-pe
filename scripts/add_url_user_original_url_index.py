#!/usr/bin/env python3
"""
Ensure the (user_id, original_url) index on url (same DDL as app startup).

Uses Peewee + DATABASE_* from the environment. Loads .env from the repo root.

Usage (from repo root):
  uv run python scripts/add_url_user_original_url_index.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv

load_dotenv(_ROOT / ".env")


def main() -> int:
    if os.getenv("TESTING", "").strip().lower() in {"1", "true", "yes", "on"}:
        print("Refusing to run while TESTING=true (use SQLite in tests).", file=sys.stderr)
        return 1

    from app.database import (
        URL_USER_ORIGINAL_URL_INDEX_NAME,
        close_db,
        connect_db,
        ensure_url_user_original_url_index,
        init_db,
    )

    init_db(testing=False)
    connect_db()
    try:
        ensure_url_user_original_url_index()
        print(
            f"OK: index {URL_USER_ORIGINAL_URL_INDEX_NAME} ensured on url (user_id, original_url).",
        )
    finally:
        close_db()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
