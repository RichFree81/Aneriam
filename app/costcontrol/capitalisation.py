"""Capitalisation detection SQL fragments."""
from __future__ import annotations

from .config import CAPITALISATION_ACCOUNT_KEYWORDS


def build_capitalisation_clauses() -> tuple[str, str]:
    """Return (is_cap, not_cap) SQL boolean fragments for account_full_name."""
    likes = " OR ".join(
        f"account_full_name LIKE '%{kw.replace(chr(39), chr(39) * 2)}%'"
        for kw in CAPITALISATION_ACCOUNT_KEYWORDS
    )
    return f"({likes})", f"NOT ({likes})"


IS_CAP_SQL, NOT_CAP_SQL = build_capitalisation_clauses()
