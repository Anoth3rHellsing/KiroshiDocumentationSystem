"""Data model placeholders for the experimental desktop prototype."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class RemoteSessionEntry:
    """Placeholder for remote session tracking."""

    notes: str = ""
    duration_minutes: int = 0


@dataclass
class TrackingData:
    """Placeholder for tracked case metadata."""

    status: str = "pending"
    priority: str = "normal"


@dataclass
class CaseData:
    """Minimal case payload used throughout the prototype."""

    customer_name: str = ""
    ticket_number: str = ""
    notes: str = ""
    remote_sessions: List[RemoteSessionEntry] = field(default_factory=list)
    tracking: TrackingData = field(default_factory=TrackingData)
