"""Template formatting helpers."""
from __future__ import annotations


def fmt_zar(value) -> str:
    try:
        if value is None:
            return "R 0.00"
        return f"R {float(value):,.2f}"
    except (TypeError, ValueError):
        return "R 0.00"
