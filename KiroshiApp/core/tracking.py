"""Tracking helpers placeholder for the experimental desktop prototype."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable

from .model import CaseData, TrackingData


@dataclass
class TrackedCase:
    """Simple wrapper storing case tracking information."""

    case: CaseData
    data: TrackingData = field(default_factory=TrackingData)


class TrackingManager:
    """In-memory registry of tracked cases for the prototype."""

    def __init__(self) -> None:
        self._cases: Dict[str, TrackedCase] = {}

    def start_tracking(self, case: CaseData) -> None:
        self._cases[case.ticket_number] = TrackedCase(case)

    def stop_tracking(self, ticket_number: str) -> None:
        self._cases.pop(ticket_number, None)

    def iter_tracked_cases(self) -> Iterable[TrackedCase]:
        return self._cases.values()
