"""Attachment helpers placeholder for the experimental desktop prototype."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable


def sanitize_filename(name: str) -> str:
    """Return a filesystem friendly version of the provided name."""
    return "".join(ch for ch in name if ch.isalnum() or ch in {"-", "_"}).strip() or "attachment"


def list_attachments(case_folder: Path) -> Iterable[Path]:
    """Yield attachment files stored for a case (stub implementation)."""
    if not case_folder.exists():
        return []
    return sorted(path for path in case_folder.iterdir() if path.is_file())
