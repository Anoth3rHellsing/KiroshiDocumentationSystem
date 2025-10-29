"""Persistence helpers for autosave and case storage."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Mapping

from .model import CaseData
from .utils import get_database_root, read_json, utc_now_iso, write_json

LOGGER = logging.getLogger(__name__)
AUTOSAVE_FILENAME = "autosave.json"
CASE_EXTENSION = ".json"
CASES_DIRNAME = "cases"


def autosave_path(base_path: Path | None = None) -> Path:
    """Return the path where the autosave file is stored."""

    return get_database_root(base_path) / AUTOSAVE_FILENAME


def save_autosave(case: CaseData, base_path: Path | None = None) -> Path:
    """Write the active case to the autosave file and return the path used."""

    target = autosave_path(base_path)
    if not case.last_modified:
        case.last_modified = utc_now_iso()
    payload = {
        "case": case.to_dict(),
        "version": case.kiroshi_version,
        "last_modified": case.last_modified,
    }
    write_json(target, payload)
    return target


def load_autosave(base_path: Path | None = None) -> CaseData | None:
    """Load the autosaved case if one exists on disk."""

    path = autosave_path(base_path)
    payload = read_json(path)
    return _parse_case_payload(payload)


def save_case(case: CaseData, destination: Path) -> Path:
    """Persist ``case`` to ``destination`` ensuring the parent directory exists."""

    destination = destination.with_suffix(CASE_EXTENSION)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not case.last_modified:
        case.last_modified = utc_now_iso()
    payload = {
        "case": case.to_dict(),
        "version": case.kiroshi_version,
        "last_modified": case.last_modified,
    }
    write_json(destination, payload)
    return destination


def load_case(path: Path) -> CaseData:
    """Read a saved case from ``path`` supporting historical layouts."""

    payload = read_json(path)
    case = _parse_case_payload(payload)
    if case is None:
        raise FileNotFoundError(f"Unable to decode case at {path}")
    return case


def save_case_to_db(case: CaseData, base_path: Path | None = None) -> Path:
    """Persist the current case inside the database directory."""

    root = cases_root(base_path)
    filename = _safe_case_filename(case.case_id or "case")
    destination = root / filename
    return save_case(case, destination)


def cases_root(base_path: Path | None = None) -> Path:
    """Return the directory where persistent case files are stored."""

    root = get_database_root(base_path) / CASES_DIRNAME
    root.mkdir(parents=True, exist_ok=True)
    return root


def iter_case_files(base_path: Path | None = None):
    """Yield all known case file paths stored under the database root."""

    database_root = get_database_root(base_path)
    cases_dir = database_root / CASES_DIRNAME
    candidates: set[Path] = set()
    if database_root.exists():
        for candidate in database_root.glob(f"*{CASE_EXTENSION}"):
            if candidate.name == AUTOSAVE_FILENAME:
                continue
            candidates.add(candidate)
    if cases_dir.exists():
        candidates.update(cases_dir.glob(f"*{CASE_EXTENSION}"))
    for candidate in sorted(
        candidates,
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    ):
        yield candidate


def _parse_case_payload(payload: Any) -> CaseData | None:
    if isinstance(payload, Mapping):
        if "case" in payload and isinstance(payload["case"], Mapping):
            case_payload = payload["case"]
        else:
            case_payload = payload
        try:
            case = CaseData.from_json(case_payload)  # type: ignore[arg-type]
        except Exception as exc:
            LOGGER.warning("Failed to parse autosave payload: %s", exc)
            return None
        if not case.last_modified:
            case.last_modified = str(payload.get("last_modified") or "")
        if not case.last_modified:
            case.last_modified = utc_now_iso()
        return case
    if isinstance(payload, list):
        dict_entries = [item for item in payload if isinstance(item, Mapping)]
        if dict_entries:
            return _parse_case_payload(dict_entries[0])
    if payload is None:
        return None
    LOGGER.warning("Unsupported autosave payload: %s", type(payload).__name__)
    return None


def create_autosave_snapshot(case: CaseData, base_path: Path | None = None) -> Path:
    """Create a timestamped backup of ``case`` inside the database directory."""

    root = get_database_root(base_path)
    snapshot_dir = root / "backups"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    case_id = case.case_id or "case"
    timestamp = case.last_modified or utc_now_iso()
    safe_case_id = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in case_id)
    filename = f"autosave_{safe_case_id}_{timestamp.replace(':', '-')}.json"
    destination = snapshot_dir / filename
    write_json(destination, {"case": case.to_dict(), "version": case.kiroshi_version})
    return destination


def _safe_case_filename(case_id: str) -> str:
    text = case_id.strip() if case_id else "case"
    safe = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in text)
    return safe or "case"
