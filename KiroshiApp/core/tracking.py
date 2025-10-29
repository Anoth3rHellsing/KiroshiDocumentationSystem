"""Tracking helpers for monitoring active cases."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from .model import CaseData, TrackingData
from .storage import save_case
from .utils import get_database_root, read_json, utc_now_iso, write_json

LOGGER = logging.getLogger(__name__)
TRACKED_DIR_NAME = "TrackedCases"


@dataclass
class TrackedCaseRecord:
    path: Path
    case: CaseData
    last_modified: str
    kiroshi_version: str | None = None
    is_legacy: bool = False


def start_tracking(case: CaseData, base_path: Path | None = None) -> Path:
    """Persist ``case`` as a tracked file, enabling tracking if necessary."""

    if not isinstance(case.tracking, TrackingData):
        if isinstance(case.tracking, Mapping):
            case.tracking = TrackingData(**case.tracking)  # type: ignore[arg-type]
        else:
            case.tracking = TrackingData()
    case.tracking.active = True
    case.last_modified = utc_now_iso()

    root = get_database_root(base_path) / TRACKED_DIR_NAME
    root.mkdir(parents=True, exist_ok=True)
    safe_name = _safe_case_filename(case.case_id)
    destination = root / f"{safe_name}.json"
    counter = 1
    while destination.exists():
        destination = root / f"{safe_name}_{counter}.json"
        counter += 1
    save_case(case, destination)
    return destination


def update_tracked_case(
    path: str | Path,
    *,
    tracking_updates: Mapping[str, Any] | None = None,
    case_updates: Mapping[str, Any] | None = None,
) -> CaseData:
    """Apply updates to a tracked case file returning the refreshed ``CaseData``."""

    path = Path(path)
    payload = read_json(path)
    if payload is None:
        raise FileNotFoundError(path)

    container, case_payload = _extract_case_payload(payload)
    if case_payload is None:
        raise ValueError(f"Unsupported tracked case format at {path}")

    case_data = dict(case_payload)
    if case_updates:
        case_data.update(case_updates)
    tracking_payload = case_data.get("tracking")
    if isinstance(tracking_payload, Mapping):
        merged = dict(tracking_payload)
    else:
        merged = {}
    if tracking_updates:
        merged.update(tracking_updates)
    if merged:
        merged.setdefault("active", True)
        case_data["tracking"] = merged

    case = CaseData.from_json(case_data)
    case.last_modified = utc_now_iso()
    container.update(
        {
            "case": case.to_dict(),
            "last_modified": case.last_modified,
            "version": container.get("version") or case.kiroshi_version,
        }
    )
    write_json(path, container)
    return case


def list_tracked_cases(base_path: Path | None = None) -> list[TrackedCaseRecord]:
    """Return every active tracked case stored on disk."""

    root = get_database_root(base_path)
    tracked_root = root / TRACKED_DIR_NAME
    candidates = list(root.glob("*.json")) + list(tracked_root.glob("*.json"))
    records: list[TrackedCaseRecord] = []
    for candidate in candidates:
        payload = read_json(candidate)
        if payload is None:
            continue
        container, case_payload = _extract_case_payload(payload)
        if case_payload is None:
            continue
        try:
            case = CaseData.from_json(case_payload)
        except Exception as exc:
            LOGGER.warning("Skipping invalid tracked case %s: %s", candidate, exc)
            continue
        tracking = case.tracking
        if not isinstance(tracking, TrackingData) or not tracking.active:
            continue
        last_modified = str(container.get("last_modified") or case.last_modified or "")
        if not last_modified:
            last_modified = utc_now_iso()
        container_dict = container or {}
        is_legacy = "case" not in container_dict
        records.append(
            TrackedCaseRecord(
                path=candidate,
                case=case,
                last_modified=last_modified,
                kiroshi_version=str(container_dict.get("version")) if container_dict else None,
                is_legacy=is_legacy,
            )
        )
    return sorted(records, key=lambda record: record.last_modified, reverse=True)


def _safe_case_filename(case_id: str) -> str:
    text = case_id or "case"
    safe = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in text)
    return safe or "case"


def _extract_case_payload(payload: Any) -> tuple[dict[str, Any] | None, Mapping[str, Any] | None]:
    if isinstance(payload, Mapping):
        if "case" in payload and isinstance(payload["case"], Mapping):
            return dict(payload), payload["case"]  # type: ignore[return-value]
        return dict(payload), payload
    if isinstance(payload, Iterable):
        for item in payload:
            if isinstance(item, Mapping):
                return dict(item), item
    return None, None
