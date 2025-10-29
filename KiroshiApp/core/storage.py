"""Storage helpers placeholder for the experimental desktop prototype."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from .model import CaseData


def get_database_root() -> Path:
    """Return the default directory used for local data storage."""
    return Path.home() / "KiroshiDatabase"


def save_case(case: CaseData, *, destination: Optional[Path] = None) -> Path:
    """Persist the case to disk (stub implementation)."""
    destination = destination or get_database_root() / "autosave.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(case.notes)
    return destination


def load_case(source: Optional[Path] = None) -> CaseData:
    """Load a case from disk returning a minimal placeholder object."""
    source = source or get_database_root() / "autosave.json"
    if source.exists():
        notes = source.read_text()
    else:
        notes = ""
    return CaseData(notes=notes)
