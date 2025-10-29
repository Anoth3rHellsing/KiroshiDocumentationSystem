"""Tracking helpers for the experimental desktop prototype."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, Iterator, Mapping, Optional

from .model import CaseData, TrackingData
from .storage import get_database_root

TRACKED_CASES_DIRNAME = "TrackedCases"


@dataclass
class TrackedCase:
    """Simple wrapper storing case tracking information."""

    case: CaseData
    data: TrackingData = field(default_factory=TrackingData)


@dataclass
class TrackedCaseRecord:
    """Metadata returned when listing tracked cases from disk."""

    case: CaseData
    path: Path
    is_legacy: bool = False


class TrackingManager:
    """In-memory registry of tracked cases for the prototype."""

    def __init__(self) -> None:
        self._cases: Dict[str, TrackedCase] = {}

    def start_tracking(self, case: CaseData) -> None:
        self._cases[case.case_id or case.company_name] = TrackedCase(case)

    def stop_tracking(self, ticket_number: str) -> None:
        self._cases.pop(ticket_number, None)

    def iter_tracked_cases(self) -> Iterable[TrackedCase]:
        return self._cases.values()


def _tracking_root(base_path: Optional[Path | str] = None) -> Path:
    return get_database_root(base_path) / TRACKED_CASES_DIRNAME


def _safe_tracking_filename(case_id: str) -> str:
    sanitized = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in case_id or "case")
    return f"{sanitized}.json"


def _read_case_payload(path: Path) -> Mapping[str, object] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if isinstance(data, Mapping) and "case" in data and isinstance(data["case"], Mapping):
        return data["case"]  # type: ignore[index]
    if isinstance(data, Mapping):
        return data
    return None


def start_tracking(case: CaseData, *, base_path: Optional[Path | str] = None) -> Path:
    """Persist tracking information for the provided case."""

    root = _tracking_root(base_path)
    root.mkdir(parents=True, exist_ok=True)
    filename = _safe_tracking_filename(case.case_id)
    destination = root / filename
    payload = {
        "case": case.to_dict(),
        "tracking": case.tracking.to_dict(),
    }
    destination.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return destination


def stop_tracking(case_id: str, *, base_path: Optional[Path | str] = None) -> bool:
    """Remove the tracking file for the specified case."""

    root = _tracking_root(base_path)
    filename = _safe_tracking_filename(case_id)
    path = root / filename
    if path.exists():
        path.unlink()
        return True
    return False


def list_tracked_cases(*, base_path: Optional[Path | str] = None) -> list[TrackedCaseRecord]:
    """Return tracked case metadata from disk."""

    root = _tracking_root(base_path)
    if not root.exists():
        return []

    records: list[TrackedCaseRecord] = []
    for path in sorted(root.glob("*.json")):
        payload = _read_case_payload(path)
        if not payload:
            continue
        case = CaseData.from_dict(payload)
        records.append(TrackedCaseRecord(case=case, path=path, is_legacy=False))
    return records
