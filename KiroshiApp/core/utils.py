"""Utility helpers placeholder for the experimental desktop prototype."""
from __future__ import annotations

from datetime import datetime, timezone


def utc_now_iso() -> str:
    """Return the current time in ISO-8601 format."""
    return datetime.now(timezone.utc).isoformat()
