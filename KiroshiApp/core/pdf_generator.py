"""PDF helpers placeholder for the experimental desktop prototype."""
from __future__ import annotations

from pathlib import Path

from .model import CaseData


def generate_case_pdf(case: CaseData, destination: Path) -> Path:
    """Create a minimal PDF representation of a case (stub implementation)."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(f"PDF export placeholder for {case.ticket_number}")
    return destination
